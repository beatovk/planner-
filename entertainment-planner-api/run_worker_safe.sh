#!/bin/bash
set -e

cd "/Users/user/entertainment planner/entertainment-planner-api"

# Загружаем переменные окружения
set -a
source .env
set +a

# Функция для проверки базы
check_db() {
    sqlite3 entertainment.db "PRAGMA integrity_check;" | grep -q "ok"
}

# Функция для восстановления базы
restore_db() {
    echo "🔄 Восстанавливаю базу данных..."
    rm -f entertainment.db*
    sqlite3 entertainment.db < entertainment_clean.sql
    alembic upgrade head
    
    # Очищаем данные для обработки
    python3 -c "
from apps.core.db import SessionLocal
from sqlalchemy import text
db = SessionLocal()
db.execute(text('UPDATE places SET summary = NULL, tags_csv = NULL, interest_signals = NULL, processing_status = \"new\", updated_at = NULL'))
db.commit()
db.close()
print('✅ База восстановлена и данные очищены')
"
}

# Основной цикл
while true; do
    if ! check_db; then
        echo "❌ База повреждена, восстанавливаю..."
        restore_db
    fi
    
    echo "🚀 Запускаю воркер..."
    python -m apps.places.workers.gpt_normalizer || {
        echo "⚠️  Воркер упал, проверяю базу..."
        sleep 5
    }
    
    echo "⏳ Жду 10 секунд перед перезапуском..."
    sleep 10
done
