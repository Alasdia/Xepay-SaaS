"""rename bildbus_* tables to buildness_*

Renommage produit BildBus -> Buildness (2026-11-22) - renomme les 3
tables et l'index explicitement nommé. Les FK existantes (bildbus_
companies.customer_id -> bildbus_customers.id) survivent au renommage
(Postgres les référence par OID de relation, pas par nom) - rien à
recréer. Les contraintes UNIQUE auto-nommées par Postgres à la création
(ex. bildbus_customers_xepay_merchant_id_key) ne sont PAS renommées ici :
purement internes/jamais consultées ailleurs dans le code, le risque de
deviner le mauvais nom généré dépasse la valeur d'un renommage cosmétique.

Revision ID: a3f1c9e02b7d
Revises: d62dabcd6fd0
Create Date: 2026-11-22 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3f1c9e02b7d'
down_revision: Union[str, Sequence[str], None] = 'd62dabcd6fd0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("bildbus_customers", "buildness_customers")
    op.rename_table("bildbus_companies", "buildness_companies")
    op.rename_table("bildbus_webhook_logs", "buildness_webhook_logs")
    op.execute("ALTER INDEX idx_bbco_customer_id RENAME TO idx_buildness_companies_customer_id")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER INDEX idx_buildness_companies_customer_id RENAME TO idx_bbco_customer_id")
    op.rename_table("buildness_webhook_logs", "bildbus_webhook_logs")
    op.rename_table("buildness_companies", "bildbus_companies")
    op.rename_table("buildness_customers", "bildbus_customers")
