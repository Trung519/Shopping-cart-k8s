#!/usr/bin/env bash
# Import container images to k3s
# Usage: sudo ./import-images.sh

set -euo pipefail

echo "==> Importing container images to k3s..."

for image in order product-catalog basket; do
    tar_file="/tmp/shopping-cart-${image}.tar"
    if [[ -f "$tar_file" ]]; then
        echo "    Importing shopping-cart-${image}..."
        k3s ctr images import "$tar_file"
        echo "    ✓ Imported"
        rm -f "$tar_file"
    else
        echo "    ⚠ $tar_file not found, skipping"
    fi
done

echo ""
echo "==> Verifying imported images..."
k3s ctr images ls | grep -E 'shopping-cart' || echo "No shopping-cart images found"

echo ""
echo "==> Done!"
