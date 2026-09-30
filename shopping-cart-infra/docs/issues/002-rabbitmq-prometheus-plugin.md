# Issue 004: RabbitMQ Prometheus Plugin Not Enabled

## Summary

RabbitMQ metrics are not being scraped by Prometheus because the `rabbitmq_prometheus` plugin is not enabled.

## Symptoms

- Prometheus target for RabbitMQ shows as DOWN
- RabbitMQ dashboard in Grafana shows "No data"
- Connection refused when accessing `http://rabbitmq:15692/metrics`

```bash
# Check if plugin is enabled
kubectl exec -n shopping-cart-data rabbitmq-0 -c rabbitmq -- rabbitmq-plugins list | grep prometheus

# Output showing plugin disabled:
[  ] rabbitmq_prometheus               3.12.14
```

## Root Cause

The RabbitMQ deployment was not configured with the `rabbitmq_prometheus` plugin enabled in the `enabled_plugins` file.

## Diagnosis

```bash
# Check enabled plugins
kubectl exec -n shopping-cart-data rabbitmq-0 -c rabbitmq -- rabbitmq-plugins list | grep -E "^\[E"

# Check if metrics port is exposed
kubectl get svc rabbitmq-headless -n shopping-cart-data -o yaml | grep 15692
```

## Resolution

### Step 1: Update ConfigMap

Edit `shopping-cart-infra/data-layer/rabbitmq/configmap.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: rabbitmq-config
  namespace: shopping-cart-data
data:
  enabled_plugins: |
    [rabbitmq_management,rabbitmq_peer_discovery_k8s,rabbitmq_prometheus].
```

Note: The `rabbitmq_prometheus` plugin is added to the list.

### Step 2: Update StatefulSet

Edit `shopping-cart-infra/data-layer/rabbitmq/statefulset.yaml` to add the prometheus port:

```yaml
containers:
  - name: rabbitmq
    ports:
      - name: amqp
        containerPort: 5672
      - name: management
        containerPort: 15672
      - name: prometheus          # Add this
        containerPort: 15692
        protocol: TCP
```

### Step 3: Update Service

Edit `shopping-cart-infra/data-layer/rabbitmq/service.yaml` to expose the prometheus port:

```yaml
spec:
  ports:
    - name: prometheus
      port: 15692
      targetPort: 15692
      protocol: TCP
```

### Step 4: Apply Changes

```bash
# Apply updated manifests
kubectl apply -f shopping-cart-infra/data-layer/rabbitmq/configmap.yaml
kubectl apply -f shopping-cart-infra/data-layer/rabbitmq/service.yaml
kubectl apply -f shopping-cart-infra/data-layer/rabbitmq/statefulset.yaml

# Restart RabbitMQ pods to pick up new config
kubectl rollout restart statefulset/rabbitmq -n shopping-cart-data
```

### Step 5: Create ServiceMonitor

Create `observability-stack/manifests/prometheus/servicemonitors/rabbitmq.yaml`:

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: rabbitmq
  namespace: monitoring
  labels:
    release: prometheus
spec:
  namespaceSelector:
    matchNames:
      - shopping-cart-data
  selector:
    matchLabels:
      app: rabbitmq
  endpoints:
    - port: prometheus
      interval: 30s
      path: /metrics
```

Apply:
```bash
kubectl apply -f observability-stack/manifests/prometheus/servicemonitors/rabbitmq.yaml
```

### Step 6: Verify

```bash
# Check plugin is enabled
kubectl exec -n shopping-cart-data rabbitmq-0 -c rabbitmq -- rabbitmq-plugins list | grep prometheus
# Output: [E ] rabbitmq_prometheus

# Test metrics endpoint
kubectl run curl-test --rm -i --restart=Never --image=curlimages/curl -- \
  curl -s http://rabbitmq-headless.shopping-cart-data:15692/metrics | head -20

# Check Prometheus target
kubectl run curl-test2 --rm -i --restart=Never --image=curlimages/curl -- \
  curl -s "http://prometheus-kube-prometheus-prometheus.monitoring:9090/api/v1/targets" | \
  grep -o '"job":"[^"]*rabbitmq[^"]*"'
```

## Important Notes

### Cannot Enable Plugin at Runtime

Attempting to enable the plugin on a running container will fail:

```bash
kubectl exec -n shopping-cart-data rabbitmq-0 -c rabbitmq -- rabbitmq-plugins enable rabbitmq_prometheus
# Error: {:cannot_write_enabled_plugins_file, ~c"/etc/rabbitmq/enabled_plugins", :erofs}
```

This is because the `/etc/rabbitmq` directory is mounted from a ConfigMap and is read-only. The plugin must be enabled via the ConfigMap and requires a pod restart.

### Scaling Considerations

If RabbitMQ is scaled to multiple replicas and CPU resources are limited, you may need to scale down temporarily:

```bash
# Scale down to allow restart
kubectl scale statefulset/rabbitmq -n shopping-cart-data --replicas=1

# Delete pod to force recreation with new config
kubectl delete pod rabbitmq-0 -n shopping-cart-data

# Wait for pod to be ready
kubectl wait --for=condition=ready pod/rabbitmq-0 -n shopping-cart-data --timeout=120s

# Scale back up (if resources allow)
kubectl scale statefulset/rabbitmq -n shopping-cart-data --replicas=3
```

## Metrics Available

Once enabled, RabbitMQ exposes metrics including:

| Metric | Description |
|--------|-------------|
| `rabbitmq_connections` | Number of connections |
| `rabbitmq_channels` | Number of channels |
| `rabbitmq_queues` | Number of queues |
| `rabbitmq_consumers` | Number of consumers |
| `rabbitmq_queue_messages_ready` | Messages ready for delivery |
| `rabbitmq_queue_messages_unacked` | Unacknowledged messages |
| `rabbitmq_process_resident_memory_bytes` | Memory usage |

## Related

- [RabbitMQ Prometheus Plugin](https://www.rabbitmq.com/prometheus.html)
- `shopping-cart-infra/data-layer/rabbitmq/`
- `observability-stack/manifests/prometheus/servicemonitors/rabbitmq.yaml`
