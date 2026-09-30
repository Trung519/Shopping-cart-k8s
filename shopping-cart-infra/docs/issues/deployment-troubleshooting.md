# Deployment Troubleshooting Guide

This document captures common issues encountered during k3s deployment of the shopping cart microservices and their solutions.

## Table of Contents

1. [Resource Issues](#resource-issues)
2. [Container Image Issues](#container-image-issues)
3. [Database Issues](#database-issues)
4. [Service Configuration Issues](#service-configuration-issues)
5. [Health Check Issues](#health-check-issues)

---

## Resource Issues

### 1. Disk Pressure Causing Pod Evictions

**Symptoms:**
- Pods in `Evicted` state
- Events showing: `The node was low on resource: ephemeral-storage`
- Disk usage > 85%

**Cause:**
k3s evicts pods when disk usage exceeds 85% (kubelet default threshold).

**Solutions:**
```bash
# Check disk usage
df -h /

# Clean systemd journal (often 1-2GB)
sudo journalctl --vacuum-size=100M

# Clean podman images
podman system prune -af

# Clean k3s containerd images
sudo k3s crictl rmi --prune

# Check what's using space
du -sh /var/lib/rancher/k3s/agent/containerd/
```

**Prevention:**
- Monitor disk usage regularly
- Set up disk space alerts
- Use `make debug-disk` to check usage

---

### 2. CPU Exhaustion (100% Allocation)

**Symptoms:**
- Pods stuck in `Pending` state
- Events showing: `0/1 nodes are available: 1 Insufficient cpu`
- `kubectl describe node` shows CPU requests at 100%

**Cause:**
Multiple services with high CPU requests, orphaned replicas from previous deployments, or excessive replica counts.

**Solutions:**
```bash
# Check CPU allocation
kubectl describe node | grep -A 10 "Allocated resources:"

# List pods with CPU requests
kubectl get pods -A -o custom-columns="NS:.metadata.namespace,NAME:.metadata.name,CPU:.spec.containers[*].resources.requests.cpu"

# Scale down non-essential services
make debug-scale-down

# Delete stuck/orphaned pods
kubectl delete pods -A --field-selector=status.phase=Failed --force --grace-period=0
kubectl delete pods -A --field-selector=status.phase=Unknown --force --grace-period=0

# Scale down specific deployment
kubectl scale deployment -n <namespace> <deployment> --replicas=0
```

**Specific Fix for This Environment:**
OpenLDAP, Istio, Grafana, and Prometheus operators had 10-20+ replicas each:
```bash
kubectl scale deployment -n directory openldap-openldap-bitnami --replicas=1
kubectl scale deployment -n istio-system istio-ingressgateway --replicas=1
kubectl scale deployment -n istio-system istiod --replicas=1
kubectl scale deployment -n monitoring prometheus-grafana --replicas=1
kubectl scale deployment -n monitoring prometheus-kube-prometheus-operator --replicas=1
```

---

## Container Image Issues

### 3. Podman Authentication Errors

**Symptoms:**
```
Error: unable to retrieve auth token: unauthorized
```

**Cause:**
Stale or corrupt `auth.json` files from previous registry logins.

**Solutions:**
```bash
# Logout from all registries
podman logout --all

# Remove auth files
rm -f ~/.config/containers/auth.json
rm -f /run/user/$(id -u)/containers/auth.json

# Full reset if needed
podman system reset --force

# Then rebuild images
podman build -f Dockerfile.local -t shopping-cart-order:latest .
```

---

### 4. Images Not Found in k3s (localhost/ prefix issue)

**Symptoms:**
- Pods showing `ImagePullBackOff`
- Events: `Failed to pull image "localhost/shopping-cart-xxx:latest"`

**Cause:**
k3s containerd treats `localhost/` as a registry prefix and tries to pull from it.

**Solutions:**
```bash
# Save images from podman with proper name
podman save localhost/shopping-cart-order:latest -o /tmp/shopping-cart-order.tar

# Import to k3s
sudo k3s ctr images import /tmp/shopping-cart-order.tar

# Verify import
sudo k3s crictl images | grep shopping-cart

# Update deployment to use the exact image name
kubectl set image deployment/order-service order-service=localhost/shopping-cart-order:latest
```

---

### 5. DNS Resolution Failures

**Symptoms:**
```
lookup registry-1.docker.io: Try again
```

**Cause:**
Temporary DNS issues, often after k3s restart.

**Solutions:**
```bash
# Wait and retry - usually resolves in 1-2 minutes
# Force pod restart
kubectl delete pod -n <namespace> <pod-name>

# Check CoreDNS
kubectl get pods -n kube-system -l k8s-app=kube-dns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

---

## Database Issues

### 6. PostgreSQL Schema Mismatch (serial vs UUID)

**Symptoms:**
```
Schema-validation: wrong column type encountered in column [id] in table [order_items];
found [serial (Types#INTEGER)], but expecting [uuid (Types#UUID)]
```

**Cause:**
Database created with old schema (integer IDs) but application expects UUIDs.

**Solutions:**
```bash
# Drop the old tables (data loss!)
kubectl exec -n shopping-cart-data postgresql-orders-0 -- \
  psql -U postgres -d orders -c "DROP TABLE IF EXISTS order_items, orders CASCADE;"

# Or delete the PVC and recreate
kubectl delete pvc -n shopping-cart-data data-postgresql-orders-0
kubectl delete pod -n shopping-cart-data postgresql-orders-0
# StatefulSet will recreate with fresh storage
```

---

### 7. PostgreSQL Missing Columns

**Symptoms:**
```
column products.currency does not exist
column products.quantity does not exist
```

**Cause:**
Database schema doesn't match application model.

**Solutions:**
```bash
# Add missing columns
kubectl exec -n shopping-cart-data postgresql-products-0 -- \
  psql -U postgres -d products -c "
    ALTER TABLE products ADD COLUMN IF NOT EXISTS currency VARCHAR(3) DEFAULT 'USD';
    ALTER TABLE products ADD COLUMN IF NOT EXISTS quantity INTEGER DEFAULT 0;
    ALTER TABLE products ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT true;
  "

# Or drop and let app recreate
kubectl exec -n shopping-cart-data postgresql-products-0 -- \
  psql -U postgres -d products -c "DROP TABLE IF EXISTS products CASCADE;"
kubectl delete pod -n shopping-cart-apps -l app.kubernetes.io/name=product-catalog
```

---

### 8. PostgreSQL Corruption (Checkpoint Record Invalid)

**Symptoms:**
```
PANIC: could not locate a valid checkpoint record
```

**Cause:**
Database corruption, often from unclean shutdown.

**Solutions:**
```bash
# Delete StatefulSet, PVC, and let it recreate
kubectl delete statefulset -n shopping-cart-data postgresql-products
kubectl delete pvc -n shopping-cart-data data-postgresql-products-0
kubectl apply -f data-layer/postgresql/products/statefulset.yaml
```

---

## Service Configuration Issues

### 9. Wrong Environment Variable Names

**Symptoms:**
- Service can't connect to database
- Logs show connection to wrong host

**Cause:**
ConfigMap has `DATABASE_HOST` but app expects `DB_HOST`.

**Solutions:**
```bash
# Check what env vars the app expects (read the config.py or application.yml)
# Patch the ConfigMap
kubectl patch configmap -n shopping-cart-apps product-catalog-config --type='json' \
  -p='[{"op":"add","path":"/data/DB_HOST","value":"postgresql-products.shopping-cart-data.svc.cluster.local"}]'

# Restart the deployment
kubectl rollout restart deployment -n shopping-cart-apps product-catalog
```

---

### 10. Wrong Database Credentials

**Symptoms:**
```
FATAL: password authentication failed for user "product_catalog"
```

**Cause:**
Secret has wrong username/password for the database.

**Solutions:**
```bash
# Check PostgreSQL users
kubectl exec -n shopping-cart-data postgresql-products-0 -- env | grep POSTGRES

# Update the secret
kubectl patch secret -n shopping-cart-apps product-catalog-secrets \
  -p '{"stringData":{"DB_USERNAME":"postgres","DB_PASSWORD":"REPLACE_WITH_LOCAL_SECRET"}}'

# Restart deployment
kubectl rollout restart deployment -n shopping-cart-apps product-catalog
```

---

### 11. RabbitMQ Authentication Failure

**Symptoms:**
```
ACCESS_REFUSED - Login was refused using authentication mechanism PLAIN
```

**Cause:**
Wrong RabbitMQ credentials in secret.

**Solutions:**
```bash
# Reset RabbitMQ user password
kubectl exec -n shopping-cart-data rabbitmq-0 -- rabbitmqctl change_password demo demo

# Update secret
kubectl patch secret -n shopping-cart-apps order-service-secrets \
  -p '{"stringData":{"RABBITMQ_USERNAME":"demo","RABBITMQ_PASSWORD":"demo"}}'

# Restart deployment
kubectl rollout restart deployment -n shopping-cart-apps order-service
```

---

### 12. Vault Sealed After k3s Restart

**Symptoms:**
- Pods failing to start
- Vault-related errors in logs
- `vault status` shows `Sealed: true`

**Solutions:**
```bash
# Get unseal key from secret
kubectl get secret -n vault vault-unseal -o jsonpath='{.data.unseal-key}' | base64 -d

# Unseal vault
kubectl exec -n vault vault-0 -- vault operator unseal '<unseal-key>'

# Or use make target
make debug-vault-unseal
```

---

## Health Check Issues

### 13. Readiness Probe 401 Unauthorized

**Symptoms:**
- Pod running but not ready (0/1)
- Readiness probe failing with 401

**Cause:**
Spring Security blocking actuator endpoints.

**Solutions:**

Option 1: Use an allowed path (check SecurityConfig):
```bash
# If only /actuator/health is allowed, use that
kubectl patch deployment -n shopping-cart-apps order-service --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/actuator/health"}]'
```

Option 2: Use TCP probe instead:
```bash
kubectl patch deployment -n shopping-cart-apps order-service --type='json' \
  -p='[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe","value":{"tcpSocket":{"port":8080},"initialDelaySeconds":30,"periodSeconds":5}}]'
```

---

### 14. Health Check 503 (Custom Health Indicator Failing)

**Symptoms:**
- Pod running but not ready
- Health endpoint returns 503
- Logs show: `Health check failed` from custom indicator

**Cause:**
Custom RabbitMQ health indicator (from rabbitmq-client library) failing.

**Solutions:**

Option 1: Use TCP probes:
```bash
kubectl patch deployment -n shopping-cart-apps order-service --type='json' -p='[
  {"op":"replace","path":"/spec/template/spec/containers/0/startupProbe","value":{"tcpSocket":{"port":8080},"initialDelaySeconds":10,"periodSeconds":5,"failureThreshold":30}},
  {"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe","value":{"tcpSocket":{"port":8080},"initialDelaySeconds":30,"periodSeconds":5}},
  {"op":"replace","path":"/spec/template/spec/containers/0/livenessProbe","value":{"tcpSocket":{"port":8080},"initialDelaySeconds":60,"periodSeconds":10}}
]'
```

Option 2: Use separate management port:
```bash
kubectl patch configmap -n shopping-cart-apps order-service-config --type='json' \
  -p='[{"op":"add","path":"/data/MANAGEMENT_SERVER_PORT","value":"8081"}]'
```

---

## Quick Reference Commands

```bash
# Overall status
make apps-status

# Check CPU
make debug-cpu

# Check disk
make debug-disk

# View logs
make apps-logs-order
make apps-logs-catalog
make apps-logs-basket

# Restart services
make apps-restart-all

# Scale down non-essential
make debug-scale-down

# Unseal Vault
make debug-vault-unseal
```

---

## Prevention Checklist

Before deploying:
1. Check disk usage < 80%
2. Check CPU allocation < 80%
3. Verify Vault is unsealed
4. Ensure RabbitMQ is running
5. Verify database connectivity
6. Check that secrets have correct values
7. Confirm image names match k3s imported images

After deploying:
1. Watch pod status: `kubectl get pods -n shopping-cart-apps -w`
2. Check logs for startup errors
3. Test health endpoints
4. Verify service connectivity
