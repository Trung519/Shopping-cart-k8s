pipeline {
    agent any

    environment {
        JAVA_VERSION = '21'
    }

    options {
        timeout(time: 30, unit: 'MINUTES')
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
    }

    tools {
        maven 'Maven-3.9'
        jdk 'JDK-21'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Build') {
            steps {
                sh 'mvn -B clean compile'
            }
        }

        stage('Test') {
            steps {
                sh 'mvn -B test'
            }
            post {
                always {
                    junit '**/target/surefire-reports/*.xml'
                    jacoco(
                        execPattern: '**/target/*.exec',
                        classPattern: '**/target/classes',
                        sourcePattern: '**/src/main/java'
                    )
                }
            }
        }

        stage('Package') {
            steps {
                sh 'mvn -B package -DskipTests'
            }
            post {
                success {
                    archiveArtifacts artifacts: '**/target/*.jar', fingerprint: true
                }
            }
        }

        stage('Integration Tests') {
            when {
                anyOf {
                    branch 'main'
                    branch 'develop'
                }
            }
            environment {
                VAULT_ADDR = 'http://localhost:8200'
                VAULT_TOKEN = 'root'
                RABBITMQ_HOST = 'localhost'
                RABBITMQ_PORT = '5672'
            }
            steps {
                script {
                    // Start services with Docker Compose
                    sh '''
                        cat > docker-compose.ci.yml << 'EOF'
version: '3.8'
services:
  rabbitmq:
    image: rabbitmq:3.12-management-alpine
    ports:
      - "5672:5672"
      - "15672:15672"
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "-q", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  vault:
    image: hashicorp/vault:latest
    ports:
      - "8200:8200"
    environment:
      VAULT_DEV_ROOT_TOKEN_ID: root
      VAULT_DEV_LISTEN_ADDRESS: 0.0.0.0:8200
    cap_add:
      - IPC_LOCK
EOF
                        docker-compose -f docker-compose.ci.yml up -d

                        echo "Waiting for services..."
                        sleep 30

                        # Configure Vault
                        export VAULT_ADDR=http://localhost:8200
                        export VAULT_TOKEN=root

                        vault secrets enable rabbitmq || true
                        vault write rabbitmq/config/connection \
                            connection_uri="http://localhost:15672" \
                            username="guest" \
                            password="guest"
                        vault write rabbitmq/roles/rabbitmq-role \
                            vhosts='{"/":{\"write\": \".*\", \"read\": \".*\", \"configure\": \".*\"}}'
                    '''

                    sh 'mvn -B verify -P integration-tests'
                }
            }
            post {
                always {
                    sh 'docker-compose -f docker-compose.ci.yml down -v || true'
                    sh 'rm -f docker-compose.ci.yml'
                }
            }
        }

        stage('Release') {
            when {
                buildingTag()
            }
            steps {
                sh 'mvn -B deploy -DskipTests'
            }
        }
    }

    post {
        always {
            cleanWs()
        }
        success {
            echo 'Build succeeded!'
        }
        failure {
            echo 'Build failed!'
        }
    }
}
