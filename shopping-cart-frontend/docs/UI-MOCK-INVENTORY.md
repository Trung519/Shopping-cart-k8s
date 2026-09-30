# ShopCart UI mock inventory

Implementation entry: `/demo/admin` and `/demo/admin/:section`.

This is an isolated frontend demo, not a substitute for the protected `/admin` application. No network mutation is made by the demo. Data is saved to localStorage under `shopcart-operations-demo-v1`. Reset restores the fixture set. No fixture represents a real person or transaction.

## Current delivery

Standalone responsive operations shell, navigation, overview, charts calculated from demo orders, search, status filtering, CSV export, draft creation, editable detail drawer and local persistence. All sections visibly identify their data as demo.

## Mock register and backend handoff

| Route suffix | Mocked data | Working demo actions | Backend work / remaining UI depth |
| --- | --- | --- | --- |
| overview | Order totals, counts, priority links | Navigate to module | Aggregate API with date range, metric definitions; KPI counts currently apply only to the fixture set |
| orders | Customer names, product summaries, values, statuses | Search/filter, edit detail, notes, export | Order detail, line items, payments, shipping timeline and valid transition contract; current edit form is generic |
| products | Product summaries and prices | Draft/edit/filter/export | Product schema, variants, media uploads and moderation; variant/media editor not implemented |
| customers | Sample customer names | Draft/edit/filter/export | Customer profile and purchase history; generic editor only |
| inventory | Warehouse/product labels and stock count | Edit quantity and note | Availability/reservation model and adjustment audit; generic local edits only |
| promotions | Sample coupon titles | Draft/edit/filter/export | Eligibility, schedules, redemption limits and discount calculation; rules builder not implemented |
| content | Collection/banner titles | Draft/edit/filter/export | Media, placement, publication versioning; visual page builder not implemented |
| returns | Example order references and reasons | Edit notes/status | Evidence uploads, approval and refund APIs; generic editor only |
| finance | Example reconciliation/refund records | Filter/export | Transaction ledger, settlement and refund contracts; values are placeholders, not actual financial metrics |
| support | Example support subjects | Edit notes/status | Conversation messages, assignment, reply delivery and SLA; inbox thread UI not implemented |
| analytics | Chart from fixture orders | Navigate to orders | Time series, funnel, attribution and retention; currently overview visualization only |
| audit | Sample event labels | Search/filter/export | Immutable events with actor, timestamp and before/after; current generic demo editor is not an audit implementation |
| settings | Example settings labels | Edit local record | Typed settings forms and validation; generic editor only |

## Present demo record shape

`{ id: string, title: string, subtitle: string, amount: number, status: string, note: string }`

This is a demo presentation shape, **not a proposed universal production API**. Backend adapters should map domain-specific DTOs into dedicated UI models. Currency in this demo is VND. Inventory uses unit counts. Do not use fixture identities or IDs with production endpoints.

## Remaining scope from accepted plan

Buyer redesign; dedicated module workflows listed above; seller approval demo; pagination and saved filters; complete loading/error scenarios; visual verification at 1440/1024/768/390; end-to-end keyboard verification. Existing buyer and protected admin pages retain their earlier implementation.

No production-readiness or end-to-end commerce claim is made by this batch.
