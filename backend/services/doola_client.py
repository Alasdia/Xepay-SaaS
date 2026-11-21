"""Sélecteur Mock/réel pour Buildness (voir doola_service.py, doola_mock_
service.py, routes/buildness.py) - un seul point de décision, jamais
dupliqué dans chaque route.

CORRIGÉ le 2026-11-22, avant premier déploiement en prod : la version
initiale basculait AUTOMATIQUEMENT sur le mock dès que DOOLA_API_KEY était
absente, sans distinction d'environnement - correct pour développer en
local (c'était le but), mais dangereux tel quel en production : un
déploiement sans les vraies clés (pas encore reçues de doola, voir
conversation du 2026-11-21) aurait silencieusement formé de FAUSSES LLC
(IDs mock_*, jamais de vraie société derrière) pour de VRAIS marchands,
sans qu'ils le sachent. BUILDNESS_ALLOW_MOCK (false par défaut - même
discipline que VERTO_ENABLED, verto_service.py) exige maintenant un choix
explicite : à positionner à true UNIQUEMENT dans un .env de développement/
test local, jamais en production. Sans clé réelle ET sans ce flag, le
service est considéré indisponible (voir DoolaNotConfiguredError) plutôt
que de deviner."""

import os

from backend.services import doola_service
from backend.services.doola_mock_service import MockDoolaService

BUILDNESS_ALLOW_MOCK = os.getenv("BUILDNESS_ALLOW_MOCK", "false").lower() == "true"


class DoolaNotConfiguredError(RuntimeError):
    """DOOLA_API_KEY absente/vide et BUILDNESS_ALLOW_MOCK désactivé - voir
    routes/buildness.py, qui traduit ceci en 503 (service pas encore
    configuré) plutôt que de laisser un appel HTTP partir vers doola avec
    une clé vide/absente et échouer plus bas de façon confuse."""


def _has_real_key() -> bool:
    key = doola_service.DOOLA_API_KEY
    return bool(key) and not key.startswith("mock_")


def get_doola_service():
    """Renvoie le service réel (si une vraie clé dk_test_/dk_live_ est
    configurée - toujours prioritaire, peu importe BUILDNESS_ALLOW_MOCK),
    sinon MockDoolaService() si explicitement autorisé, sinon lève
    DoolaNotConfiguredError. Les trois exposent/attendent la même
    signature d'appel (create_customer/create_company/get_company_status
    - voir le docstring de doola_mock_service.py)."""
    if _has_real_key():
        return doola_service
    if BUILDNESS_ALLOW_MOCK:
        return MockDoolaService()
    raise DoolaNotConfiguredError(
        "DOOLA_API_KEY absente et BUILDNESS_ALLOW_MOCK désactivé - Buildness indisponible."
    )
