# 🚀 Полное руководство по деплою

## Что у нас есть

### Две версии приложения:
1. **STAGING** (тестирование) - `entertainment-planner-staging.fly.dev`
2. **PRODUCTION** (пользователи) - `entertainment-planner-prod.fly.dev`

### Две ветки в Git:
1. **staging** - для тестирования новых функций
2. **main** - стабильная версия для пользователей

## 🛠 Первоначальная настройка

### 1. Установи Fly CLI
```bash
curl -L https://fly.io/install.sh | sh
```

### 2. Войди в аккаунт
```bash
fly auth login
```

### 3. Создай два приложения на Fly.io

**Staging приложение:**
```bash
fly apps create entertainment-planner-staging
```

**Production приложение:**
```bash
fly apps create entertainment-planner-prod
```

### 4. Настрой секреты для каждого приложения

**Для Staging:**
```bash
fly secrets set --app entertainment-planner-staging OPENAI_API_KEY=your_key_here
fly secrets set --app entertainment-planner-staging DATABASE_URL=postgresql://...
fly secrets set --app entertainment-planner-staging SECRET_KEY=your_secret_key
```

**Для Production:**
```bash
fly secrets set --app entertainment-planner-prod OPENAI_API_KEY=your_key_here
fly secrets set --app entertainment-planner-prod DATABASE_URL=postgresql://...
fly secrets set --app entertainment-planner-prod SECRET_KEY=your_secret_key
```

## 🔄 Workflow разработки

### Для тестирования новых функций:

1. **Создай feature ветку:**
```bash
git checkout -b feature/new-function
# ... делай изменения ...
git add .
git commit -m "Add new function"
```

2. **Слей в staging:**
```bash
git checkout staging
git merge feature/new-function
git push origin staging
```

3. **Деплой staging:**
```bash
./deploy-staging.sh
```

4. **Тестируй на:** `https://entertainment-planner-staging.fly.dev`

### Когда все готово для пользователей:

1. **Слей staging в main:**
```bash
git checkout main
git merge staging
git push origin main
```

2. **Деплой production:**
```bash
./deploy-production.sh
```

3. **Пользователи увидят на:** `https://entertainment-planner-prod.fly.dev`

## 🚨 Экстренные ситуации

### Откат production:
```bash
git checkout main
git revert HEAD
git push origin main
# Автоматически задеплоится новая версия
```

### Просмотр логов:
```bash
# Staging
fly logs --app entertainment-planner-staging

# Production  
fly logs --app entertainment-planner-prod
```

### SSH в контейнер:
```bash
# Staging
fly ssh console --app entertainment-planner-staging

# Production
fly ssh console --app entertainment-planner-prod
```

## 📊 Мониторинг

### Статус приложений:
```bash
fly status --app entertainment-planner-staging
fly status --app entertainment-planner-prod
```

### Масштабирование:
```bash
# Увеличить количество машин
fly scale count 2 --app entertainment-planner-prod

# Уменьшить
fly scale count 1 --app entertainment-planner-prod
```

## 🔐 GitHub Actions (автоматический деплой)

1. **Добавь секрет в GitHub:**
   - Иди в Settings → Secrets and variables → Actions
   - Добавь `FLY_API_TOKEN` (получи через `fly auth token`)

2. **Теперь при каждом push:**
   - Push в `staging` → автоматически деплоится staging
   - Push в `main` → автоматически деплоится production

## 🎯 Итог

- **Разрабатывай** в feature ветках
- **Тестируй** в staging (автоматически)
- **Выпускай** в main (автоматически)
- **Мониторь** через Fly CLI

Все готово! 🎉
