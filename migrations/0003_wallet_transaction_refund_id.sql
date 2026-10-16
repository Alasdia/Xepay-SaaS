-- Migration 0003 : colonne refund_id sur wallet_transactions
-- Un remboursement ne crée pas de nouvelle ligne : il repasse le status
-- d'une ligne de dépôt existante à "refunded" (voir
-- backend/routes/payout.py:refund_payment et
-- backend/routes/webhook/paiement.py). Jusqu'ici rien ne stockait l'ID du
-- Refund Stripe lui-même (re_...), distinct de `reference` qui reste
-- volontairement l'ID du paiement original (payment_intent_id ou
-- invoice_id) pour ne pas casser la déduplication/les recherches
-- existantes. refund_id permet d'afficher la bonne référence dans
-- l'historique du wallet pour une ligne remboursée.
--
-- Appliquer :   psql $DATABASE_URL -f migrations/0003_wallet_transaction_refund_id.sql
-- Annuler  :    psql $DATABASE_URL -f migrations/0003_wallet_transaction_refund_id.sql --variable=action=down
--               (ou exécuter directement la section "DOWN" ci-dessous)

-- ===== UP =====

ALTER TABLE wallet_transactions
    ADD COLUMN IF NOT EXISTS refund_id VARCHAR;

-- ===== DOWN (rollback) =====
-- ALTER TABLE wallet_transactions DROP COLUMN IF EXISTS refund_id;
