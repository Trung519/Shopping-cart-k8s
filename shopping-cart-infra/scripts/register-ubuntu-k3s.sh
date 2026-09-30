#!/usr/bin/env bash
# register-ubuntu-k3s.sh — Register Ubuntu k3s as an ArgoCD managed cluster
#
# Prerequisites:
#   1. SSH tunnel active: ssh -fNL 0.0.0.0:6443:localhost:6443 ubuntu
#   2. kubectl pointing at infra cluster (k3d-k3d-cluster context)
#   3. ~/.kube/k3s-ubuntu.yaml exists (Ubuntu k3s kubeconfig)
#
# Usage:
#   ./scripts/register-ubuntu-k3s.sh
#   ./scripts/register-ubuntu-k3s.sh --delete   # remove the cluster secret

set -euo pipefail

KUBECONFIG_UBUNTU="${KUBECONFIG_UBUNTU:-$HOME/.kube/k3s-ubuntu.yaml}"
ARGOCD_NAMESPACE="cicd"
CLUSTER_NAME="ubuntu-k3s"
# Use host.k3d.internal so ArgoCD pods inside k3d reach Ubuntu via the SSH tunnel on the host
CLUSTER_SERVER="https://host.k3d.internal:6443"

# Preflight: require python3 and PyYAML
if ! command -v python3 >/dev/null 2>&1; then
  echo "ERROR: python3 is required but not found. Install python3 and retry." >&2
  exit 1
fi
if ! python3 -c "import yaml" 2>/dev/null; then
  echo "ERROR: PyYAML is required. Install with: pip3 install pyyaml" >&2
  exit 1
fi

if [[ "${1:-}" == "--delete" ]]; then
  echo "Removing ArgoCD cluster secret for $CLUSTER_NAME..."
  kubectl delete secret "$CLUSTER_NAME" -n "$ARGOCD_NAMESPACE" --ignore-not-found
  echo "Done."
  exit 0
fi

if [[ ! -f "$KUBECONFIG_UBUNTU" ]]; then
  echo "ERROR: Ubuntu kubeconfig not found at $KUBECONFIG_UBUNTU" >&2
  exit 1
fi

# Verify SSH tunnel is up
if ! curl -sk --max-time 3 https://localhost:6443/version >/dev/null 2>&1; then
  echo "ERROR: k3s API not reachable at localhost:6443 — is the SSH tunnel active?" >&2
  echo "  Run: ssh -fNL 0.0.0.0:6443:localhost:6443 ubuntu" >&2
  exit 1
fi

echo "Extracting credentials from $KUBECONFIG_UBUNTU..."

# Extract cert and key data via file read (not command-line interpolation) to avoid
# exposing secrets in process listings (ps/top).
_tmpfile=$(mktemp)
trap 'rm -f "$_tmpfile"' EXIT

python3 - "$KUBECONFIG_UBUNTU" > "$_tmpfile" <<'EOF'
import sys, json, yaml
with open(sys.argv[1]) as f:
    kc = yaml.safe_load(f)
user = kc['users'][0]['user']
config = {
    'tlsClientConfig': {
        # insecure: true is intentional for this dev/lab environment (self-signed k3s cert).
        # Do NOT use in production — populate caData instead.
        'insecure': True,
        'certData': user['client-certificate-data'],
        'keyData': user['client-key-data'],
    }
}
print(json.dumps(config))
EOF

CONFIG_JSON=$(cat "$_tmpfile")

echo "Applying ArgoCD cluster secret (server: $CLUSTER_SERVER)..."
kubectl create secret generic "$CLUSTER_NAME" \
  --namespace "$ARGOCD_NAMESPACE" \
  --from-literal=name="$CLUSTER_NAME" \
  --from-literal=server="$CLUSTER_SERVER" \
  --from-literal=config="$CONFIG_JSON" \
  --dry-run=client -o yaml \
  | kubectl label --local -f - "argocd.argoproj.io/secret-type=cluster" --dry-run=client -o yaml \
  | kubectl apply -f -

echo ""
echo "Cluster secret applied. Verifying ArgoCD can reach the cluster..."
sleep 3
kubectl get secret "$CLUSTER_NAME" -n "$ARGOCD_NAMESPACE" \
  -o jsonpath='{.metadata.labels}' && echo ""

echo ""
echo "Done. ArgoCD should begin syncing shopping-cart apps within ~30s."
echo "Monitor: kubectl get applications -n $ARGOCD_NAMESPACE -w"
