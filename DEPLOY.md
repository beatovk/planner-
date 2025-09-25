# Деплой на Fly.io

## Подготовка

1. Установите Fly CLI:
```bash
curl -L https://fly.io/install.sh | sh
```

2. Войдите в аккаунт:
```bash
fly auth login
```

## Настройка переменных окружения

1. Создайте приложение:
```bash
fly launch
```

2. Установите секреты:
```bash
fly secrets set OPENAI_API_KEY=your_key_here
fly secrets set DATABASE_URL=postgresql://...
fly secrets set SECRET_KEY=your_secret_key
```

## Деплой

1. Соберите и задеплойте:
```bash
fly deploy
```

2. Проверьте статус:
```bash
fly status
```

3. Откройте приложение:
```bash
fly open
```

## Полезные команды

- Просмотр логов: `fly logs`
- SSH в контейнер: `fly ssh console`
- Масштабирование: `fly scale count 2`
- Перезапуск: `fly restart`

## База данных

Для продакшена рекомендуется использовать Fly Postgres:
```bash
fly postgres create --name entertainment-planner-db
fly postgres attach entertainment-planner-db
```
