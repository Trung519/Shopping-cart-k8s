# ShopCart Performance

Reusable Docker Compose performance harness for the local ShopCart cluster.

It drives the public URL as an external client. It does not install anything into Kubernetes and does not modify ShopCart source code.

## Start

```bash
cp .env.example .env.local
make up
open http://localhost:3030
make smoke
make report RUN_ID=<run-id>
make load
```

The admin password is read from macOS Keychain service `shopping-cart-marketplace-admin`. It is passed to the tools container through stdin and is never written to Git or logs.

The default `load` profile ramps to 200 virtual users. The 500-user stress profile requires an explicit confirmation:

```bash
make stress CONFIRM=I_UNDERSTAND
```

## Results

Grafana: `http://localhost:3030`  
Prometheus: `http://localhost:9090`

Per-run files are written under `.local/results/<run-id>` and are ignored by Git. Fixture users, products, shops, orders and carts use a `perf-<run-id>` prefix and are cleaned by `make cleanup RUN_ID=<run-id>`.

The generated `report.md`, k6 `summary.json`, and cluster metrics are kept together for each run. Payment has a separate disabled profile because checkout does not call Payment Service in the current deployment.

Each run follows one lifecycle: preflight, fixture preparation, cluster monitor,
k6, business verification, report generation, and exact cleanup. Interrupting a
run still triggers the report and cleanup trap. A non-zero k6 or verification
result is retained even when cleanup succeeds.

Use the dashboard variable `run_id` in Grafana to select a run. Prometheus is
the metric store and query engine; Grafana reads those metrics and presents the
curated dashboard. Useful PromQL examples:

```promql
sum(max_over_time(k6_http_reqs_total{run_id="$run_id"}[30m]))
sum by (status) (max_over_time(k6_http_reqs_total{run_id="$run_id"}[30m]))
max_over_time(k6_shopcart_flow_duration_p99{run_id="$run_id"}[30m])
```

The harness verifies persisted orders, inventory deltas, cart state, seller
ownership, seller applications, duplicate orders, pod readiness and restarts.
It does not count a successful POST alone as a successful checkout.

## Validation

```bash
make validate
make unit
make self-test-failure
```

`self-test-failure` deliberately violates a threshold and passes only when the
runner preserves the failure, writes a report, and cleans its fixture.

## Current application behavior

The UI's “Mua ngay” currently adds one product to the cart and navigates to the cart. The checkout API creates the order and reserves inventory. The payment service is measured by an optional isolated profile because the current frontend checkout does not call it yet.
