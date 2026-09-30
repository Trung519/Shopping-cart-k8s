#!/usr/bin/env bash
# Setup a new service repository with GitHub Actions workflow
# Uses GitHub CLI to automate repository creation, secrets, and workflow deployment

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

function print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

function print_success() { echo -e "${GREEN}✓ $1${NC}"; }
function print_error() { echo -e "${RED}✗ $1${NC}"; }
function print_info() { echo -e "${YELLOW}ℹ $1${NC}"; }

# Configuration
SERVICE_NAME=""
REPO_NAME=""
VISIBILITY="public"
JENKINS_WEBHOOK_URL="${JENKINS_WEBHOOK_URL:-}"
JENKINS_WEBHOOK_TOKEN="${JENKINS_WEBHOOK_TOKEN:-}"
SERVICE_TYPE=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE_NAME="$2"
            shift 2
            ;;
        --type)
            SERVICE_TYPE="$2"
            shift 2
            ;;
        --private)
            VISIBILITY="private"
            shift
            ;;
        --jenkins-url)
            JENKINS_WEBHOOK_URL="$2"
            shift 2
            ;;
        --jenkins-token)
            JENKINS_WEBHOOK_TOKEN="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 --service <name> --type <nodejs|python|java|go> [OPTIONS]"
            echo ""
            echo "Required:"
            echo "  --service <name>    Service name (product-catalog, shopping-cart, etc.)"
            echo "  --type <type>       Service type: nodejs, python, java, go"
            echo ""
            echo "Options:"
            echo "  --private           Create private repository (default: public)"
            echo "  --jenkins-url       Jenkins webhook URL (or set JENKINS_WEBHOOK_URL env)"
            echo "  --jenkins-token     Jenkins webhook token (or set JENKINS_WEBHOOK_TOKEN env)"
            echo "  --help              Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0 --service product-catalog --type nodejs"
            echo "  $0 --service shopping-cart --type python --private"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate inputs
if [ -z "$SERVICE_NAME" ]; then
    print_error "Service name is required"
    echo "Use --help for usage information"
    exit 1
fi

if [ -z "$SERVICE_TYPE" ]; then
    print_error "Service type is required"
    echo "Use --help for usage information"
    exit 1
fi

# Validate service type
case "$SERVICE_TYPE" in
    nodejs|python|java|go) ;;
    *)
        print_error "Invalid service type: $SERVICE_TYPE"
        echo "Valid types: nodejs, python, java, go"
        exit 1
        ;;
esac

# Construct repository name
REPO_NAME="shopping-cart-${SERVICE_NAME}"

print_header "Setting Up Service Repository"
print_info "Service: ${SERVICE_NAME}"
print_info "Type: ${SERVICE_TYPE}"
print_info "Repository: ${REPO_NAME}"
print_info "Visibility: ${VISIBILITY}"

# Check if gh is authenticated
if ! gh auth status &> /dev/null; then
    print_error "GitHub CLI not authenticated"
    print_info "Run: gh auth login"
    exit 1
fi

USERNAME=$(gh api user -q .login)
print_success "Authenticated as: ${USERNAME}"

# Check if repository already exists
if gh repo view "${USERNAME}/${REPO_NAME}" &> /dev/null; then
    print_error "Repository ${USERNAME}/${REPO_NAME} already exists"
    print_info "Delete it first with: gh repo delete ${USERNAME}/${REPO_NAME}"
    exit 1
fi

# Create temporary directory for repository setup
TEMP_DIR=$(mktemp -d)
print_info "Working directory: ${TEMP_DIR}"

cd "${TEMP_DIR}"

# Initialize git repository
git init

# Create basic repository structure
print_header "Creating Repository Structure"

mkdir -p .github/workflows src

# Create appropriate Dockerfile
print_info "Creating Dockerfile for ${SERVICE_TYPE}..."

case "$SERVICE_TYPE" in
    nodejs)
        DOCKERFILE_SOURCE="Dockerfile.product-catalog"
        PORT=3000
        cat > package.json << 'EOF'
{
  "name": "SERVICE_NAME_PLACEHOLDER",
  "version": "1.0.0",
  "description": "Shopping Cart SERVICE_NAME_PLACEHOLDER Service",
  "main": "src/server.js",
  "scripts": {
    "start": "node src/server.js",
    "dev": "nodemon src/server.js"
  },
  "dependencies": {
    "express": "^4.18.2"
  },
  "devDependencies": {
    "nodemon": "^3.0.1"
  }
}
EOF
        sed -i "s/SERVICE_NAME_PLACEHOLDER/${SERVICE_NAME}/g" package.json

        cat > src/server.js << 'EOF'
const express = require('express');
const app = express();
const port = process.env.PORT || 3000;

app.use(express.json());

app.get('/', (req, res) => {
  res.json({
    service: 'SERVICE_NAME_PLACEHOLDER',
    version: '1.0.0',
    status: 'healthy',
    timestamp: new Date().toISOString()
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy' });
});

app.listen(port, () => {
  console.log(`SERVICE_NAME_PLACEHOLDER listening on port ${port}`);
});
EOF
        sed -i "s/SERVICE_NAME_PLACEHOLDER/${SERVICE_NAME}/g" src/server.js
        ;;

    python)
        DOCKERFILE_SOURCE="Dockerfile.shopping-cart"
        PORT=5000
        cat > requirements.txt << 'EOF'
flask==3.0.0
gunicorn==21.2.0
redis==5.0.1
EOF

        cat > src/app.py << 'EOF'
from flask import Flask, jsonify
import datetime

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'service': 'SERVICE_NAME_PLACEHOLDER',
        'version': '1.0.0',
        'status': 'healthy',
        'timestamp': datetime.datetime.utcnow().isoformat()
    })

@app.route('/health')
def health():
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
EOF
        sed -i "s/SERVICE_NAME_PLACEHOLDER/${SERVICE_NAME}/g" src/app.py
        ;;

    java)
        DOCKERFILE_SOURCE="Dockerfile.order-service"
        PORT=8080
        mkdir -p src/main/java/com/shopping/${SERVICE_NAME//-/}

        cat > pom.xml << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.shopping</groupId>
    <artifactId>SERVICE_NAME_PLACEHOLDER</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.2.0</version>
    </parent>

    <properties>
        <java.version>17</java.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>
EOF
        sed -i "s/SERVICE_NAME_PLACEHOLDER/${SERVICE_NAME}/g" pom.xml
        ;;

    go)
        DOCKERFILE_SOURCE="Dockerfile.payment-service"
        PORT=8081
        cat > go.mod << 'EOF'
module github.com/shopping-cart/SERVICE_NAME_PLACEHOLDER

go 1.21

require github.com/gorilla/mux v1.8.1
EOF
        sed -i "s/SERVICE_NAME_PLACEHOLDER/${SERVICE_NAME}/g" go.mod

        cat > go.sum << 'EOF'
github.com/gorilla/mux v1.8.1 h1:TuBL49tXwgrFYWhqrNgrUNEY92u81SPhu7sTdzQEiWY=
github.com/gorilla/mux v1.8.1/go.mod h1:AKf9I4AEqPTmMytcMc0KkNouC66V3BtZ4qD5fmWSiMQ=
EOF

        mkdir -p src
        cat > src/main.go << 'EOF'
package main

import (
    "encoding/json"
    "log"
    "net/http"
    "time"
    "github.com/gorilla/mux"
)

type Response struct {
    Service   string    `json:"service"`
    Version   string    `json:"version"`
    Status    string    `json:"status"`
    Timestamp time.Time `json:"timestamp"`
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
    response := Response{
        Service:   "SERVICE_NAME_PLACEHOLDER",
        Version:   "1.0.0",
        Status:    "healthy",
        Timestamp: time.Now().UTC(),
    }
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(response)
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
    w.Header().Set("Content-Type", "application/json")
    json.NewEncoder(w).Encode(map[string]string{"status": "healthy"})
}

func main() {
    r := mux.NewRouter()
    r.HandleFunc("/", homeHandler).Methods("GET")
    r.HandleFunc("/health", healthHandler).Methods("GET")

    log.Println("SERVICE_NAME_PLACEHOLDER listening on port 8081")
    log.Fatal(http.ListenAndServe(":8081", r))
}
EOF
        sed -i "s/SERVICE_NAME_PLACEHOLDER/${SERVICE_NAME}/g" src/main.go
        ;;
esac

print_success "Created application files"

# Copy Dockerfile from examples
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
EXAMPLES_DIR="${SCRIPT_DIR}/../examples/dockerfiles"

if [ -f "${EXAMPLES_DIR}/${DOCKERFILE_SOURCE}" ]; then
    cp "${EXAMPLES_DIR}/${DOCKERFILE_SOURCE}" Dockerfile
    print_success "Copied Dockerfile"
else
    print_error "Dockerfile not found: ${EXAMPLES_DIR}/${DOCKERFILE_SOURCE}"
    exit 1
fi

# Copy and customize GitHub Actions workflow
WORKFLOW_SOURCE="${SCRIPT_DIR}/../examples/github-actions/build-push.yml"

if [ -f "${WORKFLOW_SOURCE}" ]; then
    # Update port in workflow based on service type
    sed "s/8080/${PORT}/g" "${WORKFLOW_SOURCE}" > .github/workflows/build-push.yml
    print_success "Created GitHub Actions workflow"
else
    print_error "Workflow template not found: ${WORKFLOW_SOURCE}"
    exit 1
fi

# Create .dockerignore
cat > .dockerignore << 'EOF'
.git
.github
*.md
.env
.DS_Store
Dockerfile
.dockerignore
EOF

case "$SERVICE_TYPE" in
    nodejs)
        echo "node_modules" >> .dockerignore
        echo "npm-debug.log" >> .dockerignore
        ;;
    python)
        echo "__pycache__" >> .dockerignore
        echo "*.pyc" >> .dockerignore
        echo "venv/" >> .dockerignore
        ;;
    java)
        echo "target/" >> .dockerignore
        echo "*.class" >> .dockerignore
        ;;
    go)
        echo "*.exe" >> .dockerignore
        echo "vendor/" >> .dockerignore
        ;;
esac

print_success "Created .dockerignore"

# Create .gitignore
cat > .gitignore << 'EOF'
.env
.DS_Store
EOF

case "$SERVICE_TYPE" in
    nodejs)
        cat >> .gitignore << 'EOF'
node_modules/
npm-debug.log
.npm
EOF
        ;;
    python)
        cat >> .gitignore << 'EOF'
__pycache__/
*.py[cod]
*$py.class
venv/
.pytest_cache/
EOF
        ;;
    java)
        cat >> .gitignore << 'EOF'
target/
*.class
.classpath
.project
.settings/
EOF
        ;;
    go)
        cat >> .gitignore << 'EOF'
*.exe
vendor/
EOF
        ;;
esac

print_success "Created .gitignore"

# Create README
cat > README.md << EOF
# ${SERVICE_NAME^}

Shopping Cart microservice for ${SERVICE_NAME} functionality.

## Technology Stack

- **Language**: ${SERVICE_TYPE^}
- **Container Registry**: GitHub Container Registry (GHCR)
- **CI/CD**: GitHub Actions → Jenkins → Argo CD

## Development

### Running Locally

\`\`\`bash
EOF

case "$SERVICE_TYPE" in
    nodejs)
        cat >> README.md << 'EOF'
# Install dependencies
npm install

# Run development server
npm run dev

# Run in production mode
npm start
```

### Building Container Image

```bash
docker build -t shopping-cart-SERVICE_NAME_PLACEHOLDER .
docker run -p 3000:3000 shopping-cart-SERVICE_NAME_PLACEHOLDER
```

Access at: http://localhost:3000
EOF
        ;;
    python)
        cat >> README.md << 'EOF'
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run development server
python src/app.py

# Run with gunicorn (production)
gunicorn --bind 0.0.0.0:5000 src.app:app
```

### Building Container Image

```bash
docker build -t shopping-cart-SERVICE_NAME_PLACEHOLDER .
docker run -p 5000:5000 shopping-cart-SERVICE_NAME_PLACEHOLDER
```

Access at: http://localhost:5000
EOF
        ;;
    java)
        cat >> README.md << 'EOF'
# Build with Maven
mvn clean package

# Run application
java -jar target/*.jar
```

### Building Container Image

```bash
docker build -t shopping-cart-SERVICE_NAME_PLACEHOLDER .
docker run -p 8080:8080 shopping-cart-SERVICE_NAME_PLACEHOLDER
```

Access at: http://localhost:8080
EOF
        ;;
    go)
        cat >> README.md << 'EOF'
# Download dependencies
go mod download

# Run application
go run src/main.go

# Build binary
go build -o SERVICE_NAME_PLACEHOLDER src/main.go
./SERVICE_NAME_PLACEHOLDER
```

### Building Container Image

```bash
docker build -t shopping-cart-SERVICE_NAME_PLACEHOLDER .
docker run -p 8081:8081 shopping-cart-SERVICE_NAME_PLACEHOLDER
```

Access at: http://localhost:8081
EOF
        ;;
esac

cat >> README.md << 'EOF'

## API Endpoints

- `GET /` - Service information
- `GET /health` - Health check

## CI/CD Pipeline

GitHub Actions workflow automatically:
1. Lints Dockerfile on pull requests
2. Scans for vulnerabilities
3. Builds container image on merge to main
4. Pushes to GHCR with tags: branch-sha, branch, latest
5. Triggers Jenkins deployment pipeline

## Container Images

Images are published to: `ghcr.io/GITHUB_USERNAME/shopping-cart-SERVICE_NAME_PLACEHOLDER`

Available tags:
- `latest` - Latest from main branch
- `main-<sha>` - Specific commit
- `v*.*.*` - Release versions
EOF

sed -i "s/SERVICE_NAME_PLACEHOLDER/${SERVICE_NAME}/g" README.md
sed -i "s/GITHUB_USERNAME/${USERNAME}/g" README.md

print_success "Created README.md"

# Create initial commit
git add .
git commit -m "Initial commit: ${SERVICE_NAME} service

- Add ${SERVICE_TYPE} application skeleton
- Add Dockerfile with multi-stage build
- Add GitHub Actions workflow for CI/CD
- Configure automatic GHCR push
- Add documentation"

print_success "Created initial commit"

# Create GitHub repository
print_header "Creating GitHub Repository"

gh repo create "${REPO_NAME}" \
    --${VISIBILITY} \
    --description "Shopping Cart ${SERVICE_NAME} service (${SERVICE_TYPE})" \
    --source=. \
    --remote=origin \
    --push

print_success "Repository created: https://github.com/${USERNAME}/${REPO_NAME}"

# Set repository secrets
print_header "Configuring Repository Secrets"

if [ -n "$JENKINS_WEBHOOK_URL" ]; then
    echo "$JENKINS_WEBHOOK_URL" | gh secret set JENKINS_WEBHOOK_URL -R "${USERNAME}/${REPO_NAME}"
    print_success "Set JENKINS_WEBHOOK_URL secret"
else
    print_info "JENKINS_WEBHOOK_URL not provided - set manually later:"
    print_info "  gh secret set JENKINS_WEBHOOK_URL -R ${USERNAME}/${REPO_NAME}"
fi

if [ -n "$JENKINS_WEBHOOK_TOKEN" ]; then
    echo "$JENKINS_WEBHOOK_TOKEN" | gh secret set JENKINS_WEBHOOK_TOKEN -R "${USERNAME}/${REPO_NAME}"
    print_success "Set JENKINS_WEBHOOK_TOKEN secret"
else
    print_info "JENKINS_WEBHOOK_TOKEN not provided - set manually later:"
    print_info "  gh secret set JENKINS_WEBHOOK_TOKEN -R ${USERNAME}/${REPO_NAME}"
fi

# Enable GitHub Actions if not already enabled
gh api repos/${USERNAME}/${REPO_NAME}/actions/permissions \
    -X PUT \
    -f enabled=true \
    -f allowed_actions=all &> /dev/null || true

print_success "GitHub Actions enabled"

# Cleanup
cd - > /dev/null
rm -rf "${TEMP_DIR}"
print_info "Cleaned up temporary directory"

# Display summary
print_header "Setup Complete!"
echo "Repository: https://github.com/${USERNAME}/${REPO_NAME}"
echo "Container Registry: ghcr.io/${USERNAME}/${REPO_NAME}"
echo ""
echo "Next steps:"
echo "  1. Clone repository: gh repo clone ${USERNAME}/${REPO_NAME}"
echo "  2. Set secrets (if not provided):"
echo "     gh secret set JENKINS_WEBHOOK_URL -R ${USERNAME}/${REPO_NAME}"
echo "     gh secret set JENKINS_WEBHOOK_TOKEN -R ${USERNAME}/${REPO_NAME}"
echo "  3. Make changes and push to trigger workflow"
echo "  4. View actions: gh run list -R ${USERNAME}/${REPO_NAME}"
echo "  5. View package: https://github.com/${USERNAME}?tab=packages"
echo ""
print_success "Service repository ready!"
