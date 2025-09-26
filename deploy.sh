#!/bin/bash

# Скрипт для деплоя на Fly.io

ENVIRONMENT=${1:-staging}

case $ENVIRONMENT in
  "staging")
    echo "🚀 Deploying to STAGING..."
    flyctl deploy --config fly.staging.toml
    ;;
  "production")
    echo "🚀 Deploying to PRODUCTION..."
    flyctl deploy
    ;;
  *)
    echo "Usage: ./deploy.sh [staging|production]"
    exit 1
    ;;
esac
