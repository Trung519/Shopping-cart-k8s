-- Existing enum compatibility only: retain all old statuses, add CONFIRMED/DELIVERED.
-- Run on the existing orders primary, never recreate the database or delete rows.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '30s';
ALTER TABLE public.orders DROP CONSTRAINT orders_status_check;
ALTER TABLE public.orders ADD CONSTRAINT orders_status_check CHECK (
    status IN ('PENDING', 'PAID', 'CONFIRMED', 'PROCESSING', 'SHIPPED',
               'DELIVERED', 'COMPLETED', 'CANCELLED')
);
COMMIT;
