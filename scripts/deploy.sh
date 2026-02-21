#!/bin/bash

# MAGIC DEPLOY SCRIPT V1.0
# Usage: ./deploy.sh

set -e # Exit on error

echo "🚀 Starting Sovereign Roy Deployment..."

# 1. System Update
echo "🔄 Updating System..."
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y curl git

# 2. Docker Installation (if missing)
if ! command -v docker &> /dev/null
then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    sudo usermod -aG docker $USER
    echo "⚠️  Docker installed. Please re-login or run 'newgrp docker' to apply permissions."
else
    echo "✅ Docker already installed."
fi

# 3. Project Setup
if [ ! -d "DMarket-Telegram-Bot" ]; then
    echo "📥 Cloning Repository..."
    git clone https://github.com/Dykij/DMarket-Telegram-Bot.git
    cd DMarket-Telegram-Bot
else
    echo "🔄 Pulling latest changes..."
    cd DMarket-Telegram-Bot
    git pull origin main
fi

# 4. Environment Check
if [ ! -f "infra/cloud_prep/.env" ]; then
    echo "⚠️  WARNING: .env file missing in infra/cloud_prep/."
    echo "👉 Please copy infra/cloud_prep/.env.example to .env and fill it!"
    exit 1
fi

# 5. Launch
echo "🔥 Igniting Swarm..."
cd infra/cloud_prep
docker compose up -d --build

echo "✅ Deployment Complete. Roy is awake."
echo "📊 Nginx Admin: http://<YOUR_IP>:81"
