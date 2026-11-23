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
        # "ein" (pas "einNumber") : nom de champ réel confirmé dans la doc
        # officielle doola le 2026-11-23 (voir webhook/doola.py,
        # company_ein_issued) - le mock doit refléter la vraie forme de
        # réponse pour que le flux EIN soit testable sans clé réelle.
        return {"doolaCompanyId": company_id, "status": "processing", "ein": "99-9999999"}

    async def list_naics_codes(self) -> list[dict]:
        await asyncio.sleep(0)
        # Mêmes clés que la vraie réponse doola (confirmée en direct le
        # 2026-11-23) - une seule entrée suffit pour tester le flux
        # localement sans dépendre du réseau.
        return [{"industry": "Data processing", "naicsCode": "518210", "naicsCodeId": "mock_naics_1"}]

    async def list_countries(self) -> list[dict]:
        await asyncio.sleep(0)
        return [{"code": "FRA", "name": "France"}, {"code": "USA", "name": "United States"}]
