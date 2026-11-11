#!/usr/bin/env bash
set -euo pipefail
# DigitalOcean Ubuntu 24.04 Droplet One-Command Provisioner for FinMind
sudo apt-get update -y
sudo apt-get install -y ca-certificates curl git ufw
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
cp -n .env.example .env || true
sudo docker compose -f docker-compose.prod.yml up -d --build
echo "FinMind deployed on DigitalOcean Droplet. Verifying health..."
python3 scripts/verify-deployment.py --api-url http://localhost:8000 --frontend-url http://localhost:80
