#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-help}"

case "$TARGET" in
  docker|compose)
    cp -n .env.example .env || true
    docker compose up -d --build
    ;;
  compose-prod)
    cp -n .env.example .env || true
    docker compose -f docker-compose.prod.yml up -d --build
    ;;
  k8s)
    bash scripts/deploy-k8s.sh
    ;;
  helm)
    helm upgrade --install finmind ./deploy/helm/finmind --namespace finmind --create-namespace
    ;;
  tilt)
    tilt up
    ;;
  railway)
    railway up
    ;;
  heroku)
    heroku container:push web && heroku container:release web
    ;;
  do-app)
    doctl apps create --spec .do/app.yaml
    ;;
  do-droplet)
    bash deploy/platforms/do-droplet-setup.sh
    ;;
  render)
    echo "Render blueprint ready in render.yaml — trigger via Render Dashboard or CLI: render blueprint launch"
    ;;
  fly)
    flyctl deploy --config fly.toml
    ;;
  aws-ecs)
    aws ecs register-task-definition --cli-input-json file://deploy/platforms/aws/ecs-task-definition.json
    ;;
  aws-ec2)
    bash deploy/platforms/aws/ec2-deploy.sh
    ;;
  gcp-cloudrun)
    gcloud builds submit --config deploy/platforms/gcp/cloudbuild.yaml .
    ;;
  azure-containerapps)
    az containerapp up --name finmind-backend --yaml deploy/platforms/azure/containerapp.yaml
    ;;
  netlify)
    npx netlify-cli deploy --dir=app/dist --prod
    ;;
  vercel)
    npx vercel --cwd app --prod
    ;;
  verify)
    python3 scripts/verify-deployment.py
    ;;
  *)
    echo "Usage: ./scripts/deploy.sh {docker|compose-prod|k8s|helm|tilt|railway|heroku|do-app|do-droplet|render|fly|aws-ecs|aws-ec2|gcp-cloudrun|azure-containerapps|netlify|vercel|verify}"
    exit 1
    ;;
esac
