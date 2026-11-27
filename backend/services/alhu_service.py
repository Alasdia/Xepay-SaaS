"""Alhu — assistant marchand intégré au tableau de bord Xepay (demandé
le 2026-11-27, première brique d'une architecture agent plus large
envisagée par l'utilisateur). Volontairement minimal pour ce premier
chantier :
- UN seul agent (pas de directeur + sous-agents, voir la discussion
  avec l'utilisateur - on commence petit, on scale seulement une fois
  l'approche prouvée).
- Presque exclusivement des outils de LECTURE (solde, transactions,
  statut Buildness, produit, Stripe Connect, workspace/permissions).
  3 exceptions qui écrivent :
  - change_member_role/remove_team_member : réservées au PROPRIÉTAIRE
    du workspace, HARDCODÉ (jamais la capacité "manage_team" réelle,
    personnalisable - ces 2 actions restent délibérément plus strictes
    que l'UI elle-même, demande du 2026-11-27 : "des outils spécifiques
    dont seul le owner du workspace peut demander à Alhu
    d'effectuer... certaines modifications concernant son equipe").
  - request_shopify_store : n'assigne/ne transfère RIEN (impossible via
    API Shopify, voir services/buildshop_service.py) - enregistre juste
    une demande + alerte un humain côté Xepay. Gatée par la VRAIE
    capacité de workspace "manage_shopify_integration" (donc
    personnalisable par le propriétaire, contrairement aux 2
    précédentes) : cohérent avec /shopify/store-request côté dashboard,
    qui utilise la même capacité.
  Les 3 sont gardées en défense en profondeur : jamais proposées au
  modèle si l'appelant n'y a pas droit (_build_tools), ET re-vérifiées
  indépendamment à l'exécution (_require_owner/_require_capability,
  jamais une confiance aveugle dans ce qui a été proposé), ET
  conditionnées à une confirmation explicite du marchand dans la
  conversation (voir ALHU_SYSTEM_PROMPT). change_member_role/
  remove_team_member sont en plus journalisées (log_security_event,
  libellé "(via Alhu)").
- Remplace routes/app.py (ancien stub OpenAI /ai/chat, jamais appelé par
  aucun frontend, supprimé le 2026-11-27) - clé/SDK différents
  (ANTHROPIC_API_KEY, pas OPENAI_API_KEY), jamais réutilisé.
"""

import logging
import os
import re

import stripe
from sqlalchemy.orm import Session

from backend.models import (
    BuildnessCompany,
    BuildnessCustomer,
    Profile,
    ShopifyStoreRequest,
    UserDB,
    Wallet,
    WalletTransaction,
    WorkspaceUser,
)
from backend.services import permission_service
from backend.services.email_service import send_shopify_store_request_internal_email
from backend.services.security_log_service import log_security_event

# Doit rester synchro avec ASSIGNABLE_ROLES (routes/users.py) - jamais
# "owner" (protégé, voir _require_owner/_change_member_role plus bas).
_ASSIGNABLE_ROLES = {"admin", "manager", "membre", "lecteur"}

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

Tu réponds à 6 types de questions, toujours via les outils fournis - jamais à partir de connaissances générales non vérifiées, et jamais en inventant une donnée ou une fonctionnalité :
1. Questions sur les DONNÉES PROPRES du marchand (solde, transactions, dossier de création de société/LLC) - outils get_balance/get_recent_transactions/get_buildness_status.
2. Questions sur LE PRODUIT Xepay lui-même (fonctionnalités, tarifs, fonctionnement du tableau de bord) - outils list_product_files/read_product_file, qui donnent accès en LECTURE SEULE aux pages marketing et à tout le code source du SPA (frontend/pages/*.html et frontend/pages/spa/). ATTENTION : les pages marketing (frontend/pages/accueil.html, tarif.html...) décrivent l'offre générale (plans Free/Pro/Business) mais PAS les fonctionnalités internes au tableau de bord (Buildness, Stripe Connect, Shopify...) - leur coût/fonctionnement réels sont codés en dur dans le SPA, jamais sur une page marketing. Pour le coût/processus de la formation de LLC spécifiquement, utilise TOUJOURS get_buildness_info (rapide, lit la bonne info directement) plutôt que read_product_file sur parametres.js en entier (40+ Ko, beaucoup trop lent et peu fiable sur ce fichier précis). Pour toute autre question précise sur une fonctionnalité du tableau de bord sans outil dédié, lis le fichier de vue correspondant dans frontend/pages/spa/views/ avec read_product_file avant de répondre - ne te contente jamais d'une recherche dans les pages marketing seules pour ce type de question, et si après une recherche réelle tu ne trouves toujours rien, dis-le explicitement plutôt que de deviner.
3. Questions sur l'ACTIVATION DU COMPTE STRIPE CONNECT du marchand - outil get_stripe_connect_status. Tous les marchands Xepay sont des fondateurs non-résidents ayant formé une LLC américaine (via Buildness/doola) pour pouvoir utiliser Stripe Connect. Tu peux expliquer en général les grandes étapes de cette activation (informations de l'entreprise, informations du représentant légal, coordonnées bancaires, documents de vérification d'identité) MAIS pour savoir précisément ce qu'IL reste à fournir à CE marchand, utilise TOUJOURS get_stripe_connect_status et base-toi sur ses champs currently_due/eventually_due_in_addition réels (déjà traduits en français, identiques à ce que voit le marchand dans Paramètres > Compte Stripe Connect > État du compte) - ne récite jamais une liste de documents par cœur, elle peut être fausse ou incomplète pour sa situation. Tu ne peux JAMAIS remplir ce formulaire à sa place (Stripe l'interdit structurellement, les champs KYC doivent venir directement du titulaire du compte) : ton rôle est de l'accompagner et de lui relayer clairement ce qui lui manque, pas de le compléter pour lui.
4. Questions sur LE WORKSPACE ou SON PROPRE RÔLE (n'importe quel membre) - outils get_workspace_info (identifiant/nom du workspace, son rôle, nombre de membres) et get_my_permissions (ce qu'il peut/ne peut pas faire, selon son rôle réel dans CE workspace, jamais une règle générique mémorisée).
5. Demandes de GESTION D'ÉQUIPE (list_team_members/change_member_role/remove_team_member) - outils réservés au PROPRIÉTAIRE du workspace, qui ne te sont même pas proposés si le marchand n'est pas owner ; si un non-owner demande ce genre d'action, dis simplement que c'est réservé au propriétaire, n'essaie jamais ces outils. change_member_role et remove_team_member MODIFIENT réellement l'équipe (contrairement à tout le reste, en lecture seule) : avant de les appeler, décris PRÉCISÉMENT l'action prévue (qui, quoi) et attends un message de confirmation explicite et sans ambiguïté du propriétaire (ex. "oui", "confirme") dans un tour de conversation SÉPARÉ - jamais dans la même réponse que la proposition, jamais sur une simple formulation ambiguë.
6. Demande d'une BOUTIQUE SHOPIFY "prête à l'emploi" (ex. "j'ai besoin d'une boutique Shopify") - outil request_shopify_store, proposé uniquement si le marchand a la capacité de gérer l'intégration Shopify dans ce workspace (variable selon le rôle et d'éventuelles personnalisations du propriétaire - si tu as un doute, vérifie avec get_my_permissions avant de proposer cet outil). ATTENTION, à expliquer clairement si demandé : cet outil N'ASSIGNE NI NE TRANSFÈRE AUCUNE boutique - aucune API Shopify ne permet d'automatiser la création d'un "Client Transfer Store" ni son transfert à un marchand (action Partner Dashboard purement manuelle). Il se contente d'enregistrer la demande et d'alerter l'équipe Xepay, qui assignera ensuite manuellement une boutique déjà préparée. Avant de l'appeler, confirme avec le marchand qu'il souhaite bien envoyer cette demande.

Règles strictes :
- En dehors des outils d'écriture explicitement prévus ci-dessus (gestion d'équipe - strictement réservée au owner, avec confirmation explicite obligatoire dans un tour séparé ; demande de boutique Shopify - réservée à qui peut gérer l'intégration Shopify dans ce workspace, avec confirmation avant envoi), tu ne peux RIEN modifier, créer ou annuler ailleurs : le reste n'est que LECTURE. Si le marchand demande une autre action (remboursement, modification Stripe/LLC, création), explique clairement que tu ne peux pas l'exécuter et indique où le faire dans le dashboard (ex. Paramètres > Entreprise pour une demande de correction LLC).
- Les outils produit ne donnent accès qu'au code FRONTEND (pages marketing + SPA) - jamais au code backend, à des secrets ou à des données d'autres marchands.
- Si une information demandée n'est couverte par aucun outil, dis-le explicitement plutôt que de deviner.
- Réponds en français, de façon concise et directe.
"""

_BASE_TOOLS = [
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
    {
        "name": "get_workspace_info",
        "description": "Renvoie l'identifiant et le nom du workspace actuel, le rôle du marchand dans CE workspace, et le nombre total de membres.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "get_my_permissions",
        "description": "Renvoie, pour le rôle RÉEL du marchand dans ce workspace, la liste des actions qu'il peut ou ne peut pas effectuer (ex. gérer l'équipe, retirer des fonds...). Toujours utiliser cet outil plutôt que de deviner les permissions d'un rôle - elles peuvent être personnalisées par le propriétaire pour ce workspace précis.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

# Réservés au PROPRIÉTAIRE du workspace (voir le docstring du module) -
# jamais inclus dans la liste d'outils envoyée au modèle pour un
# non-owner (_build_tools), et re-vérifiés indépendamment à
# l'exécution (_require_owner) même si cette offre était contournée.
_OWNER_ONLY_TOOLS = [
    {
        "name": "list_team_members",
        "description": "Liste tous les membres du workspace (email et rôle). Réservé au propriétaire du workspace.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "change_member_role",
        "description": "Change le rôle d'un membre du workspace (admin, manager, membre ou lecteur - jamais owner, protégé). Réservé au propriétaire. NE JAMAIS appeler sans avoir d'abord obtenu une confirmation explicite et sans ambiguïté du propriétaire dans un message séparé de la proposition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_email": {"type": "string", "description": "Email du membre à modifier."},
                "new_role": {"type": "string", "description": "Nouveau rôle : admin, manager, membre ou lecteur."},
            },
            "required": ["member_email", "new_role"],
        },
    },
    {
        "name": "remove_team_member",
        "description": "Retire définitivement un membre du workspace. Réservé au propriétaire. NE JAMAIS appeler sans avoir d'abord obtenu une confirmation explicite et sans ambiguïté du propriétaire dans un message séparé de la proposition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "member_email": {"type": "string", "description": "Email du membre à retirer."},
            },
            "required": ["member_email"],
        },
    },
]

# Outils gatés par une VRAIE capacité de workspace (jamais "owner" codé
# en dur comme _OWNER_ONLY_TOOLS ci-dessus) - chaque entrée est
# (définition d'outil, clé de capacité à vérifier via
# permission_service.get_effective_min_role, qui respecte les
# surcharges posées par le propriétaire pour SON workspace). _build_tools
# vérifie cette capacité AVANT de proposer l'outil au modèle ; chaque
# fonction d'exécution la re-vérifie quand même indépendamment
# (_require_capability), même principe de défense en profondeur que
# _OWNER_ONLY_TOOLS/_require_owner.
_CAPABILITY_GATED_TOOLS = [
    (
        {
            "name": "request_shopify_store",
            "description": "Enregistre une demande de boutique Shopify \"prête à l'emploi\" (Buildshop) et alerte l'équipe Xepay, qui assignera manuellement une boutique déjà préparée (AUCUNE boutique n'est créée, assignée ou transférée automatiquement par cet outil - impossible via l'API Shopify). Proposé uniquement si le marchand a la capacité de gérer l'intégration Shopify dans ce workspace. Toujours confirmer avec le marchand qu'il souhaite envoyer cette demande avant d'appeler cet outil.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "note": {"type": "string", "description": "Précisions optionnelles du marchand sur sa demande."},
                },
            },
        },
        "manage_shopify_integration",
    ),
]


def _build_tools(db: Session, workspace_id: str, caller_role: str, is_owner: bool) -> list[dict]:
    tools = list(_BASE_TOOLS)
    if is_owner:
        tools += _OWNER_ONLY_TOOLS
    for tool_def, capability_key in _CAPABILITY_GATED_TOOLS:
        min_role = permission_service.get_effective_min_role(db, workspace_id, capability_key)
        if permission_service.role_satisfies(caller_role, min_role):
            tools.append(tool_def)
    return tools


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


def _get_workspace_info(db: Session, workspace_id: str, caller_user_id: str) -> dict:
    owner = db.query(UserDB).filter(UserDB.id == workspace_id).first()
    # Même convention que get_my_workspaces (routes/users.py) : aucun nom
    # de workspace stocké en base, dérivé de l'email du propriétaire.
    workspace_name = f"{owner.email.split('@')[0]} Workspace" if owner else workspace_id
    membership = (
        db.query(WorkspaceUser)
        .filter(WorkspaceUser.workspace_id == workspace_id, WorkspaceUser.user_id == caller_user_id)
        .first()
    )
    member_count = db.query(WorkspaceUser).filter(WorkspaceUser.workspace_id == workspace_id).count()
    return {
        "workspace_id": workspace_id,
        "workspace_name": workspace_name,
        "my_role": membership.role if membership else None,
        "member_count": member_count,
    }


def _get_my_permissions(db: Session, workspace_id: str, caller_user_id: str) -> dict:
    membership = (
        db.query(WorkspaceUser)
        .filter(WorkspaceUser.workspace_id == workspace_id, WorkspaceUser.user_id == caller_user_id)
        .first()
    )
    if not membership:
        return {"error": "Vous n'appartenez pas à ce workspace."}
    # list_capabilities lit les surcharges propres à CE workspace - jamais
    # une table de rôles générique mémorisée par le modèle, qui serait
    # fausse dès qu'un propriétaire personnalise ses permissions.
    capabilities = permission_service.list_capabilities(db, workspace_id)
    return {
        "role": membership.role,
        "capabilities": [
            {
                "key": c["key"],
                "label": c["label"],
                "description": c["description"],
                "allowed": permission_service.role_satisfies(membership.role, c["current_role"]),
            }
            for c in capabilities
        ],
    }


def _require_owner(db: Session, workspace_id: str, caller_user_id: str) -> str | None:
    """Re-vérifie INDÉPENDAMMENT (nouvelle requête DB, jamais un
    booléen transmis par l'appelant) que caller_user_id est bien owner
    de workspace_id - appelé au tout début de chacun des 3 outils
    réservés au propriétaire, même s'ils ne sont déjà proposés au
    modèle que pour un owner (_build_tools) : défense en profondeur,
    jamais une confiance aveugle dans ce qui a été offert plus haut.
    Renvoie un message d'erreur si le caller n'est pas owner, None sinon."""
    membership = (
        db.query(WorkspaceUser)
        .filter(WorkspaceUser.workspace_id == workspace_id, WorkspaceUser.user_id == caller_user_id)
        .first()
    )
    if not membership or membership.role != "owner":
        return "Cette action est réservée au propriétaire du workspace."
    return None


def _require_capability(db: Session, workspace_id: str, caller_user_id: str, capability_key: str) -> str | None:
    """Équivalent de _require_owner, mais pour une VRAIE capacité de
    workspace (respecte les surcharges du propriétaire, via
    permission_service.get_effective_min_role) plutôt qu'un rôle
    "owner" figé - utilisé par request_shopify_store, pas par les
    outils de gestion d'équipe (délibérément plus stricts, voir
    _require_owner). Re-vérifie INDÉPENDAMMENT (nouvelle requête DB)
    même si l'outil n'a déjà été proposé au modèle que pour un
    appelant éligible (_build_tools) - même défense en profondeur."""
    membership = (
        db.query(WorkspaceUser)
        .filter(WorkspaceUser.workspace_id == workspace_id, WorkspaceUser.user_id == caller_user_id)
        .first()
    )
    if not membership:
        return "Vous n'appartenez pas à ce workspace."
    min_role = permission_service.get_effective_min_role(db, workspace_id, capability_key)
    if not permission_service.role_satisfies(membership.role, min_role):
        return "Permission insuffisante pour cette action dans ce workspace."
    return None


def _request_shopify_store(db: Session, workspace_id: str, caller_user_id: str, note: str | None) -> dict:
    """N'ASSIGNE NI NE TRANSFÈRE AUCUNE boutique (impossible via l'API
    Shopify, voir services/buildshop_service.py) - enregistre juste la
    demande et alerte un humain côté Xepay, même route/même email que
    POST /shopify/store-request (routes/shopify.py) : aucune distinction
    entre une demande faite depuis le dashboard ou depuis Alhu."""
    error = _require_capability(db, workspace_id, caller_user_id, "manage_shopify_integration")
    if error:
        return {"error": error}
    safe_note = (note or "").strip()[:1000] or None
    request_row = ShopifyStoreRequest(workspace_id=workspace_id, note=safe_note)
    db.add(request_row)
    db.commit()
    db.refresh(request_row)
    send_shopify_store_request_internal_email(workspace_id, safe_note)
    return {"success": True, "id": request_row.id, "status": request_row.status}


def _list_team_members(db: Session, workspace_id: str, caller_user_id: str) -> dict:
    error = _require_owner(db, workspace_id, caller_user_id)
    if error:
        return {"error": error}
    rows = db.query(WorkspaceUser).filter(WorkspaceUser.workspace_id == workspace_id).all()
    members = []
    for row in rows:
        user = db.query(UserDB).filter(UserDB.id == row.user_id).first()
        members.append({
            "email": user.email if user else None,
            "role": row.role,
            "is_owner": row.user_id == workspace_id,
        })
    return {"members": members}


def _find_member_by_email(db: Session, workspace_id: str, member_email: str):
    """Renvoie (user, membership) pour un email donné À L'INTÉRIEUR de
    ce workspace - jamais un UserDB résolu globalement par email, qui
    pourrait exister hors de ce workspace et laisserait modifier/
    retirer n'importe qui ailleurs sur la plateforme."""
    user = db.query(UserDB).filter(UserDB.email == member_email).first()
    if not user:
        return None, None
    membership = (
        db.query(WorkspaceUser)
        .filter(WorkspaceUser.workspace_id == workspace_id, WorkspaceUser.user_id == user.id)
        .first()
    )
    if not membership:
        return None, None
    return user, membership


def _change_member_role(db: Session, workspace_id: str, caller_user_id: str, member_email: str, new_role: str) -> dict:
    error = _require_owner(db, workspace_id, caller_user_id)
    if error:
        return {"error": error}
    new_role = (new_role or "").strip().lower()
    if new_role not in _ASSIGNABLE_ROLES:
        return {"error": f"Rôle invalide : {new_role}."}
    user, membership = _find_member_by_email(db, workspace_id, member_email)
    if not membership:
        return {"error": "Ce membre n'appartient pas à ce workspace."}
    if user.id == workspace_id:
        return {"error": "Impossible de modifier le rôle du propriétaire."}
    membership.role = new_role
    db.commit()
    log_security_event(
        db,
        caller_user_id,
        "member_role_changed",
        f"Rôle de {user.email} changé en {new_role.capitalize()} (via Alhu)",
        workspace_id=workspace_id,
    )
    return {"success": True, "email": user.email, "new_role": new_role}


def _remove_team_member(db: Session, workspace_id: str, caller_user_id: str, member_email: str) -> dict:
    error = _require_owner(db, workspace_id, caller_user_id)
    if error:
        return {"error": error}
    user, membership = _find_member_by_email(db, workspace_id, member_email)
    if not membership:
        return {"error": "Ce membre n'appartient pas à ce workspace."}
    if user.id == workspace_id:
        return {"error": "Impossible de retirer le propriétaire."}
    if user.id == caller_user_id:
        return {"error": "Vous ne pouvez pas vous retirer vous-même."}
    removed_email = user.email
    db.delete(membership)
    db.commit()
    log_security_event(
        db,
        caller_user_id,
        "member_removed",
        f"{removed_email} retiré de l'équipe (via Alhu)",
        workspace_id=workspace_id,
    )
    return {"success": True, "email": removed_email}


def _execute_tool(tool_name: str, tool_input: dict, db: Session, workspace_id: str, caller_user_id: str) -> dict:
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
    if tool_name == "get_workspace_info":
        return _get_workspace_info(db, workspace_id, caller_user_id)
    if tool_name == "get_my_permissions":
        return _get_my_permissions(db, workspace_id, caller_user_id)
    if tool_name == "list_team_members":
        return _list_team_members(db, workspace_id, caller_user_id)
    if tool_name == "change_member_role":
        return _change_member_role(db, workspace_id, caller_user_id, tool_input.get("member_email"), tool_input.get("new_role"))
    if tool_name == "remove_team_member":
        return _remove_team_member(db, workspace_id, caller_user_id, tool_input.get("member_email"))
    if tool_name == "request_shopify_store":
        return _request_shopify_store(db, workspace_id, caller_user_id, tool_input.get("note"))
    return {"error": f"Outil inconnu : {tool_name}"}


class AlhuNotConfiguredError(Exception):
    pass


# Libellés affichés côté client pendant l'exécution d'un outil (demande
# du 2026-11-27 : "le marchand doit voir et comprendre que la réflexion
# est en cours", pas juste un indicateur générique) - un par outil,
# plutôt qu'un message unique "Je réfléchis" qui ne dit rien de ce qui
# se passe réellement.
_TOOL_STATUS_LABELS = {
    "get_balance": "💰 Je consulte votre solde...",
    "get_recent_transactions": "📋 Je consulte vos transactions récentes...",
    "get_buildness_status": "🏢 Je vérifie le statut de votre dossier de création de société...",
    "get_stripe_connect_status": "🔐 Je vérifie votre compte Stripe Connect...",
    "get_buildness_info": "📖 Je consulte les informations sur la formation de LLC...",
    "list_product_files": "🔍 J'explore la documentation du produit...",
    "read_product_file": "📄 Je lis la documentation du produit...",
    "get_workspace_info": "🧭 Je consulte les informations du workspace...",
    "get_my_permissions": "🔑 Je vérifie vos permissions...",
    "list_team_members": "👥 Je consulte la liste de l'équipe...",
    "change_member_role": "✏️ Je modifie le rôle du membre...",
    "remove_team_member": "🚪 Je retire ce membre de l'équipe...",
    "request_shopify_store": "🛍️ J'envoie votre demande de boutique Shopify...",
}


def stream_alhu_chat(workspace_id: str, caller_user_id: str, caller_role: str, user_messages: list[dict]):
    """Générateur d'évènements ({"type": "status"|"delta"|"done"|"error", ...})
    pour streamer la réflexion/réponse d'Alhu en direct (demande du
    2026-11-27 : "le chat doit montrer au marchand qu'il est en train de
    réfléchir... les réponses défilent ligne par ligne... le marchand
    doit voir que la réflexion est en cours" pendant un appel d'outil) -
    remplace l'ancienne version bloquante (run_alhu_chat, qui renvoyait
    une seule string une fois tout terminé). user_messages : historique
    de la conversation côté client, déjà au format Anthropic, jamais
    persisté côté serveur (voir le commentaire d'en-tête) - le client
    renvoie tout l'historique à chaque appel.

    caller_role (ajouté le 2026-11-27, remplace l'ancien is_owner: bool) :
    le rôle RÉEL de l'appelant (membership.role), nécessaire pour
    évaluer à la fois l'accès owner-only (gestion d'équipe) ET une
    VRAIE capacité de workspace personnalisable (request_shopify_store,
    voir _CAPABILITY_GATED_TOOLS/_build_tools) - un simple booléen
    is_owner ne suffisait plus pour ce 2e cas.

    Ouvre SA PROPRE session DB (jamais Depends(get_db)) - même raison
    que _apply_doola_event (webhook/doola.py) : get_db() ferme sa
    session dans un finally dès que la fonction de route RETOURNE, ce
    qui arrive dès que StreamingResponse reçoit ce générateur, PAS une
    fois le flux entièrement consommé - réutiliser la session de la
    requête planterait sur le 1er appel d'outil après le tout premier
    yield."""
    if not ANTHROPIC_API_KEY:
        raise AlhuNotConfiguredError("ANTHROPIC_API_KEY non configurée")

    # Import différé (démarrage du serveur ne doit jamais échouer si le
    # SDK est absent/la clé manquante - même raison que get_doola_service
    # dans doola_client.py, pattern déjà établi dans ce projet).
    import anthropic
    from backend.database import SessionLocal

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    messages = list(user_messages)
    full_text_parts = []
    db = SessionLocal()
    # Figée UNE SEULE FOIS ici, au tout début de la conversation - jamais
    # recalculée à partir d'une entrée du modèle : c'est elle qui décide
    # quels outils sont même proposés à Claude pour tout ce tour (voir
    # _build_tools), et chaque outil réservé re-vérifie quand même
    # indépendamment (_require_owner/_require_capability).
    tools = _build_tools(db, workspace_id, caller_role, caller_role == "owner")

    try:
        yield from _stream_alhu_rounds(client, db, workspace_id, caller_user_id, tools, messages, full_text_parts)
    finally:
        db.close()


def _stream_alhu_rounds(client, db, workspace_id, caller_user_id, tools, messages, full_text_parts):
    for _ in range(MAX_TOOL_ROUNDS):
        with client.messages.stream(
            model=ALHU_MODEL,
            max_tokens=1024,
            system=ALHU_SYSTEM_PROMPT,
            tools=tools,
            messages=messages,
        ) as stream:
            for event in stream:
                if event.type == "content_block_start" and event.content_block.type == "tool_use":
                    label = _TOOL_STATUS_LABELS.get(event.content_block.name, "🔎 Je recherche...")
                    yield {"type": "status", "text": label}
                elif event.type == "content_block_delta" and event.delta.type == "text_delta":
                    full_text_parts.append(event.delta.text)
                    yield {"type": "delta", "text": event.delta.text}
            response = stream.get_final_message()

        if response.stop_reason != "tool_use":
            yield {"type": "done", "reply": "".join(full_text_parts)}
            return

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            try:
                result = _execute_tool(block.name, block.input or {}, db, workspace_id, caller_user_id)
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
    yield {
        "type": "done",
        "reply": "Désolé, je n'ai pas pu finaliser ma réponse. Réessayez en reformulant votre question.",
    }
