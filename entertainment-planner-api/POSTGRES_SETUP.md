# 🐘 Настройка PostgreSQL для Entertainment Planner

## 📋 Требования
- PostgreSQL 12+ 
- Python 3.8+
- psycopg2-binary

## 🚀 Быстрая настройка

### 1. Установка PostgreSQL (macOS)
```bash
# Через Homebrew
brew install postgresql@16
brew services start postgresql@16

# Или скачать с официального сайта
# https://www.postgresql.org/download/macosx/
```

### 2. Создание базы данных
```bash
# Подключиться к PostgreSQL
psql postgres

# Создать базу данных и пользователя
CREATE DATABASE ep;
CREATE USER ep WITH PASSWORD 'ep';
GRANT ALL PRIVILEGES ON DATABASE ep TO ep;
\q
```

### 3. Настройка подключения
```bash
# В entertainment-planner-api/.env
DATABASE_URL=postgresql+psycopg://ep:ep@localhost:5432/ep
```

### 4. Создание таблиц
```bash
cd entertainment-planner-api
source ../venv/bin/activate
python -c "from apps.core.db import engine; from apps.places.models import Base; Base.metadata.create_all(engine)"
```

## ✅ Проверка
```bash
# Тест подключения
python -c "
from apps.core.db import engine
from sqlalchemy import text
with engine.connect() as conn:
    result = conn.execute(text('SELECT COUNT(*) FROM places'))
    print(f'Мест в базе: {result.scalar()}')
"
```

## 🔧 Альтернативные настройки

### Изменение пароля/пользователя
```bash
# В PostgreSQL
ALTER USER ep WITH PASSWORD 'новый_пароль';

# В .env
DATABASE_URL=postgresql+psycopg://ep:новый_пароль@localhost:5432/ep
```

### Изменение порта
```bash
# В .env
DATABASE_URL=postgresql+psycopg://ep:ep@localhost:5433/ep
```

## 🆘 Решение проблем

### Ошибка подключения
```bash
# Проверить статус PostgreSQL
brew services list | grep postgresql

# Перезапустить
brew services restart postgresql@16
```

### Ошибка прав доступа
```bash
# Пересоздать пользователя
psql postgres
DROP USER IF EXISTS ep;
CREATE USER ep WITH PASSWORD 'ep';
GRANT ALL PRIVILEGES ON DATABASE ep TO ep;
```

### Ошибка psycopg2
```bash
pip install psycopg2-binary
```

## 📊 Текущая статистика
- **База данных**: `ep`
- **Пользователь**: `ep`
- **Пароль**: `ep`
- **Порт**: `5432`
- **Мест в базе**: 1873
- **Статусы**: published (1640), enriched (227), summarized (6)