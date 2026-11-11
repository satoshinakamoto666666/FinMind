# Universal One-Click Deployment Guide for FinMind (`#144`)

This guide covers one-click and one-command deployment across **Docker Compose**, **Kubernetes (Helm)**, **Tilt (Local K8s Dev)**, and **12 Cloud & PaaS Platforms**.

## Supported Deployment Targets

| Platform | Configuration Artifact | One-Command Trigger |
| --- | --- | --- |
| Docker Compose (Dev) | `docker-compose.yml` | `./scripts/deploy.sh docker` |
| Docker Compose (Prod) | `docker-compose.prod.yml` | `./scripts/deploy.sh compose-prod` |
| Kubernetes (Raw Manifests) | `deploy/k8s/*.yaml` | `./scripts/deploy.sh k8s` |
| Kubernetes (Helm Chart) | `deploy/helm/finmind/` | `./scripts/deploy.sh helm` |
| Tilt (Local K8s Live Dev) | `Tiltfile` | `./scripts/deploy.sh tilt` |
| Railway | `railway.toml`, `deploy/platforms/railway.json` | `./scripts/deploy.sh railway` |
| Heroku | `heroku.yml`, `Procfile`, `app.json` | `./scripts/deploy.sh heroku` |
| DigitalOcean App Platform | `.do/app.yaml` | `./scripts/deploy.sh do-app` |
| DigitalOcean Droplet | `deploy/platforms/do-droplet-setup.sh` | `./scripts/deploy.sh do-droplet` |
| Render | `render.yaml` | `./scripts/deploy.sh render` |
| Fly.io | `fly.toml`, `deploy/platforms/fly.frontend.toml` | `./scripts/deploy.sh fly` |
| AWS (ECS Fargate / App Runner / EC2) | `deploy/platforms/aws/*` | `./scripts/deploy.sh aws-ecs` |
| GCP Cloud Run | `deploy/platforms/gcp/*` | `./scripts/deploy.sh gcp-cloudrun` |
| Azure Container Apps | `deploy/platforms/azure/containerapp.yaml` | `./scripts/deploy.sh azure-containerapps` |
| Netlify (Frontend) | `netlify.toml`, `app/netlify.toml` | `./scripts/deploy.sh netlify` |
| Vercel (Frontend) | `vercel.json`, `app/vercel.json` | `./scripts/deploy.sh vercel` |

## Runtime Acceptance & Health Verification

- Liveness Probe: `GET /health`
- Readiness Probe (DB + Redis verified): `GET /health/ready`
- Automated E2E Smoke Verification across Auth, Categories, Expenses, Bills, Reminders, Dashboard, and Insights:
  ```bash
  python scripts/verify-deployment.py --api-url http://localhost:8000
  ```
