# Troubleshooting — Shopping Cart Frontend

## Local Dev

### Blank page / OIDC redirect loop

**Cause:** Keycloak not running or `VITE_KEYCLOAK_URL` incorrect.

**Fix:**
1. Confirm Keycloak is running: `kubectl get pods -n identity`
2. Check `.env.local` has the correct `VITE_KEYCLOAK_URL`
3. Confirm the `frontend` client exists in the `shopping-cart` realm with the correct redirect URI

---

### `npm run dev` fails with `EADDRINUSE`

Port 3000 already in use.

```bash
lsof -i :3000 | grep LISTEN
kill -9 <pid>
```

---

### TypeScript errors after `git pull`

New types added — regenerate:

```bash
npm install
npx tsc --noEmit
```

---

### E2E tests fail locally (`npx playwright install` not run)

```bash
npm run playwright:install
npm run test:e2e
```

---

## CI

### `npm audit` reports vulnerabilities (Security Scan job)

Security Scan has `continue-on-error: true` — it will not block the build. Review the
audit output in the job logs and open an issue for any high/critical findings.

### E2E job fails in CI but passes locally

API mocking is done inside the E2E spec files via `page.route(...)` (see `e2e/*.spec.ts`).
Check that the route intercepts match the actual request paths made by the component under test.

---

## Kubernetes / ArgoCD

### Pod in `ImagePullBackOff`

Image not yet pushed to ghcr.io or kustomization.yaml has a stale tag.

```bash
kubectl describe pod <pod-name> -n shopping-cart-apps
# Check "Failed to pull image" message for the exact tag

# Verify image exists in ghcr.io
gh api /user/packages/container/shopping-cart-frontend/versions --jq '.[0]'
```

If the tag is stale, update `config-secret-secure/values/local/20-frontend.yaml` and redeploy the Helm release.

### App shows `Degraded` in ArgoCD

```bash
kubectl get application shopping-cart-frontend -n cicd -o yaml | grep -A10 conditions
kubectl get pods -n shopping-cart-apps -l app.kubernetes.io/name=frontend
kubectl logs -n shopping-cart-apps -l app.kubernetes.io/name=frontend --previous
```

### Nginx returns 502 for API calls

Backend pod not ready or Kubernetes service DNS unreachable. nginx proxies directly to
service DNS names — check that the target pods are Running in `shopping-cart-apps`.

```bash
kubectl get pods -n shopping-cart-apps
kubectl get svc -n shopping-cart-apps
```
