"""Mock local de doola_service.py (voir doola_client.get_doola_service) -
aucun appel réseau, retourne des IDs factices mais plausibles. Les clés
sandbox doola (dk_test_...) sont désormais configurées sur le serveur AWS
(2026-11-23), mais ce mock reste utile pour développer/tester tout le flux
Buildness (onboard + webhook) en LOCAL sans dépendre du réseau ni risquer
le moindre appel réel, via BUILDNESS_ALLOW_MOCK=true (jamais en
production, voir doola_client.py).

Mêmes signatures d'appel que doola_service.py (create_customer,
create_company, get_company_status) - PAS d'héritage formel depuis une
classe commune : côté réel, ce sont des fonctions module-level (voir
doola_service.py), pas une classe, donc il n'y a littéralement rien à
hériter. Le duck typing suffit ici - routes/buildness.py appelle
`service.create_customer(...)` de façon identique, que `service` soit ce
mock ou le module doola_service réel (voir doola_client.py)."""

import asyncio
import uuid


class MockDoolaService:
    async def create_customer(self, payload: dict) -> str:
        await asyncio.sleep(0)
        return f"mock_cus_{uuid.uuid4().hex[:12]}"

    async def create_company(self, customer_id: str, payload: dict) -> dict:
        await asyncio.sleep(0)
        return {
            "doolaCompanyId": f"mock_co_{uuid.uuid4().hex[:12]}",
            "status": "submitted",
        }

    async def get_company_status(self, company_id: str) -> dict:
        await asyncio.sleep(0)
        # Forme alignée sur une vraie réponse sandbox inspectée en direct
        # le 2026-11-24 (voir doola_service.py) - "ein"/"registeredAgent"/
        # "addresses"/"responsibleParty" sont les vrais noms de champs,
        # pour que le recap "Mon entreprise" soit testable sans clé réelle.
        return {
            "doolaCompanyId": company_id,
            "status": "processing",
            "ein": "99-9999999",
            "formationFilingNumber": "MOCK-FILING-0001",
            "legalName": "Mock Test LLC",
            "responsibleParty": {
                "legalFirstName": "Jean",
                "legalLastName": "Dupont",
                "email": "jean.dupont@example.com",
                "address": {"line1": "12 rue de la Paix", "city": "Paris", "state": "Ile-de-France", "postalCode": "75002", "country": "FRA", "phone": "+33612345678"},
            },
            "addresses": [
                {"provider": "customer", "type": "mailing", "address": {"line1": "12 rue de la Paix", "city": "Paris", "state": "Ile-de-France", "postalCode": "75002", "country": "FRA"}},
                {"provider": "registeredAgent", "type": "business", "address": {"line1": "30 N Gould St", "line2": "STE R", "city": "Sheridan", "state": "WYOMING", "postalCode": "82801", "country": "USA"}},
            ],
            "registeredAgent": {"name": "Mock Registered Agents, Inc.", "address": {"line1": "30 N Gould St", "line2": "STE R", "city": "Sheridan", "state": "WY", "postalCode": "82801", "country": "USA"}},
        }

    async def list_documents(self, company_id: str) -> list[dict]:
        await asyncio.sleep(0)
        # NON VÉRIFIÉ sur un vrai document (voir doola_service.py) - forme
        # plausible pour tester le rendu de la liste sans clé réelle.
        return [{"documentId": "mock_doc_1", "name": "Articles of Organization", "type": "AOO", "createdAt": "2026-11-24T10:00:00Z"}]

    async def get_document(self, company_id: str, document_id: str) -> dict:
        await asyncio.sleep(0)
        return {"documentId": document_id, "name": "Articles of Organization", "downloadUrl": "https://example.invalid/mock-document.pdf"}

    async def list_naics_codes(self) -> list[dict]:
        await asyncio.sleep(0)
        # Mêmes clés que la vraie réponse doola (confirmée en direct le
        # 2026-11-23) - une seule entrée suffit pour tester le flux
        # localement sans dépendre du réseau.
        return [{"industry": "Data processing", "naicsCode": "518210", "naicsCodeId": "mock_naics_1"}]

    async def list_countries(self) -> list[dict]:
        await asyncio.sleep(0)
        return [{"code": "FRA", "name": "France"}, {"code": "USA", "name": "United States"}]
