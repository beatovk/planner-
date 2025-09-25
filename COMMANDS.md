# 🚀 Команды Entertainment Planner

## 📋 Быстрые команды

### Настройка окружения
```bash
cd entertainment-planner-api
source ../venv/bin/activate
export $(cat .env | xargs)
```

### Полный пайплайн (рекомендуется)
```bash
./run_full_pipeline.sh
```

### Добавление новых мест
```bash
python add_new_places.py
```

### GPT обработка
```bash
# В фоне
nohup python fixed_gpt_worker.py > gpt_worker.log 2>&1 &

# Проверить статус
ps aux | grep fixed_gpt_worker
```

### Google обогащение
```bash
python enhanced_google_enrichment_agent.py
```

### Публикация мест
```bash
python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
from datetime import datetime, timezone

db = SessionLocal()
try:
    places_to_publish = db.query(Place).filter(
        Place.processing_status == 'enriched',
        Place.summary.isnot(None),
        Place.lat.isnot(None),
        Place.lng.isnot(None)
    ).count()
    
    if places_to_publish > 0:
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
finally:
    db.close()
"
```

### Проверка статуса
```bash
python check_progress.py
```

### Мониторинг логов
```bash
tail -f gpt_worker.log
```

## 🔧 API сервер

### Запуск
```bash
uvicorn apps.api.main:app --host 0.0.0.0 --port 3000 --reload
```

### Проверка
```bash
curl http://localhost:3000/api/health
```

## 🌐 Веб-интерфейс

### Запуск
```bash
cd apps/web-mobile/web2
python3 -m http.server 8080
```

### Доступ
- http://localhost:8080

## 🗄️ База данных

### Проверка статусов
```bash
python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
from sqlalchemy import func

db = SessionLocal()
try:
    statuses = db.query(Place.processing_status, func.count(Place.id)).group_by(Place.processing_status).all()
    print('📊 СТАТУСЫ МЕСТ:')
    for status, count in statuses:
        print(f'  {status}: {count}')
finally:
    db.close()
"
```

### Очистка кэша
```bash
python -c "from apps.places.services.search import SearchService; SearchService().clear_cache()"
```

## 🆘 Устранение неполадок

### Остановить воркер
```bash
pkill -f fixed_gpt_worker.py
```

### Перезапустить воркер
```bash
pkill -f fixed_gpt_worker.py && nohup python fixed_gpt_worker.py > gpt_worker.log 2>&1 &
```

### Проверить ошибки
```bash
python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place

db = SessionLocal()
try:
    error_places = db.query(Place).filter(Place.processing_status == 'error').all()
    print(f'❌ Мест с ошибками: {len(error_places)}')
    for place in error_places:
        print(f'  - {place.name}: {place.last_error}')
finally:
    db.close()
"
```

## 📊 Статистика

### Текущая статистика (2025-09-21)
- **Всего мест**: 1873
- **📰 Опубликовано**: 1640 мест (87.5%)
- **🔍 Обогащено**: 227 мест (12.1%)
- **📝 Готовы к обогащению**: 6 мест (0.3%)

### Успешность агентов
- **GPT Worker**: 100% успешность обработки
- **Google Enrichment**: 100% успешность обогащения
  - Google Places API: 94.8% мест
  - Веб-поиск: 5.2% мест
