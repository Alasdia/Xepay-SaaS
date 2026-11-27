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

from sqlalchemy.orm import Session

from backend.models import BuildnessCompany, BuildnessCustomer, Wallet, WalletTransaction

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ALHU_MODEL = os.getenv("ALHU_MODEL", "claude-sonnet-5")

# Boucle outil/réponse bornée (demande normale : plusieurs outils en
# chaîne, ex. solde PUIS transactions) - jamais illimitée, au cas où le
# modèle boucle sur un appel d'outil sans jamais conclure.
MAX_TOOL_ROUNDS = 5

ALHU_SYSTEM_PROMPT = """Tu es Alhu, l'assistant intégré au tableau de bord Xepay (plateforme de paiement pour marchands).

Tu réponds UNIQUEMENT aux questions du marchand sur SES PROPRES données (solde, transactions, dossier de création de société/LLC) via les outils fournis - jamais à partir de connaissances générales non vérifiées, et jamais en inventant une donnée.

Règles strictes :
- Tu ne peux RIEN modifier, créer ou annuler : tu n'as accès qu'à des outils de LECTURE. Si le marchand demande une action (remboursement, modification, création), explique clairement que tu ne peux pas l'exécuter et indique où le faire dans le dashboard (ex. Paramètres > Entreprise pour une demande de correction LLC).
- Si une information demandée n'est pas couverte par tes outils, dis-le explicitement plutôt que de deviner.
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


def _execute_tool(tool_name: str, tool_input: dict, db: Session, workspace_id: str) -> dict:
    if tool_name == "get_balance":
        return _get_balance(db, workspace_id)
    if tool_name == "get_recent_transactions":
        return _get_recent_transactions(db, workspace_id, tool_input.get("limit"))
    if tool_name == "get_buildness_status":
        return _get_buildness_status(db, workspace_id)
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
