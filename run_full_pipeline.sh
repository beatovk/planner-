#!/bin/bash

# 🚀 Полный пайплайн обработки мест Entertainment Planner
# Автор: AI Assistant
# Дата: 2025-09-21

set -e  # Остановка при ошибке

echo "🚀 ЗАПУСК ПОЛНОГО ПАЙПЛАЙНА ОБРАБОТКИ МЕСТ"
echo "=============================================="

# Проверка окружения
if [ ! -f ".env" ]; then
    echo "❌ Файл .env не найден!"
    exit 1
fi

# Активация окружения
echo "🔧 Настройка окружения..."
source ../venv/bin/activate
export $(cat .env | xargs)

# Проверка базы данных
echo "🗄️ Проверка базы данных..."
python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
from sqlalchemy import func

db = SessionLocal()
try:
    statuses = db.query(Place.processing_status, func.count(Place.id)).group_by(Place.processing_status).all()
    print('📊 ТЕКУЩИЕ СТАТУСЫ МЕСТ:')
    for status, count in statuses:
        print(f'  {status}: {count}')
    
    new_count = db.query(Place).filter(Place.processing_status == 'new').count()
    print(f'\\n🆕 Новых мест для обработки: {new_count}')
    
    if new_count == 0:
        print('✅ Нет новых мест для обработки')
        exit(0)
finally:
    db.close()
"

# Шаг 1: GPT Worker
echo ""
echo "🤖 ШАГ 1: Запуск GPT Worker..."
echo "================================"

# Проверяем, не запущен ли уже воркер
if pgrep -f "fixed_gpt_worker.py" > /dev/null; then
    echo "⚠️ GPT Worker уже запущен. Останавливаем..."
    pkill -f "fixed_gpt_worker.py"
    sleep 2
fi

# Запускаем GPT Worker в фоне
echo "🔄 Запуск GPT Worker в фоновом режиме..."
nohup python fixed_gpt_worker.py > gpt_worker.log 2>&1 &
GPT_PID=$!
echo "📝 GPT Worker запущен (PID: $GPT_PID)"

# Ждем завершения GPT обработки
echo "⏳ Ожидание завершения GPT обработки..."
while true; do
    NEW_COUNT=$(python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
db = SessionLocal()
try:
    count = db.query(Place).filter(Place.processing_status == 'new').count()
    print(count)
finally:
    db.close()
")
    
    if [ "$NEW_COUNT" -eq 0 ]; then
        echo "✅ GPT обработка завершена!"
        break
    fi
    
    echo "🔄 Осталось новых мест: $NEW_COUNT"
    sleep 10
done

# Шаг 2: Google Enrichment
echo ""
echo "🔍 ШАГ 2: Запуск Google Enrichment Agent..."
echo "============================================="

echo "🔄 Запуск Google обогащения..."
python enhanced_google_enrichment_agent.py

# Шаг 3: Публикация
echo ""
echo "📰 ШАГ 3: Публикация готовых мест..."
echo "====================================="

python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
from sqlalchemy import func
from datetime import datetime, timezone

db = SessionLocal()
try:
    # Переводим места с саммари и Google данными в published
    places_to_publish = db.query(Place).filter(
        Place.processing_status == 'enriched',
        Place.summary.isnot(None),
        Place.lat.isnot(None),
        Place.lng.isnot(None)
    ).count()
    
    print(f'📝 Мест готовых к публикации: {places_to_publish}')
    
    if places_to_publish > 0:
        # Обновляем статус
        db.query(Place).filter(
            Place.processing_status == 'enriched',
            Place.summary.isnot(None),
            Place.lat.isnot(None),
            Place.lng.isnot(None)
        ).update({
            'processing_status': 'published',
            'published_at': datetime.now(timezone.utc)
        })
        db.commit()
        print(f'✅ Опубликовано {places_to_publish} мест!')
    else:
        print('⚠️ Нет мест для публикации')
    
    # Финальная статистика
    final_statuses = db.query(Place.processing_status, func.count(Place.id)).group_by(Place.processing_status).all()
    print(f'\\n🎯 ИТОГОВАЯ СТАТИСТИКА:')
    for status, count in final_statuses:
        print(f'  {status}: {count}')
        
finally:
    db.close()
"

echo ""
echo "🎉 ПАЙПЛАЙН ЗАВЕРШЕН УСПЕШНО!"
echo "=============================="
echo "📊 Проверьте финальную статистику выше"
echo "📝 Логи GPT Worker: gpt_worker.log"
echo "🔍 Логи Google Enrichment: выводятся в консоль"
