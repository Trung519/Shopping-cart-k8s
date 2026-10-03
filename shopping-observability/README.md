# Shopping Observability

Chart 0.5.0 manages logs, metrics, alerts and distributed tracing in the existing namespace `shopping-cart-observability`, through the existing Argo CD Application `shopping-observability` on branch `dev`.

## Components

- kube-prometheus-stack 91.8.2: Prometheus, Alertmanager, Grafana (`shopmon-grafana`), node exporter and kube-state-metrics. Prometheus retention is 3 days / 3GB.
- Loki chart 7.2.0: single binary, local PVC 8Gi, retention 48h. The existing disk-pressure cleaner requests asynchronous deletion of the oldest four-hour window at 90% usage; local-path does not enforce a hard filesystem quota.
- Fluent Bit chart 0.57.9: one pod per node, container logs with Kubernetes metadata and persistent Tail DB. Current Read_from_Head is Off; acceptance uses a newly generated request rather than promising backfill of historical log files.
- Tempo image 2.9.0: monolithic, PVC 5Gi, WAL/local blocks, compactor retention 48h; OTLP only on ClusterIP.
- OTel Collector contrib image 0.140.0: OTLP receivers, memory limiter, privacy processing, batching and bounded retry queue; sends traces to Tempo. The observed binary reports 0.140.1 despite the pinned image tag.
- Go BFF and Python FastAPI/SQLAlchemy catalog instrumentation: W3C context propagation and PostgreSQL client dependency spans.

The standalone vendored Grafana chart 10.5.15 remains disabled. Active Grafana is the kube-prometheus-stack instance; do not deploy a second Grafana or a new observability namespace to extend this stack.

## Plans and verified scope

- [Full observability plan](docs/PLAN.md)
- [Fluent Bit + Loki execution plan](docs/PLAN_FLUENTBIT_LOKI.md)
- [Tempo + Collector + OTel execution plan, real evidence and Argo operations](docs/PLAN_TEMPO_OTEL.md)

The verified flow is a real public products GET through Gateway → commerce-bff → product-catalog → PostgreSQL. The trace contains two application services and DB client spans; browser/Gateway server spans, checkout, payment and RabbitMQ tracing are not implemented by this stage. Grafana links both logs → trace and trace → logs, and the existing live metrics dashboard links to Tempo.

## Operate through the existing Argo Applications

Edit existing source/chart/local overrides → lint/render and review → build/import fresh application image tags → commit/push dev → Refresh/Diff/Sync the existing Applications. In the current local-image setup, Argo does not build or distribute images. Both Argo sources must use the same pushed revision. Keep prune=false for this change and preserve PVCs. Follow the tracing plan for selective sync rather than reapplying unrelated CRDs/hooks/data charts.

```bash
helm lint shopping-observability/helmchart
helm template shopping-observability shopping-observability/helmchart --namespace shopping-cart-observability
kubectl --context k3d-lab-k8s -n shopping-cart-observability get pods,pvc,svc
kubectl --context k3d-lab-k8s -n shopping-cart-observability port-forward svc/shopmon-grafana 3000:80
kubectl --context k3d-lab-k8s -n shopping-cart-observability port-forward svc/shopmon-prometheus 9090:9090
kubectl --context k3d-lab-k8s -n shopping-cart-observability port-forward svc/tempo 3200:3200
```

Commands assume repository root. When operated from Agent_setup, use its approved trace runner for every substantive command. Rendered output can contain Secrets: inspect privately and do not commit or copy raw rendered manifests into logs. Grafana is available at `http://localhost:3000` while its port-forward runs; port 3000 is not an Ingress/NodePort exposure.

Credentials remain in existing Kubernetes Secrets; do not print them into execution logs or Git. The final deployment recovered a VM global OOM and uses temporary VM swap. Read the incident section in the tracing plan before repeating resource-intensive builds. The stack is single-replica/local-storage, not an HA production deployment. ExternalSecret provider errors in the two application Argo health statuses are documented separately from their healthy running workloads.


## Full-system tracing acceptance

Full request instrumentation for8 SDK services and namespace Istio tracing is implemented.30 real requests/666 verified spans include checkout, order confirmation, JDBC/Redis and exact RabbitMQ producer→consumer propagation. [Final execution plan](docs/PLAN_FULL_SYSTEM_TRACING.md) records corrections, selective existing-Argo operations, evidence and explicit limits. Observability remains in shopping-cart-observability; the existing Istio mesh merge and additive order-status SQL migration are explicit prerequisites.


Catalog access-log correlation correction: deployed v1.4.8-access-trace-20261003; product UUID access lines now carry active trace/span IDs. See final plan correction section and catalog-access-correlation-evidence.json for actual GET200→12-span SQL trace acceptance. Historical logs remain unchanged.
