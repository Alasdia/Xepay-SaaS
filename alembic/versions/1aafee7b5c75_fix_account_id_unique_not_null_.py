"""fix: account_id unique not null, withdrawals payout index, webhook fk cascade

Revision ID: 1aafee7b5c75
Revises: 78e72802e47e
Create Date: 2026-10-02 21:41:23.416863

Synchronise la production avec backend/models.py pour les correctifs #2,
#3 et #4 de l'audit de divergences du 2026-10-02 (#1, api_logs.id, est
delibrement laisse de cote - hors perimetre).

#2 users.account_id : 38 lignes avaient account_id NULL en production
   (verifie en lecture seule avant cette migration, 0 doublon parmi les
   valeurs non-NULL). Backfill avec le meme schema que
   generate_prefixed_id("acct") avant d'ajouter l'index unique et la
   contrainte NOT NULL.
#3 withdrawals.stripe_payout_id : l'index reel (idx_withdrawals_stripe_payout_id)
   n'etait pas unique (0 doublon verifie au prealable). Remplace par un
   index unique nomme selon la convention SQLAlchemy.
#4 webhook_delivery_logs.webhook_id (FK) : aucun changement de schema ici,
   le modele a ete mis a jour separement (ondelete="CASCADE") pour
   refleter un comportement deja reel en production.

Index crees/supprimes en CONCURRENTLY (hors transaction) pour ne prendre
aucun verrou bloquant sur des tables en production.
"""
import secrets
import string
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = '1aafee7b5c75'
down_revision: Union[str, Sequence[str], None] = '78e72802e47e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _generate_account_id() -> str:
    # Meme schema que generate_prefixed_id("acct") dans backend/models.py
    chars = string.ascii_lowercase + string.digits
    random_part = "".join(secrets.choice(chars) for _ in range(24))
    return f"acct_{random_part}"


def upgrade() -> None:
    bind = op.get_bind()

    # --- #2 : backfill des account_id manquants, avant toute contrainte ---
    rows = bind.execute(
        text("SELECT id FROM users WHERE account_id IS NULL")
    ).fetchall()
    used = set()
    for (user_id,) in rows:
        new_account_id = _generate_account_id()
        while new_account_id in used:
            new_account_id = _generate_account_id()
        used.add(new_account_id)
        bind.execute(
            text("UPDATE users SET account_id = :aid WHERE id = :uid"),
            {"aid": new_account_id, "uid": user_id},
        )

    # --- #2 : index unique + NOT NULL (CONCURRENTLY, hors transaction) ---
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_users_account_id ON users (account_id)"
        )
    op.alter_column(
        "users", "account_id",
        existing_type=sa.String(length=50),
        nullable=False,
    )

    # --- #3 : remplace l'index non-unique par un index unique ---
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_withdrawals_stripe_payout_id ON withdrawals (stripe_payout_id)"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS idx_withdrawals_stripe_payout_id"
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "idx_withdrawals_stripe_payout_id ON withdrawals (stripe_payout_id)"
        )
        op.execute(
            "DROP INDEX CONCURRENTLY IF EXISTS ix_withdrawals_stripe_payout_id"
        )

    op.alter_column(
        "users", "account_id",
        existing_type=sa.String(length=50),
        nullable=True,
    )
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_users_account_id")
    # Le backfill de donnees n'est pas annule (les account_id generes
    # restent) : un downgrade de schema ne doit pas supprimer des
    # identifiants deja potentiellement exposes/utilises.
