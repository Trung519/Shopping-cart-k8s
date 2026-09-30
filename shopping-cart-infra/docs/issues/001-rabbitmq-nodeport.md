# Issue 002: RabbitMQ NodePort Not Accessible

## Summary

Integration tests fail with "RabbitMQ NodePort 30672 is not accessible" error.

## Symptoms

```
[0;31m✗ RabbitMQ NodePort 30672 is not accessible[0m
  Ensure RabbitMQ service is NodePort type:
  kubectl patch svc rabbitmq -n shopping-cart-data -p '{"spec": {"type": "NodePort", ...}}'
```

## Root Cause

The RabbitMQ service is configured as `ClusterIP` instead of `NodePort`, making it inaccessible from outside the cluster (including the test runner on the host).

## Diagnosis

```bash
# Check RabbitMQ service type
kubectl get svc rabbitmq -n shopping-cart-data

# Look for TYPE column - should be NodePort, not ClusterIP
NAME       TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)
rabbitmq   ClusterIP   10.43.61.104   <none>        5672/TCP   <-- Problem
```

## Resolution

### Option 1: Patch the Service (Quick Fix)

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

### Option 2: Update Service Manifest (Permanent Fix)

Edit `shopping-cart-infra/data-layer/rabbitmq/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: rabbitmq
  namespace: shopping-cart-data
spec:
  type: NodePort          # Changed from ClusterIP
  ports:
    - name: amqp
      port: 5672
      targetPort: 5672
      nodePort: 30672     # Added explicit NodePort
  selector:
    app: rabbitmq
```

Apply the change:
```bash
kubectl apply -f shopping-cart-infra/data-layer/rabbitmq/service.yaml
```

### Verify

```bash
# Check service is now NodePort
kubectl get svc rabbitmq -n shopping-cart-data

# Expected output:
NAME       TYPE       CLUSTER-IP     EXTERNAL-IP   PORT(S)          AGE
rabbitmq   NodePort   10.43.61.104   <none>        5672:30672/TCP   10d

# Test connectivity
nc -zv localhost 30672
```

## Environment Variables

The test runner uses these environment variables for NodePort configuration:

```bash
# Default values in bin/run-tests.sh
RABBITMQ_NODEPORT=30672
VAULT_NODEPORT=30820

# Override if using different ports
export RABBITMQ_NODEPORT=32672
./bin/run-tests.sh integration
```

## Prevention

Ensure the RabbitMQ service manifest always specifies NodePort type for development/testing environments:

```yaml
# In service.yaml
spec:
  type: NodePort
  ports:
    - name: amqp
      port: 5672
      targetPort: 5672
      nodePort: 30672
```

## Related

- [Kubernetes NodePort Services](https://kubernetes.io/docs/concepts/services-networking/service/#type-nodeport)
- `bin/run-tests.sh` - Test runner script
- `shopping-cart-infra/data-layer/rabbitmq/service.yaml`
