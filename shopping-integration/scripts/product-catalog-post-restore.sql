BEGIN;

ALTER TABLE products ADD COLUMN IF NOT EXISTS currency VARCHAR(3) NOT NULL DEFAULT 'USD';
ALTER TABLE products ADD COLUMN IF NOT EXISTS quantity INTEGER NOT NULL DEFAULT 0;
ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE;

DROP VIEW IF EXISTS low_inventory_products;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'products'
      AND column_name = 'inventory_count'
  ) THEN
    UPDATE products
    SET quantity = inventory_count
    WHERE quantity = 0;
  END IF;

  IF EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'products'
      AND column_name = 'id'
      AND data_type = 'integer'
  ) THEN
    ALTER TABLE products ALTER COLUMN id DROP DEFAULT;
    ALTER TABLE products
      ALTER COLUMN id TYPE UUID
      USING md5('shopping-cart-product-' || id::text)::uuid;
    DROP SEQUENCE IF EXISTS products_id_seq;
  END IF;
END $$;

CREATE OR REPLACE VIEW low_inventory_products AS
SELECT *
FROM products
WHERE is_active = TRUE AND quantity <= 10;

COMMIT;
