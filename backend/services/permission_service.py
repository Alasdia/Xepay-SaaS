"""Permissions par rôle, configurables par le owner de chaque workspace.

Contexte produit (conversation du 2026-10-25) : la configuration actuelle
de l'app (quel rôle minimal peut faire quoi, voir CAPABILITIES ci-dessous)
est exactement ce qui est voulu - elle devient donc la configuration PAR
DÉFAUT, et le owner d'un workspace obtient le pouvoir d'en décider
autrement pour SON workspace (jamais pour les autres). Granularité par
rôle (pas par membre individuel) : un changement s'applique à TOUT le
rôle concerné.

Ce module ne couvre QUE les actions déjà gardées par un rôle au-dessus du
plancher actuel (require_manager/require_admin/require_owner) - les
actions déjà ouvertes à tout membre (require_member, qui inclut déjà
"lecteur") n'ont rien à configurer, il n'existe rien de plus bas.

Le mécanisme de plan Free/Pro/Business (require_pro_or_business/
require_business dans middleware/authorization.py) a été entièrement
retiré le 2026-11-23 (demande explicite de l'utilisateur) - toutes les
fonctionnalités qu'il réservait (clés API/webhooks/logs, export, liens
internationaux, équipe multi-utilisateurs) sont désormais ouvertes à
tout workspace, peu importe un plan qui n'existe plus côté accès. Seule
la commission dégressive par volume (commission_service.py), un
mécanisme entièrement séparé, a été conservée - voir view_commission_rate
ci-dessous.
"""

from sqlalchemy.orm import Session

from backend.models import WorkspacePermissionOverride

# Ordre du plus privilégié au moins privilégié - l'index sert à comparer
# "ce rôle a-t-il AU MOINS le rôle minimal requis".
ROLE_ORDER = ["owner", "admin", "manager", "membre", "lecteur"]

ROLE_LABELS = {
    "owner": "Propriétaire uniquement",
    "admin": "Admin et plus",
    "manager": "Manager et plus",
    "membre": "Membre et plus",
    "lecteur": "Tout le monde (y compris Lecteur)",
}

# Rôle minimal PAR DÉFAUT pour chaque capacité - reflète exactement ce que
# le code impose déjà aujourd'hui (voir le fichier/la ligne cité en
# commentaire), avant toute personnalisation par un owner. Ne JAMAIS
# changer ces valeurs pour "corriger" un comportement : ce sont les
# défauts d'origine, un changement de comportement voulu passe par une
# config.set_override, pas par ce dictionnaire.
CAPABILITY_DEFAULTS = {
    "create_payment_links": "manager",       # POST /links (routes/lien.py)
    "manage_stripe_billing": "manager",       # /stripe/connect/{invoices,subscriptions,products,customers}* (routes/webhook/stripe.py)
    "view_stripe_account_info": "manager",    # GET /stripe/status, /stripe/business-details
    "manage_stripe_account_config": "owner",  # /onboarding, /stripe/login-link, /stripe/account-session
    # PATCH /profile uniquement (GET /profile est passée à require_member
    # le 2026-11-22 - voir routes/users.py - car elle mélange des données
    # partagées avec le workspace et des données personnelles à
    # current_user, qu'un membre doit toujours pouvoir consulter). Rôle
    # minimal remonté de "manager" à "owner" le 2026-11-22 (décision
    # explicite) : Nom/Téléphone de contact ne doivent plus être
    # modifiables par un admin/manager non-propriétaire par défaut - le
    # owner peut toujours rouvrir cette capacité pour son propre workspace
    # via Permissions.
    "manage_workspace_profile": "owner",      # PATCH /profile
    "view_commission_rate": "manager",        # GET /me/commission
    "manage_team": "admin",                   # /invites, /users (POST/PUT/DELETE/toggle)
    "withdraw_funds": "owner",                # /withdraw, /withdraw/{id}/process, /withdrawals
    "export_reports": "manager",              # /reports/financial, /reports/connect-session
    "manage_company_formation": "owner",      # /buildness/onboard, /buildness/status/{merchant_id} (routes/buildness.py)
    "manage_shopify_integration": "owner",    # GET /shopify/install, /shopify/status (routes/shopify.py)
    "view_shopify_data": "manager",           # GET /shopify/products, /orders, /customers (routes/shopify.py)
}

CAPABILITY_LABELS = {
    "create_payment_links": ("Créer des liens de paiement", "Générer de nouveaux liens de paiement pour encaisser des clients."),
    "manage_stripe_billing": ("Gérer les factures et abonnements Stripe", "Créer/modifier des factures, abonnements, produits et clients côté Stripe Connect."),
    "view_stripe_account_info": ("Consulter le compte Stripe Connect", "Voir le statut de vérification et les informations du compte Stripe Connect."),
    "manage_stripe_account_config": ("Configurer le compte Stripe Connect", "Lancer l'onboarding Stripe, accéder au Dashboard Stripe, modifier les informations Stripe du compte."),
    "manage_workspace_profile": ("Modifier les informations du compte", "Modifier le nom/téléphone de contact affichés pour ce workspace (la lecture reste ouverte à tout membre)."),
    "view_commission_rate": ("Consulter la commission Xepay", "Voir le taux de commission dégressif actuel et le volume encaissé ce mois."),
    "manage_team": ("Gérer l'équipe", "Inviter, changer le rôle, suspendre ou supprimer un membre."),
    "withdraw_funds": ("Retirer des fonds", "Initier et traiter un retrait depuis le solde disponible."),
    "export_reports": ("Exporter des rapports", "Télécharger un rapport financier ou ouvrir le rapport Stripe intégré."),
    "manage_company_formation": ("Créer une LLC (Buildness)", "Démarrer la formation d'une LLC américaine et consulter son avancement (EIN, documents)."),
    "manage_shopify_integration": ("Connecter une boutique Shopify", "Lier une boutique Shopify au workspace pour encaisser ses commandes via Xepay."),
    "view_shopify_data": ("Consulter les données Shopify", "Voir les produits, commandes et clients de la boutique Shopify connectée (onglet Commerce)."),
}


def normalize_role(role: str) -> str:
    return (role or "").lower().strip()


def role_rank(role: str) -> int:
    role = normalize_role(role)
    return ROLE_ORDER.index(role) if role in ROLE_ORDER else len(ROLE_ORDER)


def role_satisfies(role: str, min_role: str) -> bool:
    """True si `role` est au moins aussi privilégié que `min_role`."""
    return role_rank(role) <= role_rank(min_role)


def get_effective_min_role(db: Session, workspace_id: str, capability_key: str) -> str:
    override = (
        db.query(WorkspacePermissionOverride)
        .filter(
            WorkspacePermissionOverride.workspace_id == workspace_id,
            WorkspacePermissionOverride.capability_key == capability_key,
        )
        .first()
    )
    if override:
        return override.min_role
    return CAPABILITY_DEFAULTS.get(capability_key, "owner")


def list_capabilities(db: Session, workspace_id: str) -> list[dict]:
    overrides = {
        o.capability_key: o.min_role
        for o in db.query(WorkspacePermissionOverride)
        .filter(WorkspacePermissionOverride.workspace_id == workspace_id)
        .all()
    }
    result = []
    for key, default_role in CAPABILITY_DEFAULTS.items():
        label, description = CAPABILITY_LABELS.get(key, (key, ""))
        current = overrides.get(key, default_role)
        result.append({
            "key": key,
            "label": label,
            "description": description,
            "default_role": default_role,
            "current_role": current,
            "is_overridden": key in overrides,
        })
    return result


def set_override(db: Session, workspace_id: str, capability_key: str, min_role: str) -> None:
    if capability_key not in CAPABILITY_DEFAULTS:
        raise ValueError(f"Capacité inconnue : {capability_key}")
    if normalize_role(min_role) not in ROLE_ORDER:
        raise ValueError(f"Rôle invalide : {min_role}")
    min_role = normalize_role(min_role)

    existing = (
        db.query(WorkspacePermissionOverride)
        .filter(
            WorkspacePermissionOverride.workspace_id == workspace_id,
            WorkspacePermissionOverride.capability_key == capability_key,
        )
        .first()
    )
    # Revenir au défaut = ne garder aucune ligne (pas une ligne redondante
    # qui dupliquerait CAPABILITY_DEFAULTS) - évite une dérive silencieuse
    # si le défaut change un jour dans le code sans que cette ligne ne
    # suive.
    if min_role == CAPABILITY_DEFAULTS[capability_key]:
        if existing:
            db.delete(existing)
            db.commit()
        return

    if existing:
        existing.min_role = min_role
    else:
        db.add(WorkspacePermissionOverride(
            workspace_id=workspace_id,
            capability_key=capability_key,
            min_role=min_role,
        ))
    db.commit()


def reset_override(db: Session, workspace_id: str, capability_key: str) -> None:
    db.query(WorkspacePermissionOverride).filter(
        WorkspacePermissionOverride.workspace_id == workspace_id,
        WorkspacePermissionOverride.capability_key == capability_key,
    ).delete()
    db.commit()
