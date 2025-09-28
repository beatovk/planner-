# Entertainment Planner - Deploy Files

## Структура файлов

### Конфигурация деплоя
- Dockerfile - Docker образ для API
- fly.toml - Fly.io конфигурация
- .python-version - версия Python (3.11.x)
- requirements.txt - зависимости Python
- .env.example - переменные окружения

### Автоматизация
- Makefile - команды для dev/deploy

### Код приложения
- apps/core/db.py - конфигурация БД (без statement_timeout)
- apps/api/main.py - роутинг (все под /api)
- apps/api/routes/db_diag.py - диагностика БД
- apps/api/routes/compose.py - rails логика
- apps/places/services/search.py - поиск (fts вместо search_vector)

### База данных
- create_mv.sql - DDL для создания MV с derived-флагами
- create_epx_objects.py - Python скрипт для создания MV

## Быстрый старт

1. Скопировать файлы в проект
2. Настроить .env по .env.example
3. Выполнить create_mv.sql в PostgreSQL
4. make dev - запуск локально
5. make deploy-staging - деплой на стейджинг

## Проверки

- make api-diag - диагностика API
- make master-local - тесты локально
- make master-prod - тесты на проде
