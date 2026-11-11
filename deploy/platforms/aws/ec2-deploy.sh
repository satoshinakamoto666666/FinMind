#!/usr/bin/env bash
set -euo pipefail
# AWS EC2 Docker Compose Production Deployer
sudo yum update -y || sudo apt-get update -y
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
cp -n .env.example .env || true
sudo docker compose -f docker-compose.prod.yml up -d --build
