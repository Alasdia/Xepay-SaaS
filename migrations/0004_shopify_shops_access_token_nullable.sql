-- Migration 0004 : access_token devient NULLABLE sur shopify_shops
-- Le mécanisme de déconnexion (POST /shopify/disconnect, routes/
-- shopify.py::shopify_disconnect, demande du 2026-11-24) vide
-- access_token ET merchant_id sur la ligne existante plutôt que de la
-- supprimer (shop_domain reste UNIQUE, pour qu'une ré-connexion
-- ultérieure de la même boutique retrouve cette ligne au lieu d'en
-- créer une seconde) - sans cette migration, ce commit échoue en
-- IntegrityError (colonne NOT NULL à l'origine, voir models.py).
--
-- Appliquer :   psql $DATABASE_URL -f migrations/0004_shopify_shops_access_token_nullable.sql
-- Annuler  :    voir la section "DOWN" ci-dessous (ne fonctionne que si
--               aucune ligne n'a access_token NULL au moment du rollback)

-- ===== UP =====

ALTER TABLE shopify_shops
    ALTER COLUMN access_token DROP NOT NULL;

-- ===== DOWN (rollback) =====
-- ALTER TABLE shopify_shops ALTER COLUMN access_token SET NOT NULL;
