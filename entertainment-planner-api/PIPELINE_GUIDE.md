# 🚀 Руководство по цепочке обработки данных

## Быстрый старт

```bash
# Активировать виртуальное окружение
source ../venv/bin/activate

# Запустить полную цепочку
./run_pipeline.sh

# Или отдельные этапы
./run_pipeline.sh gpt        # GPT обработка
./run_pipeline.sh google     # Google обогащение  
./run_pipeline.sh ai_editor  # AI верификация
```

## 📊 Текущее состояние БД

- **Всего мест**: 1159
- **new**: 1 (ожидает GPT)
- **error**: 5 (ошибки)
- **published**: 1153 (готовы)
- **AI верифицировано**: 641

## 🔄 Цепочка обработки

### 1️⃣ GPT Normalizer
```bash
python apps/places/commands/run_gpt_worker.py --batch-size 10
```
- **Вход**: `new`, `error` статусы
- **Выход**: `summarized` статус
- **Функции**: генерация summary, тегов, часов работы

### 2️⃣ Google API Enricher  
```bash
python apps/places/commands/enrich_google.py --batch-size 20
```
- **Вход**: места БЕЗ `gmaps_place_id`
- **Выход**: обогащенные данные
- **Функции**: координаты, адреса, фото, категории

### 3️⃣ AI Editor Agent
```bash
python apps/places/commands/run_ai_editor.py --batch-size 5
```
- **Вход**: `published` места БЕЗ `ai_verified`
- **Выход**: `ai_verified = 'true'`
- **Функции**: верификация, поиск фото, дополнение полей

## ⚙️ Настройка

### PYTHONPATH
Уже установлен в `~/.zshrc`:
```bash
export PYTHONPATH="/Users/user/entertainment planner/entertainment-planner-api"
```

### API Ключи
```bash
export OPENAI_API_KEY="your-key-here"
export GOOGLE_PLACES_API_KEY="your-key-here"
```

## 🐛 Отладка

```bash
# Подробное логирование
python apps/places/commands/run_gpt_worker.py --verbose

# Dry run (без изменений)
python apps/places/commands/enrich_google.py --dry-run

# Проверка статусов БД
python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
from sqlalchemy import func
db = SessionLocal()
stats = db.query(Place.processing_status, func.count(Place.id)).group_by(Place.processing_status).all()
for status, count in stats: print(f'{status}: {count}')
db.close()
"
```

## 📈 Мониторинг

- Логи выводятся в консоль
- Статусы сохраняются в БД
- Ошибки записываются в `last_error` поле
- AI верификация в `ai_verified` поле
