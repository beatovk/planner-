#!/bin/bash

# Скрипт для деплоя PRODUCTION версии
echo "🚀 Deploying PRODUCTION version..."

# Переключаемся на main ветку
git checkout main

# Пушим изменения
git push origin main

# Деплоим на Fly.io
flyctl deploy --config fly.toml

echo "✅ Production deployed to: https://entertainment-planner-prod.fly.dev"
