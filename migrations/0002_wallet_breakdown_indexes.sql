-- Migration 0002 : index de performance pour l'agrégation du solde par
-- source (/wallet/breakdown) et le calcul du solde global (/wallet/me).
-- Ces deux routes agrègent désormais wallet_transactions en SQL (SUM/MIN
-- conditionnels côté Postgres, plus de .all() rapatrié en Python) filtrées
-- sur (user_id, type, status[, source]) et triées sur available_at pour le
-- prochain déblocage — sans ces index, ces agrégats dégénèrent en scan
-- complet des transactions de l'utilisateur dès que son historique grossit
-- (des millions, voire des milliards de lignes à terme).
--
-- Appliquer :   psql $DATABASE_URL -f migrations/0002_wallet_breakdown_indexes.sql
-- Annuler  :    psql $DATABASE_URL -f migrations/0002_wallet_breakdown_indexes.sql --variable=action=down
--               (ou exécuter directement la section "DOWN" ci-dessous)

-- ===== UP =====

-- Couvre le GROUP BY source de /wallet/breakdown et les SUM conditionnels
-- de /wallet/me (type/status en tête, filtrés sur une égalité ; amount et
-- fee_amount en INCLUDE pour un index-only scan, pas de retour en heap).
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_wallet_tx_user_type_status_source
    ON wallet_transactions (user_id, type, status, source)
    INCLUDE (amount, fee_amount);

-- Index partiel dédié aux fonds encore verrouillés (available_at futur) :
-- alimente next_available_at (MIN) et la liste bornée des locked_items
-- (ORDER BY available_at ASC LIMIT 50) en O(log n + k), indépendamment du
-- nombre total de dépôts déjà réglés et sortis de cette fenêtre.
CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_wallet_tx_locked_lookup
    ON wallet_transactions (user_id, available_at)
    WHERE type = 'deposit' AND available_at IS NOT NULL;

-- ===== DOWN (rollback) =====
-- DROP INDEX CONCURRENTLY IF EXISTS ix_wallet_tx_user_type_status_source;
-- DROP INDEX CONCURRENTLY IF EXISTS ix_wallet_tx_locked_lookup;
