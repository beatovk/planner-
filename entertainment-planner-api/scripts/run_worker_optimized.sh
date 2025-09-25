#!/usr/bin/env bash
set -Eeuo pipefail

cd "/Users/user/entertainment planner/entertainment-planner-api"

# Загружаем переменные окружения
set -a
source .env
set +a

# Функция для проверки базы
check_db() {
    sqlite3 "$(echo $DATABASE_URL | sed 's/sqlite:\/\/\///')" "PRAGMA integrity_check;" | grep -q "ok"
}

# Функция для восстановления базы
restore_db() {
    echo "❌ База данных повреждена, восстанавливаю..."
    DB_PATH="$(echo $DATABASE_URL | sed 's/sqlite:\/\/\///')"
    BACKUP_PATH="${DB_PATH}.backup.$(date +%Y%m%d%H%M%S)"
    
    # Создаем бэкап
    cp "$DB_PATH" "$BACKUP_PATH"
    
    # Восстанавливаем из SQL дампа
    if [ -f "entertainment_clean.sql" ]; then
        rm -f "$DB_PATH"
        sqlite3 "$DB_PATH" < entertainment_clean.sql
        alembic upgrade head
        echo "✅ База восстановлена из SQL дампа"
    else
        echo "❌ SQL дамп не найден"
        exit 1
    fi
}

# Функция для очистки данных
clear_data() {
    echo "Очищаю summary и tags_csv..."
    python -c "
from apps.core.db import SessionLocal
from sqlalchemy import text
db = SessionLocal()
db.execute(text('''
UPDATE places SET 
    summary = NULL,
    tags_csv = NULL,
    interest_signals = NULL,
    processing_status = 'new',
    updated_at = NULL
'''))
db.commit()
result = db.execute(text('SELECT COUNT(*) FROM places WHERE processing_status = \"new\"')).scalar()
print(f'Записей со статусом new: {result}')
db.close()
"
}

# Основной цикл
while true; do
    if ! check_db; then
        restore_db
        clear_data
    fi

    echo "🚀 Запускаю оптимизированный воркер..."
    python -m apps.places.workers.gpt_normalizer
    echo "⚠️  Воркер завершился, проверяю базу..."
    sleep 5
done
