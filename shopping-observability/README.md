# Shopping Observability

Helm umbrella chart for the lab shopping-cart logging stack.

This folder vendors upstream Helm charts under `helmchart/charts/` so external chart code is kept separate from local configuration:

- `grafana/loki` chart `7.2.0`
- `grafana/grafana` chart `10.5.15`
- `fluent/fluent-bit` chart `0.57.9`

The local chart configures:

- Namespace: `shopping-cart-observability`
- Fluent Bit DaemonSet to collect `/var/log/containers/*.log`
- Loki single-binary with filesystem storage, PVC `8Gi`, retention `48h`
- Loki disk-pressure cleaner requests deletion of the oldest 4-hour log window when the PVC reaches 90%
- Grafana with a Loki datasource

The pinned Grafana chart is marked deprecated by its upstream repository. It is retained for this lab release because it is the latest version available in the configured upstream repository; migrate the vendored dependency before treating this stack as a production baseline.

## Review

Render everything before applying:

```bash
helm template shopping-observability ./helmchart \
  --namespace shopping-cart-observability
```

Check chart structure:

```bash
helm lint ./helmchart
```

## Apply after review approval

```bash
kubectl --context k3d-lab-k8s create namespace shopping-cart-observability \
  --dry-run=client -o yaml | kubectl --context k3d-lab-k8s apply -f -

kubectl --context k3d-lab-k8s label namespace shopping-cart-observability \
  istio-injection=disabled --overwrite

helm upgrade --install shopping-observability ./helmchart \
  --kube-context k3d-lab-k8s \
  --namespace shopping-cart-observability
```

## Verify

```bash
kubectl --context k3d-lab-k8s -n shopping-cart-observability get pods,pvc,svc -o wide
kubectl --context k3d-lab-k8s -n shopping-cart-observability get ds fluent-bit -o wide
kubectl --context k3d-lab-k8s -n shopping-cart-observability get pods \
  -l app.kubernetes.io/name=fluent-bit \
  -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,READY:.status.containerStatuses[*].ready
kubectl --context k3d-lab-k8s -n shopping-cart-observability logs ds/fluent-bit --tail=100
kubectl --context k3d-lab-k8s -n shopping-cart-observability port-forward svc/grafana 3000:80
```

Grafana local URL:

```text
http://localhost:3000
```

Retrieve the generated Grafana admin password from its Kubernetes Secret:

```bash
kubectl --context k3d-lab-k8s -n shopping-cart-observability \
  get secret grafana-admin -o jsonpath='{.data.admin-password}' | base64 --decode
```

After rollout, acceptance requires Fluent Bit `DESIRED=3` and `READY=3`, with exactly one Fluent Bit pod on each cluster node. Query Loki by the generated `kubernetes_host`, `kubernetes_namespace_name`, `kubernetes_pod_name`, and `kubernetes_container_name` labels to verify end-to-end ingestion from all nodes and namespaces. `Read_from_Head On` plus the host-persisted Tail DB ensures existing container log files are collected once and subsequent restarts resume from their saved offsets.

The disk-pressure cleaner checks allocated bytes under `/var/loki` every five minutes against the configured `8Gi` capacity. This is intentional because the cluster's `local-path` provisioner does not enforce a filesystem quota. At 90% usage (about `7.2Gi`) it asks Loki to delete the actual oldest four-hour window, then waits four hours before another pressure deletion. Deletion is asynchronous and handled by the Loki compactor; it never removes PVC files directly.

Note: if Rancher webhook is not Ready, namespace creation can fail. Check it first:

```bash
kubectl --context k3d-lab-k8s -n cattle-system get pods,svc,endpoints -o wide
```
