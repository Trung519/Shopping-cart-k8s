# Redis Password Rotation

This document describes how Redis passwords are managed via Vault and how to rotate them.

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Vault     │────▶│ ExternalSecrets │────▶│  K8s Secret     │
│  (KV Store) │     │   Operator      │     │ redis-cart-secret│
└─────────────┘     └─────────────────┘     └────────┬────────┘
                                                      │
                                                      ▼
                                            ┌─────────────────┐
                                            │ Basket Service  │
                                            │ (reads password)│
                                            └─────────────────┘
```

## Credential Storage

| Component | Vault Path | K8s Secret | Namespace |
|-----------|------------|------------|-----------|
| Redis Cart | `secret/data/redis/cart` | `redis-cart-secret` | `shopping-cart-data` |
| Redis Orders Cache | `secret/data/redis/orders-cache` | `redis-orders-cache-secret` | `shopping-cart-data` |

## Manual Rotation

### Using the Rotation Script

```bash
# Rotate Redis cart password
./bin/rotate-redis-password.sh --instance cart

# Rotate and restart dependent services
./bin/rotate-redis-password.sh --instance cart --restart-services

# Dry run (show what would be done)
./bin/rotate-redis-password.sh --instance cart --dry-run

# Rotate orders-cache Redis
./bin/rotate-redis-password.sh --instance orders-cache --restart-services
```

### Manual Steps

If the script is unavailable, follow these steps:

1. **Generate new password:**
   ```bash
   NEW_PASSWORD=$(openssl rand -base64 32 | tr -dc 'a-zA-Z0-9' | head -c 32)
   echo "New password: $NEW_PASSWORD"
   ```

2. **Update Vault:**
   ```bash
   vault kv put secret/redis/cart password="$NEW_PASSWORD"
   ```

3. **Update Redis directly (optional but recommended):**
   ```bash
   # Port-forward to Redis
   kubectl port-forward -n shopping-cart-data svc/redis-cart 6379:6379 &

   # Get current password
   CURRENT=$(kubectl get secret -n shopping-cart-data redis-cart-secret -o jsonpath='{.data.password}' | base64 -d)

   # Update Redis password
   redis-cli -a "$CURRENT" CONFIG SET requirepass "$NEW_PASSWORD"
   ```

4. **Trigger ExternalSecret refresh:**
   ```bash
   kubectl annotate externalsecret -n shopping-cart-data redis-cart \
     --overwrite force-sync="$(date +%s)"
   ```

5. **Restart dependent services:**
   ```bash
   kubectl rollout restart deployment/basket-service -n shopping-cart-apps
   ```

## Automatic Rotation

For automatic rotation, you can create a Kubernetes CronJob:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: redis-password-rotation
  namespace: shopping-cart-data
spec:
  schedule: "0 2 1 * *"  # 2 AM on 1st of each month
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: password-rotator
          containers:
            - name: rotator
              image: bitnami/kubectl:latest
              command: ["/bin/bash", "-c"]
              args:
                - |
                  # Rotation logic here
                  # (requires vault CLI in image)
          restartPolicy: OnFailure
```

## Retrieving Current Password

```bash
# From K8s secret
kubectl get secret -n shopping-cart-data redis-cart-secret \
  -o jsonpath='{.data.password}' | base64 -d

# From Vault
vault kv get -field=password secret/redis/cart
```

## Troubleshooting

### ExternalSecret Not Syncing

Check ExternalSecret status:
```bash
kubectl get externalsecret -n shopping-cart-data redis-cart -o yaml
kubectl describe externalsecret -n shopping-cart-data redis-cart
```

### Application Can't Connect After Rotation

1. Verify secret was updated:
   ```bash
   kubectl get secret -n shopping-cart-data redis-cart-secret -o jsonpath='{.data.password}' | base64 -d
   ```

2. Verify Redis has new password:
   ```bash
   kubectl port-forward -n shopping-cart-data svc/redis-cart 6379:6379 &
   redis-cli -a "<new-password>" PING
   ```

3. Restart the application:
   ```bash
   kubectl rollout restart deployment/basket-service -n shopping-cart-apps
   ```

### Rollback

If rotation fails, restore the previous password:

1. Get previous password from Vault history (if enabled)
2. Or restore from backup
3. Update both Vault and Redis
4. Trigger ExternalSecret refresh
5. Restart applications

## Security Considerations

- Passwords are never logged
- Vault audit logging tracks all secret access
- ExternalSecrets uses K8s service account auth to Vault
- Applications never directly access Vault (use K8s secrets)
- Password complexity: 32 chars, alphanumeric
