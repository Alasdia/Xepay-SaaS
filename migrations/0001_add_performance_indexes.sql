-- Migration 0001 : index de performance identifiés lors de l'audit
-- (colonnes réellement filtrées/jointes en production, sur tables à forte
-- croissance organique : workspace_users, wallet_transactions, payments,
-- withdrawals, webhooks). CONCURRENTLY évite tout verrou bloquant en prod.
--
-- Appliquer :   psql $DATABASE_URL -f migrations/0001_add_performance_indexes.sql
-- Annuler  :    psql $DATABASE_URL -f migrations/0001_add_performance_indexes.sql --variable=action=down
--               (ou exécuter directement la section "DOWN" ci-dessous)

-- ===== UP =====

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_workspace_users_user_workspace
    ON workspace_users (user_id, workspace_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_wallet_transactions_user_created
    ON wallet_transactions (user_id, created_at DESC);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payments_user_id
    ON payments (user_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_payments_link_id
    ON payments (link_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_withdrawals_user_id
    ON withdrawals (user_id);

CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_webhooks_user_id
    ON webhooks (user_id);

-- ===== DOWN (rollback) =====
-- DROP INDEX CONCURRENTLY IF EXISTS ix_workspace_users_user_workspace;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_wallet_transactions_user_created;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_payments_user_id;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_payments_link_id;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_withdrawals_user_id;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_webhooks_user_id;
