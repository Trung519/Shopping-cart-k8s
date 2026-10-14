# Shopping Cart observability

The existing `shopping-observability` Argo CD Application owns this chart in
`shopping-cart-observability`. Do not create a separate metrics Application or
install it in `monitoring`.

`metrics` is the pinned kube-prometheus-stack dependency (91.8.2), containing
Prometheus, Grafana, Alertmanager, kube-state-metrics and node exporters. The
`shopmon` resource names remain stable so migrated data claims can be reused.
Loki and Fluent Bit are enabled in this chart. Loki runs one SingleBinary replica
with an 8Gi local-path PVC and 48h retention. Fluent Bit runs once per Linux node,
collecting Shopping Cart logs and excluding the observability namespace. It uses
stat polling (inotify initialization hit errno24 in this lab), persistent node-local
offsets, max8 memory-resident chunks and a 50M filesystem output buffer.
The standalone Grafana dependency stays disabled. The existing metrics Grafana has
Loki datasource UID `loki`; the existing dashboard now includes a Live Logs panel.
Grafana's memory limit is640Mi after repeated exit137 near the previous512Mi limit;
the exact termination cause was not conclusively established as OOM.

## Git-managed configuration

- `values.yaml`: resources, persistence, Istio/RabbitMQ scrape discovery and settings.
- `files/alerts-spec.yaml`: real alert conditions; no always-firing test rule.
- `files/shopping-live.json`: dashboard provisioned through a ConfigMap.
- `files/telegram-message.tmpl`: clickable HTML notification links.
- `templates/metrics.yaml`: alert rules, dashboard and notification template ConfigMaps.
- `Chart.lock` and vendored dependencies: reproducible render.

Secrets `shopmon-grafana-admin`, `shopmon-telegram`, and
`shopmon-alertmanager-config` are prerequisites in the destination namespace.
They are retained outside Git. Never commit token, chat ID, password or Secret exports.
The receiver configuration Secret references template `shopping.telegram` and
`/etc/alertmanager/configmaps/shopmon-alert-templates/*.tmpl`. Token and chat ID
stay in Secrets; the template is managed in Git.

## Argo CD

1. Change this chart and push `dev`.
2. Refresh `shopping-observability`, inspect Diff, then Sync that Application.
3. The existing ApplicationSet applies ServerSideApply for this Application;
   with `ClientSideApplyMigration=false` for Argo CD 3.5. The existing project permits required CRDs, webhook resources, and CoreDNS's
   metrics Service in `kube-system`.
4. Leave automated sync/prune disabled during migration. Review PVC ownership
   before pruning anything; the historical `grafana` PVC is not the migrated
   `shopmon-grafana` PVC.

Use port-forwards to Services `shopmon-grafana` (3000:80), `shopmon-prometheus`
(9090:9090), and `shopmon-alertmanager` (9093:9093), all in
`shopping-cart-observability`. Notification links target this Mac's loopback.
Prometheus Source displays the triggering query; application error details require logs.

## Finding a real request log

Frontend writes access logs to stdout. Send a GET with a unique non-sensitive marker
in its query string and search the existing Loki datasource:

```logql
{job="fluent-bit",kubernetes_namespace_name="shopping-cart-apps",kubernetes_container_name="frontend"} |= "<marker>"
```

Fluent Bit5.0.9 expands nested record accessors into labels with the `kubernetes_`
prefix; use those actual names. Request markers remain log content, not labels.
Collection starts from new logs (Read_from_Head Off); existing offsets persist
through collector restarts. Backend services must emit their own request logs to
support equivalent searches; the pipeline does not invent application logging.
Full request/source/Loki/Grafana-proxy acceptance was verified on2026-10-02.
Retention is configured and the compactor runs; deletion after48h was not time-tested.
The 8Gi local-path claim is a requested capacity, not a filesystem quota.

The three migrated data PVs use Retain. Namespace deletion does not erase them;
storage disposal must be a separate explicit operation.
Grafana `persistence.volumeName` is pinned to this lab's existing PV; this binding
must remain unchanged while adopting the bound PVC with server-side apply.
# Distributed tracing (chart 0.5.0)

Tempo and OTel Collector are managed by this same chart in `shopping-cart-observability`.
The real read-products flow is instrumented in commerce-bff (Go OTel HTTP server/client)
and product-catalog (Python FastAPI/SQLAlchemy). OTLP HTTP goes to Collector 4318;
Collector applies memory limiting, removes SQL text/URL query attributes, batches
and exports to Tempo via OTLP gRPC. Grafana datasource UID: `tempo`.

Tempo: pinned version 2.9.0, one replica, local-path 5Gi PVC, 48h block retention.
Collector: pinned version 0.140.0, one replica, bounded in-memory queue, retry 60s,
256Mi memory limit. Queue does not survive a restart. Sampling is ParentBased 100%
for instrumented services. DB spans represent application-side calls, not server
execution profiling. RabbitMQ/payment/checkout tracing is not claimed by this flow.

Local application images must be built/imported before syncing their existing Argo
Applications. Build product-catalog with `Dockerfile.telemetry` to preserve existing
application dependencies; the standard Dockerfiles also install the OTel packages.
For k3d on ARM64, export with `docker save --platform=linux/arm64`, then import the
tar archive; inspect node image inventories because k3d can exit 0 despite digest errors.

Use existing Argo app `shopping-observability`, then `product-catalog`, then
`commerce-bff`, at the pushed dev revision. Keep prune disabled. Source values are
`config-secret-secure/values/local/22-product-catalog.yaml` and `25-commerce-bff.yaml`.
Instrumentation can be disabled using `OTEL_SDK_DISABLED=true` and a normal rollout.
Keep Tempo PVC during rollback. `local-path` capacity is not a filesystem hard quota.


## Full-system tracing acceptance

Full request instrumentation for8 SDK services and namespace Istio tracing is implemented.30 real requests/666 verified spans include checkout, order confirmation, JDBC/Redis and exact RabbitMQ producer→consumer propagation. [Final execution plan](../docs/PLAN_FULL_SYSTEM_TRACING.md) records corrections, selective existing-Argo operations, evidence and explicit limits. Observability remains in shopping-cart-observability; the existing Istio mesh merge and additive order-status SQL migration are explicit prerequisites.
