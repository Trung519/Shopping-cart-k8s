# Category and Inventory Regression Report

Date: 2026-08-02  
Cluster: `k3d-lab-k8s`

## Result

| Check | Result | Evidence |
| --- | --- | --- |
| Admin can create and delete categories | PASS | Temporary category returned `201` and was deleted |
| Arbitrary product category is rejected | PASS | Product create with free-text category returned `422` |
| Storefront taxonomy is canonical | PASS | 12 active categories; 0 products reference an unknown category |
| Imported catalog is complete | PASS | 400 imported products and 400 distinct product names |
| Checkout decrements inventory | PASS | Test product quantity changed from 61 to 59 for a quantity-2 order |
| Failed checkout compensation | PASS | Inventory reserve was released when order creation was unavailable |
| Test data cleanup | PASS | Test order count returned to 0 and product quantity returned to 61 |
| Runtime health | PASS | 0 non-ready pods; Vault initialized and unsealed |

## Implementation

- Categories are persisted as a managed taxonomy instead of arbitrary product text.
- Category CRUD is restricted to catalog/platform administrators.
- Product creation and editing accept only an active category slug.
- Seller and product forms use a category selector sourced from the catalog API.
- Checkout reserves inventory atomically before order creation.
- Reservation is released when order creation fails; successful checkout keeps stock deducted.
- The online fixture set was reseeded transactionally and normalized to the canonical taxonomy.

## Repeat Verification

Run:

```bash
./scripts/verify-category-inventory.sh
```

The script uses an isolated temporary category, cart, and order. Its exit cleanup removes the order and restores the selected product's original inventory. Authentication credentials are read from macOS Keychain and are never printed.

## Deployed Images

- `shopping-cart-product-catalog:v1.3.2`
- `shopping-cart-basket:v1.4.0`
- `shopping-cart-frontend:v2.1.0`

Draft images created during this change were removed after deployment verification.
