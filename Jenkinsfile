pipeline {
    agent any
    environment {
        DOCKER_REGISTRY = 'your-registry.azurecr.io'
        IMAGE_NAME = 'resovva-backend'
        KUBE_CONFIG = credentials('k8s-kubeconfig')
    }
    stages {
        stage('Checkout') {
            steps { checkout scm }
        }

        stage('Test & Lint') {
            steps {
                sh 'pip install -r requirements-dev.txt'
                sh 'pytest tests/'
                sh 'flake8 app/'
            }
        }

        stage('Build & Push') {
            steps {
                script {
                    docker.withRegistry("https://${DOCKER_REGISTRY}", 'docker-registry-credentials') {
                        def appImage = docker.build("${DOCKER_REGISTRY}/${IMAGE_NAME}:${env.BUILD_NUMBER}")
                        appImage.push()
                        appImage.push('latest')
                    }
                }
            }
        }

        stage('Deploy to K8s') {
            steps {
                withKubeConfig([credentialsId: 'k8s-kubeconfig']) {
                    // Update Image Tag im Manifest (einfache sed Lösung für MVP)
                    sh "sed -i 's|backend:latest|backend:${env.BUILD_NUMBER}|g' k8s/deployment.yaml"
                    sh 'kubectl apply -f k8s/'
                }
            }
        }
    }
}
