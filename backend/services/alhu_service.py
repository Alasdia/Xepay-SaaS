"""Alhu — assistant marchand en LECTURE SEULE (demandé le 2026-11-27,
première brique d'une architecture agent plus large envisagée par
l'utilisateur). Volontairement minimal pour ce premier chantier :
- UN seul agent (pas de directeur + sous-agents, voir la discussion
  avec l'utilisateur - on commence petit, on scale seulement une fois
  l'approche prouvée).
- AUCUN outil d'écriture : les 3 outils exposés (solde, transactions
  récentes, statut Buildness) ne font que lire des données déjà
  visibles ailleurs dans le dashboard, jamais une action côté Stripe/
  doola/Shopify. Pas de permission_policy "always_ask" à construire ici
  tant qu'aucun outil n'écrit quoi que ce soit.
- Remplace routes/app.py (ancien stub OpenAI /ai/chat, jamais appelé par
  aucun frontend, supprimé le 2026-11-27) - clé/SDK différents
  (ANTHROPIC_API_KEY, pas OPENAI_API_KEY), jamais réutilisé.
"""

import logging
import os
import re

import stripe
from sqlalchemy.orm import Session

from backend.models import BuildnessCompany, BuildnessCustomer, Profile, Wallet, WalletTransaction

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALHU_MODEL = os.getenv("ALHU_MODEL", "claude-sonnet-5")
# Même clé/convention que services/stripe_service.py, routes/buildness.py -
# posée ici aussi (pas seulement supposée déjà positionnée par un autre
# module importé avant celui-ci) pour que get_stripe_connect_status
# fonctionne même si alhu_service est importé isolément.
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Boucle outil/réponse bornée (demande normale : plusieurs outils en
# chaîne, ex. lister un dossier PUIS lire 2-3 fichiers PUIS répondre) -
# jamais illimitée, au cas où le modèle boucle sur un appel d'outil sans
# jamais conclure. Relevé de 5 à 8 le 2026-11-27 (ajout des outils
# produit ci-dessous, qui demandent souvent plusieurs allers-retours
# lister/lire avant de pouvoir répondre).
MAX_TOOL_ROUNDS = 8

# Racine UNIQUE et FERMÉE pour les outils de lecture produit ci-dessous
# (list_product_files/read_product_file, demandés le 2026-11-27) :
# "frontend" seulement - jamais "backend" (logique métier/sécurité
# interne, hors sujet pour un assistant marchand) ni la racine du dépôt
# (.env, alembic/...). Couvre à la fois les pages marketing
# (frontend/pages/*.html) et "absolument tout" le code source du SPA
# (frontend/pages/spa/**) avec le même mécanisme, puisque les deux
# vivent sous ce même répertoire.
_SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCT_READ_ROOT = os.path.abspath(os.path.join(_SERVICE_DIR, "..", "..", "frontend"))

# Extensions texte autorisées en lecture - jamais un binaire (image/
# police/etc.) renvoyé tel quel comme "contenu de fichier".
_PRODUCT_READ_EXTENSIONS = {".html", ".js", ".css", ".json", ".md", ".txt"}
_PRODUCT_READ_MAX_CHARS = 40_000
_PRODUCT_LIST_MAX_ENTRIES = 400
# Jamais parcourus/lus (demande implicite - rien à voir avec les pages
# marketing ou l'architecture du SPA, uniquement du bruit/des assets).
_PRODUCT_READ_EXCLUDED_DIRS = {"node_modules", ".git"}


def _resolve_product_path(relative_path: str) -> str:
    """Résout relative_path SOUS PRODUCT_READ_ROOT uniquement - lève
    ValueError si le chemin résolu sort de cette racine (traversée "..",
    chemin absolu détourné...). Seul point d'entrée filesystem des 2
    outils ci-dessous, jamais contourné."""
    candidate = os.path.abspath(os.path.join(PRODUCT_READ_ROOT, relative_path or ""))
    if not (candidate == PRODUCT_READ_ROOT or candidate.startswith(PRODUCT_READ_ROOT + os.sep)):
        raise ValueError("Chemin hors du périmètre autorisé (frontend/ uniquement).")
    return candidate

ALHU_SYSTEM_PROMPT = """Tu es Alhu, l'assistant intégré au tableau de bord Xepay (plateforme de paiement pour marchands).

Tu réponds à 3 types de questions, toujours via les outils fournis - jamais à partir de connaissances générales non vérifiées, et jamais en inventant une donnée ou une fonctionnalité :
1. Questions sur les DONNÉES PROPRES du marchand (solde, transactions, dossier de création de société/LLC) - outils get_balance/get_recent_transactions/get_buildness_status.
2. Questions sur LE PRODUIT Xepay lui-même (fonctionnalités, tarifs, fonctionnement du tableau de bord) - outils list_product_files/read_product_file, qui donnent accès en LECTURE SEULE aux pages marketing et à tout le code source du SPA (frontend/pages/*.html et frontend/pages/spa/). ATTENTION : les pages marketing (frontend/pages/accueil.html, tarif.html...) décrivent l'offre générale (plans Free/Pro/Business) mais PAS les fonctionnalités internes au tableau de bord (Buildness, Stripe Connect, Shopify...) - leur coût/fonctionnement réels sont codés en dur dans le SPA, jamais sur une page marketing. Pour le coût/processus de la formation de LLC spécifiquement, utilise TOUJOURS get_buildness_info (rapide, lit la bonne info directement) plutôt que read_product_file sur parametres.js en entier (40+ Ko, beaucoup trop lent et peu fiable sur ce fichier précis). Pour toute autre question précise sur une fonctionnalité du tableau de bord sans outil dédié, lis le fichier de vue correspondant dans frontend/pages/spa/views/ avec read_product_file avant de répondre - ne te contente jamais d'une recherche dans les pages marketing seules pour ce type de question, et si après une recherche réelle tu ne trouves toujours rien, dis-le explicitement plutôt que de deviner.
3. Questions sur l'ACTIVATION DU COMPTE STRIPE CONNECT du marchand - outil get_stripe_connect_status. Tous les marchands Xepay sont des fondateurs non-résidents ayant formé une LLC américaine (via Buildness/doola) pour pouvoir utiliser Stripe Connect. Tu peux expliquer en général les grandes étapes de cette activation (informations de l'entreprise, informations du représentant légal, coordonnées bancaires, documents de vérification d'identité) MAIS pour savoir précisément ce qu'IL reste à fournir à CE marchand, utilise TOUJOURS get_stripe_connect_status et base-toi sur ses champs currently_due/eventually_due_in_addition réels (déjà traduits en français, identiques à ce que voit le marchand dans Paramètres > Compte Stripe Connect > État du compte) - ne récite jamais une liste de documents par cœur, elle peut être fausse ou incomplète pour sa situation. Tu ne peux JAMAIS remplir ce formulaire à sa place (Stripe l'interdit structurellement, les champs KYC doivent venir directement du titulaire du compte) : ton rôle est de l'accompagner et de lui relayer clairement ce qui lui manque, pas de le compléter pour lui.

Règles strictes :
- Tu ne peux RIEN modifier, créer ou annuler, nulle part : tu n'as accès qu'à des outils de LECTURE. Si le marchand demande une action (remboursement, modification, création), explique clairement que tu ne peux pas l'exécuter et indique où le faire dans le dashboard (ex. Paramètres > Entreprise pour une demande de correction LLC).
- Les outils produit ne donnent accès qu'au code FRONTEND (pages marketing + SPA) - jamais au code backend, à des secrets ou à des données d'autres marchands.
- Si une information demandée n'est couverte par aucun outil, dis-le explicitement plutôt que de deviner.
- Réponds en français, de façon concise et directe.
"""

ALHU_TOOLS = [
    {
        "name": "get_balance",
        "description": "Renvoie le solde du workspace du marchand (disponible et en attente), en devise de la plateforme.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_recent_transactions",
        "description": "Renvoie les transactions les plus récentes du workspace (paiements reçus, retraits, remboursements...), triées de la plus récente à la plus ancienne.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Nombre de transactions à renvoyer (par défaut 10, maximum 20).",
                }
            },
        },
    },
    {
        "name": "get_buildness_status",
        "description": "Renvoie l'état du dossier de création de société américaine (LLC) et d'obtention de l'EIN du marchand, s'il en a lancé un.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "list_product_files",
        "description": "Liste les fichiers/dossiers sous un sous-chemin de frontend/ (pages marketing HTML + tout le code source du SPA). Appeler avec subpath=\"\" pour voir la racine, puis descendre dans les sous-dossiers d'intérêt (ex. \"pages/spa/views\").",
        "input_schema": {
            "type": "object",
            "properties": {
                "subpath": {
                    "type": "string",
                    "description": "Sous-chemin relatif à frontend/ à lister (ex. \"pages\", \"pages/spa/views\"). Vide ou omis = racine de frontend/.",
                }
            },
        },
    },
    {
        "name": "read_product_file",
        "description": "Lit le contenu d'un fichier texte sous frontend/ (page marketing HTML, ou tout fichier du code source du SPA - .js/.css/.json/.md). Lecture seule, jamais d'écriture.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Chemin relatif à frontend/ du fichier à lire (ex. \"pages/accueil.html\", \"pages/spa/views/commerce.js\").",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "get_stripe_connect_status",
        "description": "Renvoie l'état RÉEL et à jour de l'activation du compte Stripe Connect du marchand : si le compte existe, si les paiements/retraits sont activés, et la liste exacte (currently_due/eventually_due_in_addition) des informations encore requises par Stripe pour CE marchand précis - déjà traduite en français, identique à ce qu'affiche Paramètres > Compte Stripe Connect > État du compte. Toujours utiliser cet outil plutôt que deviner une liste générique de documents.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_buildness_info",
        "description": "Renvoie le prix actuel de la formation de LLC (Buildness) et le détail des étapes du processus, extraits en direct du tableau de bord (jamais une valeur devinée ou mémorisée). Toujours utiliser cet outil pour une question sur le coût ou le déroulement de la création de LLC, plutôt que de chercher dans les pages marketing (qui ne couvrent pas cette fonctionnalité) ou de lire parametres.js en entier.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def _get_balance(db: Session, workspace_id: str) -> dict:
    wallet = db.query(Wallet).filter(Wallet.user_id == workspace_id).first()
    if not wallet:
        return {"available": 0, "pending": 0}
    return {"available": wallet.available, "pending": wallet.pending}


def _get_recent_transactions(db: Session, workspace_id: str, limit: int | None) -> dict:
    # Borné (demande du 2026-11-27) - ni un marchand ni le modèle n'ont
    # besoin de récupérer un historique illimité d'un coup ici, Alhu
    # reste un assistant de consultation ponctuelle, pas un export.
    safe_limit = max(1, min(int(limit or 10), 20))
    rows = (
        db.query(WalletTransaction)
        .filter(WalletTransaction.user_id == workspace_id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(safe_limit)
        .all()
    )
    return {
        "transactions": [
            {
                "type": r.type,
                "direction": r.direction,
                "amount": r.amount,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "description": r.description,
            }
            for r in rows
        ]
    }


def _get_buildness_status(db: Session, workspace_id: str) -> dict:
    customer = (
        db.query(BuildnessCustomer)
        .filter(BuildnessCustomer.xepay_merchant_id == workspace_id)
        .first()
    )
    if not customer:
        return {"status": "not_started"}
    company = (
        db.query(BuildnessCompany)
        .filter(BuildnessCompany.customer_id == customer.id)
        .order_by(BuildnessCompany.created_at.desc())
        .first()
    )
    if not company:
        return {"status": "not_started"}
    return {
        "status": company.status,
        "company_name": company.company_name,
        "state": company.state,
        "ein_number": company.ein_number,
        "last_successful_step": company.last_successful_step,
    }


def _list_product_files(subpath: str | None) -> dict:
    try:
        base = _resolve_product_path(subpath or "")
    except ValueError as e:
        return {"error": str(e)}
    if not os.path.isdir(base):
        return {"error": "Ce chemin n'est pas un dossier."}

    entries = []
    for root, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in _PRODUCT_READ_EXCLUDED_DIRS]
        for name in sorted(dirnames) + sorted(filenames):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, PRODUCT_READ_ROOT)
            entries.append(rel + ("/" if os.path.isdir(full) else ""))
            if len(entries) >= _PRODUCT_LIST_MAX_ENTRIES:
                return {"entries": entries, "truncated": True}
    return {"entries": entries, "truncated": False}


def _read_product_file(path: str | None) -> dict:
    if not path:
        return {"error": "path manquant."}
    try:
        full = _resolve_product_path(path)
    except ValueError as e:
        return {"error": str(e)}
    if not os.path.isfile(full):
        return {"error": "Ce fichier n'existe pas."}
    _, ext = os.path.splitext(full)
    if ext.lower() not in _PRODUCT_READ_EXTENSIONS:
        return {"error": f"Extension non lisible ({ext or 'inconnue'}) - fichiers texte uniquement (.html/.js/.css/.json/.md/.txt)."}
    try:
        with open(full, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(_PRODUCT_READ_MAX_CHARS + 1)
    except OSError as e:
        return {"error": f"Lecture impossible : {e}"}
    truncated = len(content) > _PRODUCT_READ_MAX_CHARS
    if truncated:
        content = content[:_PRODUCT_READ_MAX_CHARS]
    return {"content": content, "truncated": truncated}


# Port Python EXACT de STRIPE_REQUIREMENT_LABELS/formatStripeRequirement
# (frontend/pages/spa/views/parametres.js, section "État du compte") -
# demandé le 2026-11-27 pour qu'Alhu donne toujours le MÊME libellé
# français que ce que voit déjà le marchand à l'écran. Traduit ici
# directement en Python (déterministe, zéro appel d'outil
# supplémentaire) plutôt que de faire relire ce fichier de 40+ Ko par
# le modèle à chaque question Stripe - testé, beaucoup trop lent/
# instable (plusieurs relectures redondantes, risque de ne jamais
# conclure dans MAX_TOOL_ROUNDS). Les deux copies doivent rester
# synchronisées manuellement si l'une des deux change.
_STRIPE_REQUIREMENT_LABELS = {
    "business_profile.mcc": "Secteur d'activité",
    "business_profile.url": "Site web de l'entreprise",
    "business_profile.product_description": "Description du produit ou service",
    "business_profile.support_phone": "Téléphone du service client",
    "business_profile.support_email": "Email du service client",
    "business_profile.support_address": "Adresse du service client",
    "business_type": "Type d'entreprise (société, particulier...)",
    "external_account": "Coordonnées bancaires pour recevoir les virements",
    "tos_acceptance.date": "Acceptation des conditions Stripe",
    "tos_acceptance.ip": "Acceptation des conditions Stripe",
    "settings.payments.statement_descriptor": "Libellé affiché sur les relevés bancaires de vos clients",
    "company.name": "Raison sociale de l'entreprise",
    "company.tax_id": "Numéro fiscal (SIRET/TVA) de l'entreprise",
    "company.phone": "Téléphone de l'entreprise",
    "company.address.line1": "Adresse de l'entreprise",
    "company.address.postal_code": "Adresse de l'entreprise",
    "company.address.city": "Adresse de l'entreprise",
    "company.verification.document": "Document d'immatriculation de l'entreprise",
}
for _field in ("dob.day", "dob.month", "dob.year"):
    _STRIPE_REQUIREMENT_LABELS[f"representative.{_field}"] = "Date de naissance du représentant légal"
    _STRIPE_REQUIREMENT_LABELS[f"individual.{_field}"] = "Date de naissance"
for _key, _label in (
    ("first_name", "Prénom"),
    ("last_name", "Nom"),
    ("email", "Email"),
    ("phone", "Numéro de téléphone"),
    ("id_number", "Numéro d'identité"),
    ("verification.document", "Pièce d'identité"),
    ("address.line1", "Adresse"),
    ("address.postal_code", "Adresse"),
    ("address.city", "Adresse"),
):
    _STRIPE_REQUIREMENT_LABELS[f"representative.{_key}"] = f"{_label} du représentant légal"
    _STRIPE_REQUIREMENT_LABELS[f"individual.{_key}"] = _label


def _format_stripe_requirement(code: str) -> str:
    if code in _STRIPE_REQUIREMENT_LABELS:
        return _STRIPE_REQUIREMENT_LABELS[code]
    # Repli pour un code non mappé (même logique que le frontend) :
    # rendre au moins lisible plutôt que d'afficher le jargon brut.
    return " ".join(w.capitalize() for w in re.split(r"[._]", code) if w)


def _format_stripe_requirement_list(codes: list[str]) -> list[str]:
    seen = set()
    labels = []
    for code in codes:
        label = _format_stripe_requirement(code)
        if label not in seen:
            seen.add(label)
            labels.append(label)
    return labels


def _get_stripe_connect_status(db: Session, workspace_id: str) -> dict:
    profile = db.query(Profile).filter(Profile.user_id == workspace_id).first()
    if not profile or not profile.stripe_account_id:
        return {
            "status": "not_started",
            "note": "Aucun compte Stripe Connect n'a encore été créé pour ce marchand.",
        }
    try:
        account = stripe.Account.retrieve(profile.stripe_account_id)
    except stripe.error.StripeError:
        logger.exception("Echec recuperation compte Stripe Connect pour workspace_id=%s", workspace_id)
        return {"error": "Impossible de récupérer le statut Stripe Connect pour le moment."}

    requirements = account.requirements or {}
    charges_enabled = account.charges_enabled
    payouts_enabled = account.payouts_enabled
    if charges_enabled and payouts_enabled:
        status = "active"
    elif account.details_submitted:
        status = "pending_review"
    else:
        status = "in_progress"

    currently_due = requirements.get("currently_due", [])
    # eventually_due est un sur-ensemble de currently_due (même remarque
    # que côté frontend) - on ne renvoie que ce qui s'ajoute EN PLUS,
    # jamais une liste dupliquée.
    eventually_due_extra = [c for c in requirements.get("eventually_due", []) if c not in currently_due]

    return {
        "status": status,
        "details_submitted": account.details_submitted,
        "charges_enabled": charges_enabled,
        "payouts_enabled": payouts_enabled,
        # Déjà traduits en français (identique à Paramètres > Compte
        # Stripe Connect > État du compte) - jamais les codes bruts
        # Stripe, jamais une traduction inventée par le modèle.
        "currently_due": _format_stripe_requirement_list(currently_due),
        "eventually_due_in_addition": _format_stripe_requirement_list(eventually_due_extra),
        "past_due": _format_stripe_requirement_list(requirements.get("past_due", [])),
        "disabled_reason": requirements.get("disabled_reason"),
    }


def _get_buildness_info() -> dict:
    """Extrait le prix et le processus Buildness directement depuis
    parametres.js, LU À CHAQUE APPEL (jamais mis en cache ni codé en
    dur - reste toujours synchro avec le vrai texte affiché) - ajouté
    le 2026-11-27 : laisser le modèle lire ce fichier de 40+ Ko en
    entier à chaque question Buildness était trop lent/peu fiable
    (même constat que pour get_stripe_connect_status/parametres.js
    plus haut - plusieurs relectures redondantes, risque de ne jamais
    conclure dans MAX_TOOL_ROUNDS)."""
    try:
        path = _resolve_product_path("pages/spa/views/parametres.js")
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except (ValueError, OSError) as e:
        return {"error": f"Lecture impossible : {e}"}

    price_match = re.search(r"Créer ma société \(([^)]+)\)", content)

    steps = []
    modal_start = content.find("BUILDNESS_INFO_MODAL_HTML")
    if modal_start != -1:
        modal_chunk = content[modal_start:modal_start + 3000]
        for raw_step in re.findall(r"<li>(.*?)</li>", modal_chunk, re.DOTALL):
            steps.append(re.sub(r"<[^>]+>", "", raw_step).strip())

    return {
        "price": price_match.group(1) if price_match else None,
        "process_steps": steps,
    }


def _execute_tool(tool_name: str, tool_input: dict, db: Session, workspace_id: str) -> dict:
    if tool_name == "get_balance":
        return _get_balance(db, workspace_id)
    if tool_name == "get_recent_transactions":
        return _get_recent_transactions(db, workspace_id, tool_input.get("limit"))
    if tool_name == "get_buildness_status":
        return _get_buildness_status(db, workspace_id)
    if tool_name == "list_product_files":
        return _list_product_files(tool_input.get("subpath"))
    if tool_name == "read_product_file":
        return _read_product_file(tool_input.get("path"))
    if tool_name == "get_stripe_connect_status":
        return _get_stripe_connect_status(db, workspace_id)
    if tool_name == "get_buildness_info":
        return _get_buildness_info()
    return {"error": f"Outil inconnu : {tool_name}"}


class AlhuNotConfiguredError(Exception):
    pass


def run_alhu_chat(db: Session, workspace_id: str, user_messages: list[dict]) -> str:
    """user_messages : historique de la conversation côté client, déjà
    au format Anthropic ({"role": "user"/"assistant", "content": "..."}),
    jamais persisté côté serveur pour ce premier chantier (voir le
    commentaire d'en-tête) - le client renvoie tout l'historique à
    chaque appel."""
    if not ANTHROPIC_API_KEY:
        raise AlhuNotConfiguredError("ANTHROPIC_API_KEY non configurée")

    # Import différé (démarrage du serveur ne doit jamais échouer si le
    # SDK est absent/la clé manquante - même raison que get_doola_service
    # dans doola_client.py, pattern déjà établi dans ce projet).
    import anthropic

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = list(user_messages)

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=ALHU_MODEL,
            max_tokens=1024,
            system=ALHU_SYSTEM_PROMPT,
            tools=ALHU_TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _execute_tool(block.name, block.input or {}, db, workspace_id)
            except Exception:
                logger.exception("Echec execution outil Alhu %s", block.name)
                result = {"error": "Erreur interne lors de l'exécution de cet outil."}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": str(result),
            })
        messages.append({"role": "user", "content": tool_results})

    logger.warning("Alhu : MAX_TOOL_ROUNDS atteint pour workspace_id=%s sans réponse finale", workspace_id)
    return "Désolé, je n'ai pas pu finaliser ma réponse. Réessayez en reformulant votre question."
