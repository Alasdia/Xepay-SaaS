"""Commission Xepay dégressive par volume mensuel.

Contexte produit (décision prise en conversation le 2026-10-25, avant tout
lancement commercial - voir le fil "modèle économique" de cette période) :
un taux fixe de 6% traite un marchand qui encaisse 200€/mois exactement
comme un marchand qui en encaisse 200 000€/mois, alors que le coût marginal
de Xepay pour traiter un gros volume est quasi nul une fois l'infrastructure
en place. Le barème ci-dessous récompense la croissance : plus un marchand
encaisse dans le mois, plus son taux baisse - par PALIER (comme les
tranches d'impôt), jamais par seuil-cliquet : seuls les euros au-dessus
d'un palier profitent du taux de ce palier, pas la totalité du mois
rétroactivement.

Pourquoi des seuils hauts et "ronds" (5 000 / 20 000 / 75 000) plutôt qu'une
optimisation fine : au moment où ce barème est écrit, Xepay n'a encore AUCUN
marchand réel (phase de pré-lancement) - il n'existe donc aucune donnée de
distribution de volume pour calibrer un seuil "optimal". Des seuils hauts et
volontairement conservateurs limitent l'exposition de marge pendant que les
premières données réelles s'accumulent, tout en permettant d'afficher la
grille dégressive comme argument commercial dès le lancement (plutôt que
d'attendre d'avoir des données, au risque qu'un concurrent affiche cet
argument en premier).

RÈGLE DE NON-RÉGRESSION (impérative pour toute révision future de
COMMISSION_TIERS) : une révision ne peut QUE baisser un taux existant, ou
baisser le seuil nécessaire pour l'atteindre - jamais remonter un taux ou un
seuil déjà publié. Casser cette règle reprendrait un avantage déjà annoncé à
des marchands déjà acquis, ce qui ressemble à un retour en arrière même si
l'intention est de corriger une estimation initiale mal calibrée. Si le
barème s'avère mal calibré à l'usage, on AJOUTE un palier plus généreux, on
ne retire/dégrade jamais un palier existant.

Fenêtre de calcul : mois calendaire en cours (1er au dernier jour du mois,
UTC) - la MÊME fenêtre que les compteurs de plan déjà en place
(paid_count/links_used, voir backend/routes/lien.py et
GET /me/plan dans backend/routes/users.py), pour rester cohérent avec le
reste de l'app plutôt que d'introduire une deuxième notion de "mois".

Mécanique de calcul par transaction, PAS de recalcul rétroactif en fin de
mois : au moment de chaque nouveau paiement, on regarde le volume déjà
encaissé par ce workspace depuis le début du mois en cours (AVANT cette
transaction - ne jamais appeler resolve_commission_rate/
compute_application_fee_cents APRÈS avoir enregistré la transaction dont on
calcule la commission, sous peine qu'elle se compte elle-même), on en
déduit le palier, et on applique le taux de ce palier à la TOTALITÉ de cette
transaction. Une transaction qui chevauche deux paliers reste donc au taux
du palier où elle démarre - imprécision mineure et délibérément acceptée :
Stripe ne permet pas de scinder un seul application_fee_amount/
application_fee_percent en deux taux au sein d'une même transaction.

Limite connue sur la devise : les seuils de COMMISSION_TIERS sont en USD
(cohérent avec Payment.amount pour un paiement par lien, TOUJOURS normalisé
en USD par process_checkout_session_payment, quelle que soit la devise
d'origine du lien - voir backend/routes/webhook/paiement.py). Les factures
et abonnements marchands, eux, gardent Payment.amount dans leur devise
Stripe d'origine (jamais normalisés, voir process_invoice_paid_event dans
backend/routes/webhook/stripe.py) - workspace_volume_this_month ne somme
donc QUE les paiements effectivement en USD (Payment.currency == "USD",
voir plus bas), pour ne jamais additionner des devises différentes sans
taux de change. Une facture/un abonnement en EUR ne contribue donc PAS
encore au volume mensuel (sous-estimation, jamais une addition erronée) -
à corriger par une vraie conversion si des marchands facturent
significativement hors USD.

Limite connue sur les abonnements marchands (factures récurrentes qu'un
marchand envoie à SES propres clients, voir create_merchant_subscription
dans backend/routes/webhook/stripe.py) : Stripe fixe
application_fee_percent une seule fois à la création de la Subscription et
l'applique identique à CHAQUE facture générée automatiquement par la suite
- il n'existe pas de hook natif pour recalculer ce taux à chaque cycle sans
logique webhook supplémentaire (intercepter invoice.created avant son
auto-finalisation, fenêtre d'environ 1h par défaut chez Stripe). Ce module
résout donc le taux UNE SEULE FOIS pour ce flux, au moment de la création
de l'abonnement, sur le volume du marchand à cet instant précis - le taux
reste ensuite figé pour toute la durée de vie de CET abonnement (jamais
recalculé à chaque renouvellement). C'est une simplification volontaire,
documentée ici pour ne pas être prise pour un oubli - une vraie
réévaluation par cycle demanderait un chantier séparé (webhook
invoice.created + Invoice.modify avant finalisation).
"""

import calendar
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models import Payment

# Paliers de commission dégressive, par volume ENCAISSÉ dans le mois
# calendaire en cours (montant en unité principale - euros/dollars, pas en
# centimes). Lire "à partir de X" : le taux s'applique à la tranche
# [X, seuil suivant[. Doit rester trié par seuil croissant.
#
# Voir la RÈGLE DE NON-RÉGRESSION dans le docstring du module avant de
# modifier une seule de ces valeurs.
COMMISSION_TIERS: list[tuple[Decimal, Decimal]] = [
    (Decimal("0"), Decimal("0.06")),
    (Decimal("5000"), Decimal("0.05")),
    (Decimal("20000"), Decimal("0.04")),
    (Decimal("75000"), Decimal("0.03")),
]

# Taux par défaut/historique (palier 0) - utilisé comme repli si jamais
# COMMISSION_TIERS était vide ou mal formé, pour ne jamais lever d'erreur
# sur le chemin critique de la création d'un paiement.
DEFAULT_COMMISSION_RATE = COMMISSION_TIERS[0][1]


def _month_bounds(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Bornes [début, fin] du mois calendaire UTC contenant `now` (ou
    maintenant si omis). Même découpage que les compteurs de plan
    existants (voir docstring du module)."""
    now = now or datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(now.year, now.month)[1]
    end = start.replace(day=last_day, hour=23, minute=59, second=59, microsecond=999999)
    return start, end


def workspace_volume_this_month(db: Session, workspace_id: str, now: datetime | None = None) -> Decimal:
    """Volume déjà encaissé (paiements réussis uniquement) par ce workspace
    depuis le début du mois calendaire en cours, TOUTES sources confondues
    (liens, factures ponctuelles, abonnements marchands) - voir
    Payment.user_id, posé au marchand dans les 3 flux (process_
    checkout_session_payment pour les liens, process_invoice_paid_event
    pour les factures/abonnements), jamais au client. Filtrer sur
    Payment.user_id directement, PAS en passant par un join sur Link :
    les factures/abonnements n'ont pas de link_id (Payment.link_id est
    NULL pour eux) - un join sur Link les exclurait silencieusement du
    volume, faussant le palier de TOUTES les commissions de ce marchand à
    la baisse (constaté : une facture ne poussait jamais vers un palier
    inférieur, pas même pour elle-même sur un renouvellement suivant).

    À appeler AVANT d'enregistrer la transaction dont on calcule la
    commission - voir le docstring du module, sinon cette transaction se
    compterait elle-même.

    Même filtre de statut que le plafond de plan déjà en place (voir
    paid_count dans backend/routes/lien.py) : ["paid", "success"].

    Filtré sur Payment.currency == "USD" - voir la limite documentée dans
    le docstring du module : une facture/un abonnement en EUR n'est pas
    encore normalisé en USD, et serait sommé à tort (pas "en moins", "en
    plus" sans aucun taux de change) si on l'incluait tel quel."""
    start, end = _month_bounds(now)
    total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.user_id == workspace_id)
        .filter(Payment.currency == "USD")
        .filter(Payment.status.in_(["paid", "success"]))
        .filter(Payment.created_at >= start)
        .filter(Payment.created_at <= end)
        .scalar()
    )
    return Decimal(str(total or 0))


def resolve_commission_rate(db: Session, workspace_id: str, now: datetime | None = None) -> Decimal:
    """Taux de commission applicable à la PROCHAINE transaction de ce
    workspace, d'après le palier déjà atteint par son volume encaissé ce
    mois (voir COMMISSION_TIERS ci-dessus)."""
    volume = workspace_volume_this_month(db, workspace_id, now=now)
    rate = DEFAULT_COMMISSION_RATE
    for threshold, tier_rate in COMMISSION_TIERS:
        if volume >= threshold:
            rate = tier_rate
        else:
            break
    return rate


def compute_application_fee_cents(db: Session, workspace_id: str, amount_cents: int, now: datetime | None = None) -> int:
    """Commission (en centimes) à poser comme application_fee_amount pour
    une transaction de `amount_cents` centimes émise par ce workspace.
    Résout le taux AVANT tout enregistrement de cette transaction (voir
    resolve_commission_rate)."""
    rate = resolve_commission_rate(db, workspace_id, now=now)
    return int(Decimal(amount_cents) * rate)


def commission_tiers_public() -> list[dict]:
    """Représentation JSON-friendly du barème, pour les endpoints exposant
    la grille aux marchands (page tarifs, section Plans et frais) - évite
    de dupliquer les seuils/taux en dur côté frontend."""
    return [
        {"from": float(threshold), "rate": float(rate)}
        for threshold, rate in COMMISSION_TIERS
    ]
