# GitHub Actions and Jenkins Webhook Setup Guide

Complete step-by-step guide for setting up GitHub Actions workflows with Jenkins webhook integration for the Shopping Cart CI/CD pipeline.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Part 1: GitHub Actions Workflow Setup](#part-1-github-actions-workflow-setup)
4. [Part 2: Jenkins Webhook Configuration](#part-2-jenkins-webhook-configuration)
5. [Part 3: Connecting GitHub to Jenkins](#part-3-connecting-github-to-jenkins)
6. [Part 4: Testing the Integration](#part-4-testing-the-integration)
7. [Troubleshooting](#troubleshooting)

## Overview

The complete CI/CD flow:

```
Developer Push → GitHub Actions → GHCR → Jenkins Webhook → Update Infrastructure Repo → Argo CD → Kubernetes
```

**GitHub Actions** handles:
- Linting and security scanning (on PRs)
- Building container images
- Pushing to GitHub Container Registry (GHCR)
- Triggering Jenkins pipeline

**Jenkins** handles:
- Receiving webhook from GitHub Actions
- Updating infrastructure repository with new image tags
- Committing and pushing changes

**Argo CD** handles:
- Watching infrastructure repository
- Automatically deploying changes to Kubernetes

## Prerequisites

### Required Tools
- GitHub account with repository admin access
- GitHub CLI (`gh`) installed and authenticated
- Jenkins instance accessible from GitHub Actions
- Access to infrastructure repository

### Required Information
- Jenkins URL (e.g., `https://jenkins.example.com`)
- Jenkins webhook endpoint path
- Jenkins authentication token

## Part 1: GitHub Actions Workflow Setup

### Step 1: Copy Workflow Template to Service Repository

For each microservice repository (product-catalog, shopping-cart, order-service, payment-service):

```bash
# Navigate to your service repository
cd shopping-cart-product-catalog

# Create workflows directory
mkdir -p .github/workflows

# The reusable workflow lives in shopping-cart-infra — reference it directly
# See .github/workflows/build-push-deploy.yml in shopping-cart-infra for the template
```

### Step 2: Customize Workflow for Your Service

Edit `.github/workflows/build-push.yml`:

**For Node.js services (product-catalog):**
```yaml
# Line 148 - Update port for health check
if curl -f http://localhost:3000/health || curl -f http://localhost:3000/; then
```

**For Python services (shopping-cart):**
```yaml
# Line 148 - Update port for health check
if curl -f http://localhost:5000/health || curl -f http://localhost:5000/; then
```

**For Java services (order-service):**
```yaml
# Line 148 - Update port for health check
if curl -f http://localhost:8080/actuator/health || curl -f http://localhost:8080/; then
```

**For Go services (payment-service):**
```yaml
# Line 148 - Update port for health check
if curl -f http://localhost:8081/health || curl -f http://localhost:8081/; then
```

### Step 3: Configure GitHub Repository Secrets

Set up required secrets for your service repository:

#### Method 1: Using GitHub CLI (Recommended)

```bash
# Set Jenkins webhook URL
echo "https://jenkins.example.com/generic-webhook-trigger/invoke" | \
  gh secret set JENKINS_WEBHOOK_URL

# Set Jenkins webhook token (generate a random token)
openssl rand -hex 32 | gh secret set JENKINS_WEBHOOK_TOKEN
```

#### Method 2: Using GitHub Web UI

1. Navigate to your repository on GitHub
2. Go to **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add the following secrets:

| Name | Value | Description |
|------|-------|-------------|
| `JENKINS_WEBHOOK_URL` | `https://jenkins.example.com/generic-webhook-trigger/invoke` | Jenkins webhook endpoint |
| `JENKINS_WEBHOOK_TOKEN` | `<random-token>` | Authentication token for webhook |

**Generate a secure token:**
```bash
openssl rand -hex 32
# Example output: a3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3d5e7f9b1c3
```

### Step 4: Enable GitHub Actions

Ensure GitHub Actions are enabled for your repository:

#### Using GitHub CLI:
```bash
gh api repos/:owner/:repo/actions/permissions \
  -X PUT \
  -f enabled=true \
  -f allowed_actions=all
```

#### Using GitHub Web UI:
1. Go to **Settings** → **Actions** → **General**
2. Under **Actions permissions**, select **Allow all actions and reusable workflows**
3. Click **Save**

### Step 5: Commit and Push Workflow

```bash
git add .github/workflows/build-push.yml
git commit -m "ci: add GitHub Actions workflow for container image build/push"
git push origin main
```

### Step 6: Verify Workflow Execution

```bash
# Watch the workflow run
gh run watch

# Or list recent runs
gh run list

# View detailed logs
gh run view --log
```

## Part 2: Jenkins Webhook Configuration

### Step 1: Install Required Jenkins Plugins

Install the **Generic Webhook Trigger** plugin:

#### Via Jenkins Web UI:
1. Navigate to **Manage Jenkins** → **Manage Plugins**
2. Go to **Available** tab
3. Search for "Generic Webhook Trigger"
4. Check the box and click **Install without restart**

#### Via Jenkins CLI:
```bash
jenkins-cli.jar install-plugin generic-webhook-trigger

-plugin -restart
```

### Step 2: Create Jenkins Pipeline Job

#### Option A: Using Jenkins Web UI

1. Go to **New Item**
2. Enter name: `shopping-cart-image-update`
3. Select **Pipeline**
4. Click **OK**

Configure the job:

**General Settings:**
- Description: `Updates infrastructure repo when service images are pushed to GHCR`

**Build Triggers:**
- Check **Generic Webhook Trigger**

**Generic Webhook Trigger Configuration:**

Add these parameters:

| Variable | Expression | JSONPath | Default Value |
|----------|------------|----------|---------------|
| `service` | `$.service` | `$.service` | - |
| `image_tag` | `$.image_tag` | `$.image_tag` | - |
| `git_sha` | `$.git_sha` | `$.git_sha` | - |
| `git_ref` | `$.git_ref` | `$.git_ref` | - |

**Token Configuration:**
- Token: `<your-jenkins-webhook-token>` (same as JENKINS_WEBHOOK_TOKEN secret)

**Pipeline Script:**

```groovy
pipeline {
    agent any

    environment {
        INFRASTRUCTURE_REPO = 'https://github.com/YOUR_USERNAME/shopping-cart-infra.git'
        GIT_CREDENTIAL = 'github-credentials'
        HELM_VALUES_DIR = 'helm/shopping-cart'
    }

    stages {
        stage('Validate Input') {
            steps {
                script {
                    echo "Service: ${service}"
                    echo "Image Tag: ${image_tag}"
                    echo "Git SHA: ${git_sha}"
                    echo "Git Ref: ${git_ref}"

                    if (!service || !image_tag) {
                        error("Missing required parameters: service or image_tag")
                    }
                }
            }
        }

        stage('Clone Infrastructure Repo') {
            steps {
                dir('infrastructure') {
                    git credentialsId: "${GIT_CREDENTIAL}",
                        url: "${INFRASTRUCTURE_REPO}",
                        branch: 'main'
                }
            }
        }

        stage('Update Image Tag') {
            steps {
                dir('infrastructure') {
                    script {
                        // Determine the values file path based on service name
                        def valuesFile = "${HELM_VALUES_DIR}/values.yaml"

                        // Map service name to Helm value path
                        def serviceMap = [
                            'shopping-cart-product-catalog': 'productCatalog.image.tag',
                            'shopping-cart-shopping-cart': 'shoppingCart.image.tag',
                            'shopping-cart-order-service': 'orderService.image.tag',
                            'shopping-cart-payment-service': 'paymentService.image.tag'
                        ]

                        def valuePath = serviceMap[service]
                        if (!valuePath) {
                            error("Unknown service: ${service}")
                        }

                        // Update the image tag using yq
                        sh """
                            yq eval '.${valuePath} = \"${image_tag}\"' -i ${valuesFile}

                            # Verify the change
                            echo "Updated ${valuePath} to ${image_tag}"
                            yq eval '.${valuePath}' ${valuesFile}
                        """
                    }
                }
            }
        }

        stage('Commit and Push') {
            steps {
                dir('infrastructure') {
                    script {
                        sh """
                            git config user.email "jenkins@ci.local"
                            git config user.name "Jenkins CI"

                            git add ${HELM_VALUES_DIR}/values.yaml

                            git commit -m "chore: update ${service} to ${image_tag}

Triggered by GitHub Actions
Git SHA: ${git_sha}
Git Ref: ${git_ref}"

                            git push origin main
                        """
                    }
                }
            }
        }

        stage('Trigger Argo CD Sync') {
            steps {
                script {
                    // Optional: Manually trigger Argo CD sync
                    echo "Argo CD will automatically detect and sync the change"
                    // Or use Argo CD CLI to force sync:
                    // sh 'argocd app sync shopping-cart'
                }
            }
        }
    }

    post {
        success {
            echo "Successfully updated ${service} to ${image_tag}"
        }
        failure {
            echo "Failed to update infrastructure repository"
        }
        always {
            cleanWs()
        }
    }
}
```

#### Option B: Using Jenkins Configuration as Code (JCasC)

Create `jenkins-job-dsl.yaml`:

```yaml
jobs:
  - script: >
      pipelineJob('shopping-cart-image-update') {
        description('Updates infrastructure repo when service images are pushed to GHCR')

        properties {
          pipelineTriggers {
            triggers {
              genericTrigger {
                genericVariables {
                  genericVariable {
                    key("service")
                    value("\$.service")
                  }
                  genericVariable {
                    key("image_tag")
                    value("\$.image_tag")
                  }
                  genericVariable {
                    key("git_sha")
                    value("\$.git_sha")
                  }
                  genericVariable {
                    key("git_ref")
                    value("\$.git_ref")
                  }
                }
                token('${JENKINS_WEBHOOK_TOKEN}')
                printContributedVariables(true)
                printPostContent(true)
                causeString('Triggered by GitHub Actions')
              }
            }
          }
        }

        definition {
          cps {
            script(readFileFromWorkspace('jenkins-pipeline.groovy'))
            sandbox()
          }
        }
      }
```

### Step 3: Configure Jenkins Credentials

Add GitHub credentials for pushing to infrastructure repo:

1. Go to **Manage Jenkins** → **Manage Credentials**
2. Click on **(global)** domain
3. Click **Add Credentials**

Configure:
- **Kind**: Username with password
- **Username**: Your GitHub username
- **Password**: GitHub Personal Access Token (with `repo` scope)
- **ID**: `github-credentials`
- **Description**: GitHub access for infrastructure repo updates

**Create GitHub PAT:**
```bash
# Using GitHub CLI
gh auth token

# Or create at: https://github.com/settings/tokens/new
# Required scopes: repo, workflow
```

### Step 4: Test Jenkins Webhook Endpoint

Test the webhook endpoint manually:

```bash
curl -X POST 'https://jenkins.example.com/generic-webhook-trigger/invoke?token=YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "service": "shopping-cart-product-catalog",
    "image_tag": "main-abc1234",
    "git_sha": "abc1234567890",
    "git_ref": "refs/heads/main"
  }'
```

Expected response:
```json
{
  "jobs": {
    "shopping-cart-image-update": {
      "triggered": true,
      "url": "queue/item/123/"
    }
  }
}
```

## Part 3: Connecting GitHub to Jenkins

### Step 1: Verify Webhook URL Format

Your Jenkins webhook URL should be:
```
https://jenkins.example.com/generic-webhook-trigger/invoke?token=YOUR_TOKEN
```

Or for token in header:
```
https://jenkins.example.com/generic-webhook-trigger/invoke
# With header: Authorization: Bearer YOUR_TOKEN
```

### Step 2: Update GitHub Actions Workflow (if needed)

The workflow template already includes webhook trigger code. Verify it matches your setup:

```yaml
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
        "git_ref": "${{ github.ref }}",
        "git_author": "${{ github.actor }}",
        "commit_message": "${{ github.event.head_commit.message }}"
      }'
```

### Step 3: Expose Jenkins Endpoint (if needed)

If Jenkins is running in Kubernetes behind Istio:

**Option A: Use Istio VirtualService**

Already configured if you used `./scripts/k3d-manager deploy_jenkins`

**Option B: Use ngrok for local testing**

```bash
# Install ngrok
brew install ngrok  # macOS
# or
sudo snap install ngrok  # Linux

# Expose Jenkins
ngrok http https://jenkins.dev.local.me:443

# Update JENKINS_WEBHOOK_URL secret with ngrok URL
echo "https://YOUR_ID.ngrok.io/generic-webhook-trigger/invoke" | \
  gh secret set JENKINS_WEBHOOK_URL
```

**Option C: Use Cloudflare Tunnel**

```bash
# Install cloudflared
brew install cloudflared

# Create tunnel
cloudflared tunnel create jenkins-webhook

# Configure tunnel
cloudflared tunnel route dns jenkins-webhook jenkins.yourdomain.com

# Run tunnel
cloudflared tunnel run jenkins-webhook
```

## Part 4: Testing the Integration

### End-to-End Test

1. **Make a code change** in your service repository:

```bash
cd shopping-cart-product-catalog

# Make a simple change
echo "// Test change" >> src/server.js

# Commit and push
git add src/server.js
git commit -m "test: trigger CI/CD pipeline"
git push origin main
```

2. **Watch GitHub Actions**:

```bash
gh run watch
```

Expected output:
```
✓ Lint and Security Scan
✓ Build and Push Image
✓ Test Container Image
✓ Trigger Jenkins Pipeline
```

3. **Check Jenkins Job**:

Visit: `https://jenkins.example.com/job/shopping-cart-image-update/`

Verify:
- Job was triggered
- Parameters received correctly
- Infrastructure repo was updated
- Changes were committed and pushed

4. **Verify Infrastructure Repo Update**:

```bash
cd shopping-cart-infra
git pull origin main

# Check the updated values
cat helm/shopping-cart/values.yaml | grep -A 2 "productCatalog:"
```

Expected:
```yaml
productCatalog:
  image:
    tag: "main-abc1234"  # <- Updated!
```

5. **Check Argo CD Sync**:

```bash
# View Argo CD application status
argocd app get shopping-cart

# Check sync status
argocd app sync shopping-cart
```

6. **Verify Deployment in Kubernetes**:

```bash
# Check pods are using new image
kubectl get pods -n shopping-cart-apps -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.containers[*].image}{"\n"}{end}'
```

## Troubleshooting

### GitHub Actions Issues

#### Workflow Not Triggering

**Problem**: Workflow doesn't run on push

**Solutions**:
```bash
# Check workflow syntax
gh workflow view build-push.yml

# Check if Actions are enabled
gh api repos/:owner/:repo/actions/permissions

# Enable Actions
gh api repos/:owner/:repo/actions/permissions \
  -X PUT -f enabled=true -f allowed_actions=all
```

#### Image Push Fails

**Problem**: `denied: permission_denied`

**Solutions**:
```bash
# Re-authenticate GitHub CLI
gh auth login --scopes write:packages,read:packages

# Verify token
gh auth status

# Check package visibility
gh api /user/packages/container/YOUR_SERVICE
```

#### Webhook Call Fails

**Problem**: Webhook returns 4xx or 5xx

**Solutions**:
```bash
# Test webhook manually
curl -v -X POST "${JENKINS_WEBHOOK_URL}?token=${JENKINS_WEBHOOK_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"service":"test","image_tag":"test"}'

# Check if Jenkins is accessible
curl -I https://jenkins.example.com

# Verify firewall/network rules
# Ensure Jenkins allows incoming connections from GitHub Actions IPs
```

### Jenkins Issues

#### Webhook Not Triggering Job

**Problem**: Webhook received but job doesn't trigger

**Solutions**:
1. Check Jenkins logs: `/var/log/jenkins/jenkins.log`
2. Verify Generic Webhook Trigger plugin is installed
3. Check token matches exactly (no extra spaces/quotes)
4. Enable debug logging in Jenkins:
   ```groovy
   // In Jenkins Script Console
   import java.util.logging.Logger
   Logger.getLogger("org.jenkinsci.plugins.gwt").setLevel(java.util.logging.Level.FINE)
   ```

#### Git Push Fails

**Problem**: `fatal: could not read Username`

**Solutions**:
1. Verify GitHub credentials are configured
2. Test credential:
   ```groovy
   // Jenkins Script Console
   def creds = com.cloudbees.plugins.credentials.CredentialsProvider.lookupCredentials(
     com.cloudbees.plugins.credentials.common.StandardUsernamePasswordCredentials.class,
     Jenkins.instance,
     null,
     null
   )
   println(creds)
   ```
3. Check PAT has `repo` scope
4. Regenerate PAT if expired

#### yq Command Not Found

**Problem**: `yq: command not found`

**Solutions**:
```bash
# Install yq in Jenkins agent
# Add to Jenkins Docker image or install via init script
wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64 \
  -O /usr/local/bin/yq && chmod +x /usr/local/bin/yq
```

### Integration Issues

#### Changes Not Syncing to Kubernetes

**Problem**: Infrastructure updated but pods not redeployed

**Solutions**:
```bash
# Check Argo CD application status
argocd app get shopping-cart

# Force sync
argocd app sync shopping-cart --force

# Check Argo CD logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-application-controller

# Verify Argo CD is watching correct branch
argocd app set shopping-cart --revision main
```

## Security Best Practices

1. **Use Strong Tokens**: Generate cryptographically random tokens
   ```bash
   openssl rand -hex 32
   ```

2. **Rotate Tokens Regularly**: Update every 90 days
   ```bash
   # Generate new token
   NEW_TOKEN=$(openssl rand -hex 32)

   # Update GitHub secret
   echo "$NEW_TOKEN" | gh secret set JENKINS_WEBHOOK_TOKEN

   # Update Jenkins job configuration
   ```

3. **Limit Token Scope**: Use minimal required permissions
   - GitHub: `write:packages`, `repo` (for infrastructure updates only)
   - Jenkins: Specific job trigger permission only

4. **Use HTTPS**: Always use encrypted connections
   - Jenkins behind TLS/SSL
   - Webhook URLs with https://

5. **IP Whitelisting**: Restrict webhook access
   ```nginx
   # Nginx config
   location /generic-webhook-trigger/ {
     allow 140.82.112.0/20;  # GitHub Actions IP range
     deny all;
   }
   ```

6. **Audit Logs**: Enable and review
   - GitHub Actions: Settings → Actions → General → Workflow permissions
   - Jenkins: Audit Trail plugin

## Next Steps

1. Set up additional service repositories following this guide
2. Configure Argo CD applications for each service
3. Add monitoring for webhook success/failure rates
4. Set up alerting for failed deployments
5. Document rollback procedures

## Additional Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Generic Webhook Trigger Plugin](https://plugins.jenkins.io/generic-webhook-trigger/)
- [Argo CD Documentation](https://argo-cd.readthedocs.io/)
- [Container Image Workflow Guide](./container-image-workflow.md)
- [CI/CD Architecture](./cicd-architecture.md)
