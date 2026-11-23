"""Pont doola pour Buildness (formation de LLC US + obtention de l'EIN pour
un marchand non-résident, voir routes/buildness.py, routes/webhook/doola.py,
BuildnessCustomer/BuildnessCompany dans models.py) - prérequis à l'activation
du compte Stripe Connect du marchand.

VÉRIFIÉ le 2026-11-23 contre la vraie documentation officielle
(docs.doola.com/api) suite à la réception des clés sandbox :
- Base URL sandbox (https://api.test.doola.com) : CONFIRMÉE.
- Chemins /v1/partner/customers, /v1/partner/companies,
  /v1/partner/companies/{id} (GET) : CONFIRMÉS.
- Header Idempotency-Key sur les POST : CONFIRMÉ.
- doolaCustomerId/doolaCompanyId comme clés d'ID en réponse : CONFIRMÉS.
- Header d'authentification : FAUX avant ce correctif - la doc dit
  explicitement "Authenticate with the raw API key in the Authorization
  header. Never add a Bearer prefix." (voir _headers ci-dessous, corrigé).

RESTE NON RÉSOLU (nécessite une décision produit, pas juste un correctif
technique - voir le rapport livré à l'utilisateur le 2026-11-23) :
create_customer n'envoie pas countryOfResidence (requis par la vraie API)
et create_company n'envoie ni nameOptions/industry/description/
responsibleParty/addresses/members (tous requis pour une LLC réelle) -
BuildnessOnboardRequest (models.py) ne collecte aujourd'hui qu'un
sous-ensemble (email/nom/prénom/company_name/state). Un vrai appel
sandbox à create_company échouera donc en validation (400) tant que le
formulaire d'onboarding n'aura pas été étendu - hors périmètre de cette
vérification (changement de formulaire/UI, pas un bug de câblage).

Client HTTP asynchrone (httpx.AsyncClient) - les deux endpoints
d'onboarding (routes/buildness.py) sont eux-mêmes async, contrairement aux
routes Verto/Stripe existantes (requests, synchrones) : Buildness n'a pas
leur contrainte historique, donc pas de raison de bloquer l'event loop
FastAPI ici."""

import asyncio
import logging
import os
import uuid

import httpx

logger = logging.getLogger(__name__)

DOOLA_API_KEY = os.getenv("DOOLA_API_KEY")
DOOLA_BASE_URL = os.getenv("DOOLA_BASE_URL", "https://api.test.doola.com")
DOOLA_TIMEOUT_SECONDS = 10

# Nombre total de TENTATIVES (pas de retries en plus de la première) - un
# appel qui échoue au 1er essai est donc retenté au plus 2 fois.
DOOLA_MAX_ATTEMPTS = 3
# Backoff exponentiel : 1s avant la 2e tentative, 2s avant la 3e.
DOOLA_RETRY_BASE_DELAY_SECONDS = 1

# Longueur max du corps de réponse loggé avant retry/échec final - jamais
# le corps brut en entier (pourrait contenir des données personnelles du
# fondateur/la société), juste assez pour diagnostiquer en prod.
_LOGGED_BODY_MAX_CHARS = 500


class DoolaAPIError(RuntimeError):
    """Erreur doola non retentée avec succès (ou non retentable - 4xx) -
    porte le status_code et le corps de réponse brut pour que l'appelant
    (routes/buildness.py) puisse distinguer un problème de validation (400)
    d'une vraie panne (5xx épuisé après DOOLA_MAX_ATTEMPTS tentatives)."""

    def __init__(self, status_code: int | None, body: str):
        self.status_code = status_code
        self.body = body
        super().__init__(f"doola a répondu {status_code}: {body[:_LOGGED_BODY_MAX_CHARS]}")


def _headers(idempotency_key: str | None) -> dict:
    # Clé brute, SANS préfixe "Bearer " - la doc officielle doola l'exige
    # explicitement ("Never add a Bearer prefix"), contrairement au
    # schéma Bearer standard utilisé par Stripe/Verto dans ce même
    # backend. Corrigé le 2026-11-23 après vérification contre
    # docs.doola.com/api - l'ancien header "Bearer {clé}" aurait fait
    # échouer TOUT appel réel en 401, jamais détecté avant faute de
    # vraies clés sandbox.
    headers = {
        "Authorization": DOOLA_API_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Idempotency-Key uniquement pour les requêtes avec corps (POST) - voir
    # le cahier des charges, section 2. Absent pour un GET, qui n'a rien à
    # dédupliquer côté doola.
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict | None = None,
    idempotent: bool = False,
) -> dict:
    """Coeur des appels doola : retry avec backoff exponentiel sur erreur
    réseau (timeout/connexion) ou 5xx UNIQUEMENT - jamais sur un 4xx (une
    requête malformée ou refusée ne devient pas valide en la retentant,
    et masquerait une vraie erreur de validation derrière un message
    générique "échec après 3 tentatives").

    idempotent=True (POST) : UNE SEULE Idempotency-Key générée avant la
    boucle, réutilisée à l'IDENTIQUE sur chaque tentative de CETTE même
    requête logique - jamais une nouvelle par tentative. C'est l'inverse
    qui casserait la garantie : si la 1re tentative a timeout côté client
    mais a en fait été reçue et traitée par doola, la 2e tentative avec
    une clé différente créerait un second customer/company en double
    côté doola. Avec la même clé, doola (si son implémentation suit la
    convention standard du header Idempotency-Key - voir NON VÉRIFIÉ en
    tête de fichier) reconnaît la requête déjà traitée et renvoie le
    résultat original au lieu de la rejouer."""
    idempotency_key = str(uuid.uuid4()) if idempotent else None
    url = f"{DOOLA_BASE_URL}{path}"

    last_error: Exception | None = None
    for attempt in range(1, DOOLA_MAX_ATTEMPTS + 1):
        try:
            async with httpx.AsyncClient(timeout=DOOLA_TIMEOUT_SECONDS) as client:
                response = await client.request(
                    method,
                    url,
                    json=json_body,
                    headers=_headers(idempotency_key),
                )
        except (httpx.TimeoutException, httpx.TransportError) as e:
            last_error = e
            logger.warning(
                "doola %s %s : erreur réseau à la tentative %d/%d (%s)",
                method, path, attempt, DOOLA_MAX_ATTEMPTS, e,
            )
            if attempt == DOOLA_MAX_ATTEMPTS:
                raise DoolaAPIError(None, str(e)) from e
            await asyncio.sleep(DOOLA_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))
            continue

        if 200 <= response.status_code < 300:
            if not response.content:
                return {}
            data = response.json()
            # Enveloppe universelle doola : {"error": null, "payload": ...}
            # - jamais documentée explicitement dans la doc officielle,
            # découverte le 2026-11-23 en inspectant de vraies réponses
            # sandbox (/v1/partner/companies, /v1/partner/references/*).
            # Sans ce déballage, create_customer/create_company/
            # get_company_status lisaient data["doolaCustomerId"] etc. à
            # la racine - toujours absent, KeyError à chaque appel réel.
            if isinstance(data, dict) and "payload" in data and "error" in data:
                return data["payload"]
            return data

        body_snippet = response.text[:_LOGGED_BODY_MAX_CHARS]

        if response.status_code < 500:
            # 4xx : jamais retenté - voir le docstring. Authorization n'est
            # jamais inclus dans ce message (seul le status/corps doola le
            # sont), ni ici ni dans logger.warning ci-dessous.
            logger.warning(
                "doola %s %s : %d non retentable - %s",
                method, path, response.status_code, body_snippet,
            )
            raise DoolaAPIError(response.status_code, response.text)

        logger.warning(
            "doola %s %s : %d à la tentative %d/%d - %s",
            method, path, response.status_code, attempt, DOOLA_MAX_ATTEMPTS, body_snippet,
        )
        last_error = DoolaAPIError(response.status_code, response.text)
        if attempt == DOOLA_MAX_ATTEMPTS:
            raise last_error
        await asyncio.sleep(DOOLA_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1)))

    # Inatteignable (la boucle lève ou retourne toujours avant la fin) -
    # garde-fou pour satisfaire le type checker, jamais censé s'exécuter.
    raise last_error or DoolaAPIError(None, "Échec doola sans détail")


async def create_customer(payload: dict) -> str:
    """POST /v1/partner/customers - crée le "customer" doola (fondateur)
    correspondant à un marchand Xepay. Retourne doolaCustomerId (voir
    BuildnessCustomer.doola_customer_id)."""
    data = await _request("POST", "/v1/partner/customers", json_body=payload, idempotent=True)
    return data["doolaCustomerId"]


async def create_company(customer_id: str, payload: dict) -> dict:
    """POST /v1/partner/companies - crée la LLC pour un customer déjà créé
    (create_customer). entityType="LLC" est forcé ici (jamais passé par
    l'appelant) : Buildness ne forme QUE des LLC, aucune autre forme
    juridique n'est un cas d'usage actuel - un payload qui tenterait de le
    surcharger serait silencieusement ignoré, donc autant ne pas exposer
    le paramètre du tout. doolaCustomerId (pas "customerId", corrigé le
    2026-11-23 après vérification contre la vraie doc) - le payload
    complet (nameOptions/industry/description/responsibleParty/
    addresses/members/services) est construit par l'appelant, voir
    routes/buildness.py. Retourne la réponse brute doola (contient au
    minimum doolaCompanyId et le statut initial)."""
    body = {**payload, "doolaCustomerId": customer_id, "entityType": "LLC"}
    return await _request("POST", "/v1/partner/companies", json_body=body, idempotent=True)


async def get_company_status(company_id: str) -> dict:
    """GET /v1/partner/companies/{company_id} - vérification manuelle de
    l'état d'une company, pour un rattrapage si un webhook (routes/
    webhook/doola.py) a été manqué/jamais livré. Jamais appelé en boucle
    de polling automatique ici - à l'appelant de décider quand (voir
    GET /buildness/status)."""
    return await _request("GET", f"/v1/partner/companies/{company_id}")


async def list_naics_codes() -> list[dict]:
    """GET /v1/partner/references/naics-codes - secteurs d'activité
    acceptés par create_company. Le champ "industry" de chaque entrée doit
    être renvoyé VERBATIM dans create_company (jamais du texte libre,
    rejeté par doola) - voir GET /buildness/naics-codes (routes/
    buildness.py), qui expose cette liste pour peupler un menu déroulant
    côté UI plutôt que de laisser le marchand taper n'importe quoi.
    _request() déballe déjà l'enveloppe {"error","payload"} - renvoie
    directement la liste."""
    return await _request("GET", "/v1/partner/references/naics-codes")


async def list_countries() -> list[dict]:
    """GET /v1/partner/references/countries - pays acceptés pour
    countryOfResidence (create_customer) et le pays des adresses
    (PartnerAddressDto.country, create_company) - mêmes codes ISO
    3166-1 alpha-3 pour les deux usages chez doola. Même déballage
    d'enveloppe automatique que list_naics_codes."""
    return await _request("GET", "/v1/partner/references/countries")
