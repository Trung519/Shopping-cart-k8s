# Container Image Workflow - GitHub Container Registry

This guide explains how to create container images for the Shopping Cart application services and push them to GitHub Container Registry (GHCR).

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [GHCR Authentication](#ghcr-authentication)
4. [Building Images Locally](#building-images-locally)
5. [GitHub Actions Workflow](#github-actions-workflow)
6. [Image Naming Convention](#image-naming-convention)
7. [Testing the Workflow](#testing-the-workflow)

## Overview

The Shopping Cart microservices architecture requires container images for each application service:

- **product-catalog** (Node.js) - Product browsing and search
- **shopping-cart** (Python) - Cart session management
- **order-service** (Java/Spring Boot) - Order processing
- **payment-service** (Go) - Payment transactions

Each service repository will:
1. Build a container image on every push/PR
2. Tag images with git commit SHA and branch name
3. Push to GHCR: `ghcr.io/<username>/<service>:<tag>`
4. Trigger infrastructure repo update (via Jenkins)

## Prerequisites

### Required Tools

```bash
# Docker
docker --version  # Docker version 20.10+

# GitHub CLI (for authentication)
gh --version  # gh version 2.0+

# Git
git --version  # git version 2.30+
```

### Required Secrets

For local development:
- GitHub Personal Access Token (PAT) with `write:packages` scope

For GitHub Actions:
- `GITHUB_TOKEN` (automatically provided)
- `JENKINS_WEBHOOK_URL` (for triggering Jenkins builds)
- `JENKINS_WEBHOOK_TOKEN` (for webhook authentication)

## GHCR Authentication

### Local Authentication

GitHub Container Registry uses your GitHub credentials for authentication.

#### Option 1: Using GitHub CLI (Recommended)

```bash
# Login to GitHub CLI
gh auth login

# Authenticate Docker with GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

#### Option 2: Using Personal Access Token

1. Create PAT at https://github.com/settings/tokens/new
   - Scopes: `write:packages`, `read:packages`, `delete:packages`
   - Note: "GHCR Access for Shopping Cart"

2. Save token to environment:
   ```bash
   export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
   ```

3. Login to GHCR:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
   ```

4. Verify authentication:
   ```bash
   docker pull ghcr.io/USERNAME/test-image:latest 2>&1 | grep -q "unauthorized" && echo "Not authenticated" || echo "Authenticated"
   ```

### GitHub Actions Authentication

GitHub Actions provides `GITHUB_TOKEN` automatically:

```yaml
- name: Login to GHCR
  uses: docker/login-action@v3
  with:
    registry: ghcr.io
    username: ${{ github.actor }}
    password: ${{ secrets.GITHUB_TOKEN }}
```

## Building Images Locally

### Sample Dockerfile (Node.js - Product Catalog)

```dockerfile
# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy application code
COPY . .

# Production stage
FROM node:18-alpine

WORKDIR /app

# Copy dependencies from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app .

# Create non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app

USER nodejs

EXPOSE 3000

CMD ["node", "server.js"]
```

### Build and Tag Image

```bash
# Navigate to service repository
cd shopping-cart-product-catalog

# Build image
docker build -t ghcr.io/USERNAME/product-catalog:latest .

# Tag with commit SHA
GIT_SHA=$(git rev-parse --short HEAD)
docker tag ghcr.io/USERNAME/product-catalog:latest \
           ghcr.io/USERNAME/product-catalog:${GIT_SHA}

# Tag with version
docker tag ghcr.io/USERNAME/product-catalog:latest \
           ghcr.io/USERNAME/product-catalog:v1.0.0
```

### Push Image to GHCR

```bash
# Push all tags
docker push ghcr.io/USERNAME/product-catalog:latest
docker push ghcr.io/USERNAME/product-catalog:${GIT_SHA}
docker push ghcr.io/USERNAME/product-catalog:v1.0.0
```

### Verify Image in GHCR

```bash
# List tags for image
gh api -H "Accept: application/vnd.github+json" \
  /user/packages/container/product-catalog/versions

# Pull image to verify
docker pull ghcr.io/USERNAME/product-catalog:latest
```

## GitHub Actions Workflow

### Complete Workflow Example

Create `.github/workflows/build-push.yml` in each service repository:

```yaml
name: Build and Push Container Image

on:
  push:
    branches:
      - main
      - develop
  pull_request:
    branches:
      - main
  release:
    types: [published]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Login to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ${{ env.REGISTRY }}
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
          tags: |
            # Git short SHA
            type=sha,prefix={{branch}}-,format=short
            # Branch name
            type=ref,event=branch
            # Semantic version on release
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            # Latest tag for main branch
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Trigger Jenkins Pipeline
        if: github.ref == 'refs/heads/main'
        run: |
          curl -X POST ${{ secrets.JENKINS_WEBHOOK_URL }} \
            -H "Authorization: Bearer ${{ secrets.JENKINS_WEBHOOK_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{
              "service": "${{ github.event.repository.name }}",
              "image_tag": "${{ steps.meta.outputs.version }}",
              "git_sha": "${{ github.sha }}",
              "git_ref": "${{ github.ref }}"
            }'

      - name: Image digest
        run: echo ${{ steps.meta.outputs.digest }}
```

### Workflow Features

1. **Multi-tag strategy**: Automatically creates tags for SHA, branch, version, and latest
2. **Cache optimization**: Uses GitHub Actions cache for faster builds
3. **Security**: Only pushes on main branch or releases
4. **Jenkins integration**: Triggers deployment pipeline after successful push
5. **Metadata extraction**: Automatic version/tag management

## Image Naming Convention

### Repository Structure

```
ghcr.io/USERNAME/SERVICE:TAG
```

Examples:
```
ghcr.io/john/product-catalog:latest
ghcr.io/john/product-catalog:main-a1b2c3d
ghcr.io/john/product-catalog:develop-e4f5g6h
ghcr.io/john/product-catalog:v1.2.3
ghcr.io/john/shopping-cart:latest
ghcr.io/john/order-service:latest
ghcr.io/john/payment-service:latest
```

### Tag Strategy

| Tag Pattern | Description | Example | When Applied |
|------------|-------------|---------|--------------|
| `latest` | Most recent main build | `latest` | Every push to main |
| `main-{sha}` | Main branch commit | `main-a1b2c3d` | Every push to main |
| `develop-{sha}` | Develop branch commit | `develop-e4f5g6h` | Every push to develop |
| `v{major}.{minor}.{patch}` | Semantic version | `v1.2.3` | GitHub release |
| `v{major}.{minor}` | Minor version | `v1.2` | GitHub release |

### Helm Values Reference

In `helm/shopping-cart/values.yaml`:

```yaml
productCatalog:
  image:
    repository: ghcr.io/USERNAME/product-catalog
    tag: "v1.2.3"  # Updated by Jenkins
    pullPolicy: IfNotPresent

shoppingCart:
  image:
    repository: ghcr.io/USERNAME/shopping-cart
    tag: "v1.2.3"
    pullPolicy: IfNotPresent
```

## Testing the Workflow

### 1. Create Test Repository

```bash
# Create new repository
mkdir shopping-cart-product-catalog
cd shopping-cart-product-catalog
git init

# Create sample application
cat > server.js << 'EOF'
const express = require('express');
const app = express();
const port = 3000;

app.get('/', (req, res) => {
  res.json({
    service: 'product-catalog',
    version: '1.0.0',
    status: 'healthy'
  });
});

app.listen(port, () => {
  console.log(`Product Catalog listening on port ${port}`);
});
EOF

# Create package.json
cat > package.json << 'EOF'
{
  "name": "product-catalog",
  "version": "1.0.0",
  "description": "Shopping Cart Product Catalog Service",
  "main": "server.js",
  "scripts": {
    "start": "node server.js"
  },
  "dependencies": {
    "express": "^4.18.2"
  }
}
EOF

# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM node:18-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .

FROM node:18-alpine
WORKDIR /app
COPY --from=builder /app .
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001 && \
    chown -R nodejs:nodejs /app
USER nodejs
EXPOSE 3000
CMD ["node", "server.js"]
EOF

# Create .dockerignore
cat > .dockerignore << 'EOF'
node_modules
npm-debug.log
.git
.github
.env
*.md
EOF
```

### 2. Test Local Build

```bash
# Build image
docker build -t ghcr.io/USERNAME/product-catalog:test .

# Run container
docker run -d -p 3000:3000 --name test-catalog ghcr.io/USERNAME/product-catalog:test

# Test endpoint
curl http://localhost:3000

# Expected output:
# {"service":"product-catalog","version":"1.0.0","status":"healthy"}

# Cleanup
docker stop test-catalog
docker rm test-catalog
```

### 3. Test GHCR Push

```bash
# Login to GHCR
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin

# Push image
docker push ghcr.io/USERNAME/product-catalog:test

# Verify in GitHub UI
# Navigate to: https://github.com/USERNAME?tab=packages
# You should see 'product-catalog' package listed

# Pull image from GHCR
docker pull ghcr.io/USERNAME/product-catalog:test
```

### 4. Create GitHub Repository and Test Actions

```bash
# Create remote repository
gh repo create shopping-cart-product-catalog --public --source=. --remote=origin

# Create GitHub Actions workflow
mkdir -p .github/workflows
cp /path/to/build-push.yml .github/workflows/

# Commit and push
git add .
git commit -m "Initial commit with GitHub Actions workflow"
git push -u origin main

# Monitor workflow
gh run watch

# View workflow logs
gh run view --log
```

### 5. Verify Image Tags

```bash
# List all tags for the image
gh api -H "Accept: application/vnd.github+json" \
  /user/packages/container/product-catalog/versions | \
  jq -r '.[].metadata.container.tags[]'

# Expected output:
# latest
# main-a1b2c3d
```

### 6. Test Image Pull in Kubernetes

```bash
# Create test namespace
kubectl create namespace test-images

# Create image pull secret
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=USERNAME \
  --docker-password=$GITHUB_TOKEN \
  --docker-email=email@example.com \
  -n test-images

# Create test pod
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: product-catalog-test
  namespace: test-images
spec:
  containers:
  - name: product-catalog
    image: ghcr.io/USERNAME/product-catalog:latest
    ports:
    - containerPort: 3000
  imagePullSecrets:
  - name: ghcr-secret
EOF

# Wait for pod to be ready
kubectl wait --for=condition=ready pod/product-catalog-test -n test-images --timeout=60s

# Test service
kubectl port-forward -n test-images pod/product-catalog-test 3000:3000 &
curl http://localhost:3000

# Cleanup
kubectl delete namespace test-images
```

## Automation Script

Create `scripts/build-and-push.sh` for local testing:

```bash
#!/usr/bin/env bash
# Build and push container image to GHCR

set -euo pipefail

# Configuration
REGISTRY="ghcr.io"
USERNAME="${GITHUB_USERNAME:-$(gh api user -q .login)}"
SERVICE_NAME="${1:-product-catalog}"
TAG="${2:-test}"

IMAGE_NAME="${REGISTRY}/${USERNAME}/${SERVICE_NAME}:${TAG}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Building ${IMAGE_NAME}${NC}"

# Build image
docker build -t "${IMAGE_NAME}" .

echo -e "${GREEN}✓ Build complete${NC}"
echo -e "${YELLOW}Pushing to GHCR${NC}"

# Authenticate if not already logged in
if ! docker info 2>/dev/null | grep -q "Username:"; then
    echo -e "${YELLOW}Logging in to GHCR${NC}"
    echo "${GITHUB_TOKEN}" | docker login ghcr.io -u "${USERNAME}" --password-stdin
fi

# Push image
docker push "${IMAGE_NAME}"

echo -e "${GREEN}✓ Push complete${NC}"
echo -e "${GREEN}Image available at: ${IMAGE_NAME}${NC}"

# Tag with git SHA if in git repo
if git rev-parse --git-dir > /dev/null 2>&1; then
    GIT_SHA=$(git rev-parse --short HEAD)
    SHA_TAG="${REGISTRY}/${USERNAME}/${SERVICE_NAME}:${GIT_SHA}"

    echo -e "${YELLOW}Tagging with git SHA: ${SHA_TAG}${NC}"
    docker tag "${IMAGE_NAME}" "${SHA_TAG}"
    docker push "${SHA_TAG}"

    echo -e "${GREEN}✓ SHA tag pushed: ${SHA_TAG}${NC}"
fi
```

### Usage

```bash
# Make executable
chmod +x scripts/build-and-push.sh

# Build and push with default tag (test)
./scripts/build-and-push.sh product-catalog

# Build and push with specific tag
./scripts/build-and-push.sh product-catalog v1.0.0

# Build and push with latest tag
./scripts/build-and-push.sh product-catalog latest
```

## Troubleshooting

### Common Issues

#### 1. Authentication Failed

```
Error: denied: permission_denied
```

**Solution**:
```bash
# Verify token has correct scopes
gh auth status

# Re-login if needed
gh auth login --scopes write:packages,read:packages

# Get new token
export GITHUB_TOKEN=$(gh auth token)

# Login to Docker
echo $GITHUB_TOKEN | docker login ghcr.io -u USERNAME --password-stdin
```

#### 2. Image Not Found After Push

```
Error: manifest unknown
```

**Solution**:
- Verify package visibility (public vs private)
- Check package permissions in GitHub settings
- Ensure correct username/organization in image name

#### 3. Rate Limiting

```
Error: toomanyrequests: too many requests
```

**Solution**:
- Use authenticated pulls (docker login)
- Implement pull-through cache
- Use layer caching in GitHub Actions

#### 4. Large Image Size

**Optimization strategies**:
- Use multi-stage builds
- Use Alpine-based images
- Minimize layers (.dockerignore)
- Remove dev dependencies in production stage

## Next Steps

1. **Create service repositories**: Set up GitHub repos for each microservice
2. **Add GitHub Actions workflows**: Copy workflow template to each repo
3. **Configure secrets**: Add `JENKINS_WEBHOOK_URL` and `JENKINS_WEBHOOK_TOKEN`
4. **Test end-to-end**: Push code → Build image → Trigger Jenkins → Deploy via Argo CD
5. **Set up image scanning**: Add Trivy or Snyk for vulnerability scanning
6. **Configure image signing**: Use Cosign for supply chain security

## References

- [GitHub Container Registry Documentation](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [Docker Login Action](https://github.com/docker/login-action)
- [Docker Metadata Action](https://github.com/docker/metadata-action)
