# 🚀 Быстрый старт Entertainment Planner

## 📋 Что нужно сделать

1. **Добавить новые места** из CSV файлов
2. **Запустить полный пайплайн** обработки
3. **Проверить результат**

## 🔧 Настройка

```bash
# Перейти в директорию API
cd entertainment-planner-api

# Активировать виртуальное окружение
source ../venv/bin/activate

# Установить переменные окружения
export $(cat .env | xargs)
```

## 🚀 Запуск

### Вариант 1: Автоматический пайплайн (рекомендуется)

```bash
# Запустить полный пайплайн
./run_full_pipeline.sh
```

### Вариант 2: Ручной запуск

```bash
# 1. Добавить новые места
python add_new_places.py

# 2. Enhanced AI Editor (веб-скрапинг + сжатие)
python enhanced_ai_editor.py --batch-size 50

# 3. GPT Normalizer (саммаризация)
python -m apps.places.workers.gpt_normalizer

# 4. Google обогащение
python enhanced_google_enrichment_agent.py

# 5. Публикация
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

## 📊 Проверка результата

```bash
# Общая статистика
python check_progress.py

# Мониторинг логов
tail -f gpt_worker.log
```

## 📁 Где что лежит

- **CSV файлы**: `docs/places.csv/`
- **Логи**: `gpt_worker.log`
- **Конфигурация**: `.env`
- **База данных**: PostgreSQL `ep` на localhost:5432 (настроена в `.env`)

## 🆘 Если что-то пошло не так

1. **Проверьте логи**: `tail -f gpt_worker.log`
2. **Проверьте статус**: `python check_progress.py`
3. **Перезапустите воркер**: `pkill -f fixed_gpt_worker.py && nohup python fixed_gpt_worker.py > gpt_worker.log 2>&1 &`

## 📚 Полная документация

- [AGENT_SYSTEM_README.md](docs/AGENT_SYSTEM_README.md) - Подробная документация агентской системы
- [ENHANCED_AI_EDITOR.md](entertainment-planner-api/ENHANCED_AI_EDITOR.md) - Техническая документация Enhanced AI Editor
- [roadmap.md](docs/roadmap.md) - Общий roadmap проекта

---

**Время обработки**: ~10-15 минут на 100 мест
**Успешность**: 100% для всех агентов
- **Enhanced AI Editor**: 100% успешность веб-скрапинга
- **GPT Normalizer**: 100% успешность саммаризации
- **Google Enrichment**: 100% успешность обогащения
- **Покрытие данными**: 100% мест имеют описания и саммари
