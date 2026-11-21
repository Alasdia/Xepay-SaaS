"""Mock local de doola_service.py (voir doola_client.get_doola_service) -
aucun appel réseau, retourne des IDs factices mais plausibles. Nécessaire
tant que les clés sandbox doola (dk_test_...) n'ont pas été reçues
(demandées le 2026-11-21, voir conversation du même jour) : permet de
développer/tester tout le flux Buildness (onboard + webhook) en local dès
aujourd'hui.

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
        return {"doolaCompanyId": company_id, "status": "processing"}
