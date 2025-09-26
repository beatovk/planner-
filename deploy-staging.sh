#!/bin/bash

# Скрипт для деплоя STAGING версии
echo "🚀 Deploying STAGING version..."

# Переключаемся на staging ветку
git checkout staging

# Пушим изменения
git push origin staging

# Деплоим на Fly.io
flyctl deploy --config fly.staging.toml

echo "✅ Staging deployed to: https://entertainment-planner-staging.fly.dev"
