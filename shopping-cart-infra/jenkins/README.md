# Jenkins Pipeline Configuration

This directory contains Jenkins pipeline configuration for the Shopping Cart infrastructure.

## Overview

The Jenkins pipeline automates the deployment workflow:

1. **GitHub Actions** builds and pushes container images to GHCR
2. **GitHub Actions webhook** triggers Jenkins with image metadata
3. **Jenkins pipeline** updates Helm values in this repository
4. **Argo CD** detects changes and syncs deployments to Kubernetes

## Files

### Jenkinsfile.update-image

Production-ready pipeline that:
- Receives webhook from GitHub Actions
- Updates Helm chart values with new image tags
- Commits and pushes changes to this repository
- Triggers Argo CD sync

## Setup Instructions

### Prerequisites

1. **Jenkins Installation**
   - Jenkins 2.300+ with Pipeline support
   - Required plugins:
     - Generic Webhook Trigger Plugin
     - Git Plugin
     - Pipeline Plugin
     - Credentials Plugin

2. **Tools Installation**
   ```bash
   # Install yq on Jenkins agent
   wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
   chmod +x /usr/local/bin/yq
   ```

3. **GitHub Credentials**
   - Create GitHub Personal Access Token with `repo` scope
   - Add to Jenkins credentials as "github-credentials"

### Step 1: Create Jenkins Pipeline Job

1. Navigate to Jenkins dashboard
2. Click "New Item"
3. Enter name: `shopping-cart-image-update`
4. Select "Pipeline" project type
5. Click "OK"

### Step 2: Configure Generic Webhook Trigger

In the job configuration:

1. Check "Generic Webhook Trigger"

2. Add Post Content Parameters:
   ```
   Variable: service
   Expression: $.service
   JSONPath

   Variable: image_tag
   Expression: $.image_tag
   JSONPath

   Variable: git_sha
   Expression: $.git_sha
   JSONPath

   Variable: git_ref
   Expression: $.git_ref
   JSONPath

   Variable: git_author
   Expression: $.git_author
   JSONPath

   Variable: commit_message
   Expression: $.commit_message
   JSONPath
   ```

3. Set Token: `shopping-cart-webhook-token` (or your preferred token)

4. Enable "Print post content" and "Print contributed variables" (for debugging)

### Step 3: Configure Pipeline from SCM

In the Pipeline section:

1. **Definition**: Pipeline script from SCM
2. **SCM**: Git
3. **Repository URL**: `https://github.com/USERNAME/shopping-cart-infra.git`
4. **Credentials**: Select your GitHub credentials
5. **Branch**: `*/main`
6. **Script Path**: `jenkins/Jenkinsfile.update-image`

### Step 4: Update Pipeline Variables

Edit `jenkins/Jenkinsfile.update-image` and update:

```groovy
environment {
    INFRASTRUCTURE_REPO = 'https://github.com/YOUR_USERNAME/shopping-cart-infra.git'
    GIT_CREDENTIAL = 'github-credentials'  // Your Jenkins credential ID
}
```

And in the "Commit and Push" stage, update the push URL:
```groovy
git push https://\${GIT_USERNAME}:\${GIT_PASSWORD}@github.com/YOUR_USERNAME/shopping-cart-infra.git
```

### Step 5: Test the Webhook

**Webhook URL Format:**
```
https://your-jenkins.com/generic-webhook-trigger/invoke?token=shopping-cart-webhook-token
```

**Test with curl:**
```bash
curl -X POST https://your-jenkins.com/generic-webhook-trigger/invoke?token=shopping-cart-webhook-token \
  -H "Content-Type: application/json" \
  -d '{
    "service": "shopping-cart-product-catalog",
    "image_tag": "main-abc1234",
    "git_sha": "abc1234567890",
    "git_ref": "refs/heads/main",
    "git_author": "testuser",
    "commit_message": "test: trigger pipeline"
  }'
```

### Step 6: Configure GitHub Actions

Update your application repository's GitHub Actions secrets:

```bash
# In your application repository (e.g., shopping-cart-product-catalog)
gh secret set JENKINS_WEBHOOK_URL --body "https://your-jenkins.com/generic-webhook-trigger/invoke?token=shopping-cart-webhook-token"
gh secret set JENKINS_WEBHOOK_TOKEN --body "shopping-cart-webhook-token"
```

## Pipeline Behavior

### Supported Services

The pipeline supports these service repositories:

| Repository Name                      | Helm Value Path                |
|--------------------------------------|--------------------------------|
| shopping-cart-product-catalog        | productCatalog.image.tag       |
| shopping-cart-shopping-cart          | shoppingCart.image.tag         |
| shopping-cart-order-service          | orderService.image.tag         |
| shopping-cart-payment-service        | paymentService.image.tag       |
| shopping-cart-frontend               | frontend.image.tag             |

### Branch Filtering

- Only processes pushes to `main` branch
- Ignores `develop`, `feature/*`, and other branches
- Skips execution if not main branch (returns success)

### Helm Values Update

Updates `chart/values-dev.yaml` by default. For production:

1. Modify `HELM_VALUES_FILE` in pipeline environment
2. Or create a separate pipeline for production updates

### Commit Message Format

```
chore(service): update image to main-abc1234

Automated update from Jenkins CI/CD pipeline

- Service: shopping-cart-product-catalog
- Image Tag: main-abc1234
- Source Commit: abc1234567890
- Author: developer
- Source Commit Message: feat: add new feature

Triggered by GitHub Actions webhook
```

## Troubleshooting

### Pipeline Fails with "yq: command not found"

**Solution**: Install yq on Jenkins agent
```bash
wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64
chmod +x /usr/local/bin/yq
```

### Pipeline Fails with "Permission denied" on git push

**Solution**: Check GitHub credentials
1. Verify Personal Access Token has `repo` scope
2. Verify credential ID matches `GIT_CREDENTIAL` in pipeline
3. Test credentials: Jenkins → Credentials → Test connection

### Webhook Not Triggering Pipeline

**Solution**: Check webhook configuration
1. Verify webhook token matches in both GitHub Actions and Jenkins
2. Check Jenkins logs: Manage Jenkins → System Log
3. Enable "Print post content" in Generic Webhook Trigger settings
4. Test with curl command above

### "Unknown service" Error

**Solution**: Add service to serviceMap
1. Edit `jenkins/Jenkinsfile.update-image`
2. Add your service to the `serviceMap` in "Update Image Tag" stage
3. Commit and push changes

### No Changes to Commit

This is normal if the image tag is already up-to-date. Pipeline succeeds with message:
```
⏭️  No changes to commit (tag already up-to-date)
```

## Monitoring

### Check Pipeline Status

```bash
# Via Jenkins CLI
jenkins-cli build shopping-cart-image-update

# Via Jenkins API
curl -u user:token https://jenkins.example.com/job/shopping-cart-image-update/lastBuild/api/json
```

### Check Argo CD Sync Status

```bash
# Get application status
argocd app get shopping-cart-dev

# Watch sync progress
argocd app sync shopping-cart-dev --watch

# Check deployment
kubectl get pods -n shopping-cart-apps
kubectl describe pod <pod-name> -n shopping-cart-apps | grep Image:
```

## Advanced Configuration

### Multiple Environments

To support dev/staging/prod:

1. Create separate pipeline jobs:
   - `shopping-cart-image-update-dev`
   - `shopping-cart-image-update-staging`
   - `shopping-cart-image-update-prod`

2. Configure different `HELM_VALUES_FILE`:
   - Dev: `values-dev.yaml`
   - Staging: `values-staging.yaml`
   - Prod: `values-prod.yaml`

3. Add branch filtering per environment

### Approval Steps for Production

Add manual approval before production updates:

```groovy
stage('Approval') {
    when {
        expression { HELM_VALUES_FILE == 'values-prod.yaml' }
    }
    steps {
        input message: 'Deploy to production?', ok: 'Deploy'
    }
}
```

### Notification Integration

Add Slack/email notifications:

```groovy
post {
    success {
        slackSend(
            color: 'good',
            message: "Image updated: ${params.service} → ${params.image_tag}"
        )
    }
    failure {
        slackSend(
            color: 'danger',
            message: "Failed to update image: ${params.service}"
        )
    }
}
```

## Security Best Practices

1. **Use Jenkins Credentials**
   - Never hardcode tokens or passwords
   - Use Jenkins Credentials Store
   - Rotate credentials regularly

2. **Webhook Token**
   - Use strong, random tokens
   - Different tokens per environment
   - Keep tokens in GitHub Secrets

3. **Repository Access**
   - Use Personal Access Tokens with minimal scope (`repo` only)
   - Consider using GitHub Apps for better security
   - Enable branch protection on infrastructure repo

4. **Pipeline Security**
   - Run pipeline in sandboxed agent
   - Limit pipeline permissions
   - Review pipeline changes before merging

## Related Documentation

- [GitHub Actions & Jenkins Webhook Setup](../docs/github-actions-webhook-setup.md)
- [Container Image Workflow](../docs/container-image-workflow.md)

## Support

For issues or questions:
1. Check Jenkins pipeline logs
2. Review troubleshooting section above
3. Check GitHub Actions workflow logs
4. Verify webhook payload in Jenkins
