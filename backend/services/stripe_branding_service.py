"""Branding du compte Stripe Connect d'un marchand (settings.branding :
icon, logo, primary_color, secondary_color) - affiché sur les reçus
Stripe UNIQUEMENT pour les paiements en direct charge (stripe_account=),
jamais pour une destination charge, qui montre le branding de la
PLATEFORME (voir conversation du 2026-11-11, confirmé sur le compte
Jupe). Ce module ne fait jamais de db.commit/db.add - rien à persister,
le branding vit entièrement côté Stripe, toujours relu depuis Stripe par
get_account_branding.

Point non-évident confirmé manuellement sur le compte Jupe : un fichier
business_icon/business_logo doit être uploadé avec la clé PLATEFORME et
SANS stripe_account= - un fichier créé avec ce paramètre devient
introuvable pour Account.modify ("No such file"), Stripe distinguant
l'espace de fichiers de la plateforme de celui du compte connecté.
"""
import io

import stripe


def upload_branding_file(data: bytes, purpose: str) -> str:
    """purpose : "business_icon" ou "business_logo". Jamais de
    stripe_account= ici (voir docstring du module). file_link_data crée
    tout de suite un lien public (autorisé par Stripe uniquement pour
    ces deux purposes) - c'est ce lien qui sert d'aperçu dans
    get_account_branding, jamais une URL devinée."""
    file = stripe.File.create(
        file=io.BytesIO(data),
        purpose=purpose,
        file_link_data={"create": True},
    )
    return file.id


def update_account_branding(
    account_id: str,
    icon_file_id: str | None,
    logo_file_id: str | None,
    primary_color: str | None,
    secondary_color: str | None,
) -> dict:
    """Ne pose que les champs fournis - jamais les autres champs du
    compte, jamais un champ branding non fourni (qui écraserait
    l'existant avec None côté Stripe). Stripe peut copier le fichier
    uploadé sous un autre id en l'assignant au compte (constaté) - on ne
    renvoie donc jamais l'id qu'on vient d'uploader, mais ce que Stripe a
    RÉELLEMENT stocké, relu depuis la réponse de cet appel."""
    branding: dict = {}
    if icon_file_id:
        branding["icon"] = icon_file_id
    if logo_file_id:
        branding["logo"] = logo_file_id
    if primary_color:
        branding["primary_color"] = primary_color
    if secondary_color:
        branding["secondary_color"] = secondary_color

    account = stripe.Account.modify(account_id, settings={"branding": branding})
    return _serialize_branding(account.settings.branding if account.settings else None)


def get_account_branding(account_id: str) -> dict:
    """Relit toujours depuis Stripe (voir docstring du module) - jamais
    de cache local, jamais d'id de fichier stocké côté Xepay."""
    account = stripe.Account.retrieve(account_id)
    return _serialize_branding(account.settings.branding if account.settings else None)


def _serialize_branding(branding) -> dict:
    icon_id = getattr(branding, "icon", None) if branding else None
    logo_id = getattr(branding, "logo", None) if branding else None
    return {
        "primary_color": getattr(branding, "primary_color", None) if branding else None,
        "secondary_color": getattr(branding, "secondary_color", None) if branding else None,
        "icon": _file_preview(icon_id),
        "logo": _file_preview(logo_id),
    }


def _file_preview(file_id: str | None) -> dict | None:
    """Les purposes business_icon/business_logo ne sont pas directement
    re-téléchargeables (file.url) - le lien public créé à l'upload
    (file_link_data) est la seule façon fiable d'obtenir un aperçu.
    Si aucun lien n'existe (branding réglé avant ce chantier, ou en
    dehors de Xepay), on renvoie l'id sans aperçu plutôt que de deviner
    une URL."""
    if not file_id:
        return None
    try:
        file = stripe.File.retrieve(file_id)
        link = file.links.data[0].url if file.links and file.links.data else None
        return {"id": file.id, "url": link}
    except stripe.error.StripeError:
        return {"id": file_id, "url": None}
