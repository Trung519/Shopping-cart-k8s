# Shopping Cart observability

The existing `shopping-observability` Argo CD Application owns this chart in
`shopping-cart-observability`. Do not create a separate metrics Application or
install it in `monitoring`.

`metrics` is the pinned kube-prometheus-stack dependency (91.8.2), containing
Prometheus, Grafana, Alertmanager, kube-state-metrics and node exporters. The
`shopmon` resource names remain stable so migrated data claims can be reused.
Loki and Fluent Bit remain configured in this chart but disabled, matching the
stopped logging pipeline. The standalone Grafana dependency is disabled to avoid
running a second Grafana. Enabling logs needs a separate RAM assessment and a
Loki datasource in the metrics Grafana.

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

The three migrated data PVs use Retain. Namespace deletion does not erase them;
storage disposal must be a separate explicit operation.
Grafana `persistence.volumeName` is pinned to this lab's existing PV; this binding
must remain unchanged while adopting the bound PVC with server-side apply.
