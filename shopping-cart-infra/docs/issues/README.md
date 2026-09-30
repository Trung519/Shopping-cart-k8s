# Known Issues and Resolutions

[← Back to README](../../README.md)

This directory documents common issues encountered with the shopping cart infrastructure and their resolutions.

## Issue Index

| Issue | Summary | Status |
|-------|---------|--------|
| [001-rabbitmq-nodeport](./001-rabbitmq-nodeport.md) | RabbitMQ NodePort not accessible | Resolved |
| [002-rabbitmq-prometheus-plugin](./002-rabbitmq-prometheus-plugin.md) | RabbitMQ prometheus plugin not enabled | Resolved |

## Quick Fixes

### RabbitMQ NodePort Not Accessible

```bash
kubectl patch svc rabbitmq -n shopping-cart-data -p '{
  "spec": {
    "type": "NodePort",
    "ports": [{
      "name": "amqp",
      "port": 5672,
      "targetPort": 5672,
      "nodePort": 30672
    }]
  }
}'
```

### RabbitMQ Prometheus Plugin

1. Add `rabbitmq_prometheus` to `data-layer/rabbitmq/configmap.yaml`:
```yaml
enabled_plugins: |
  [rabbitmq_management,rabbitmq_peer_discovery_k8s,rabbitmq_prometheus].
```

2. Add port 15692 to StatefulSet and Service

3. Restart pods:
```bash
kubectl rollout restart statefulset/rabbitmq -n shopping-cart-data
```

## Related Repositories

- [rabbitmq-client-library](../../../rabbitmq-client-library/) - Client library issues
- [observability-stack](../../../observability-stack/) - Monitoring stack issues
