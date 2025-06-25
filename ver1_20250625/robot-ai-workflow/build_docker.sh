docker build -t robot-ai-workflow:v1.0.8 .
docker build -f Dockerfile.worker -t robot-ai-workflow-worker:v1.0.8 .
