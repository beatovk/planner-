# 🤖 Агентская система Entertainment Planner

## Обзор

Агентская система Entertainment Planner - это многоагентная архитектура для автоматической обработки, обогащения и верификации данных о местах развлечений в Бангкоке.

## 🏗️ Архитектура

### Основные компоненты

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Парсеры       │───▶│  GPT Normalizer │───▶│ Google Enricher │───▶│   AI Editor     │
│ (Data Ingestion)│    │  (Summarizer)   │    │   (Enricher)    │    │ (Verification)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
    ┌─────────┐            ┌─────────┐            ┌─────────┐            ┌─────────┐
    │  new    │            │summarized│           │ enriched│            │published│
    └─────────┘            └─────────┘            └─────────┘            └─────────┘
```

### Статусы обработки

- **`new`** - новое место, требует обработки
- **`summarized`** - обработано GPT, есть саммари и теги
- **`enriched`** - обогащено Google API данными
- **`published`** - готово к публикации
- **`needs_revision`** - требует доработки
- **`review_pending`** - ожидает повторной проверки
- **`failed`** - критическая ошибка

## 🔧 Агенты

### 1. Парсеры (Data Ingestion Agents)

**Назначение**: Извлечение сырых данных из веб-источников

**Реализация**:
- `apps/places/ingestion/timeout_adapter.py` - TimeOut Bangkok
- `apps/places/ingestion/bk_magazine_adapter.py` - BK Magazine

**Входные данные**: URL статей и каталогов
**Выходные данные**: Структурированные данные о местах

### 2. GPT Normalizer (Summarizer Agent)

**Назначение**: Обработка сырых данных через GPT-4o-mini

**Функции**:
- Генерация кратких саммари (3 предложения, ≤250 символов)
- Извлечение релевантных тегов с префиксами (category:, vibe:, experience: и др.)
- Детекция Interest Signals (булевые флаги активностей)
- Универсальная классификация по типам развлечений
- Категоризация (рестораны, бары, кафе, развлечения)

**Реализация**: `apps/places/workers/gpt_normalizer.py`

**Входные данные**: Сырые данные о месте
**Выходные данные**: Структурированное саммари, теги, категория, interest_signals

### 3. Google API Enrichment Agent

**Назначение**: Обогащение данных через Google Places API

**Функции**:
- Получение точных координат
- Извлечение адресов
- Поиск качественных фотографий
- Получение часов работы
- Извлечение контактной информации
- Определение уровня цен

**Реализация**: `apps/places/workers/google_enricher_worker.py`

**Входные данные**: Название и базовые данные о месте
**Выходные данные**: Обогащенные данные с Google API

### 4. AI Editor (Final Verification Agent)

**Назначение**: Финальная верификация и улучшение данных

**Функции**:
- Проверка качества фотографий
- Поиск лучших изображений
- Верификация точности информации
- Проверка полноты данных
- Запуск повторной обработки при необходимости

**Реализация**: `apps/places/workers/ai_editor.py`

**Входные данные**: Обработанные данные о месте
**Выходные данные**: Верифицированные и улучшенные данные

## 📊 Новые поля данных

### Основные поля
- **`website`** - официальный сайт заведения
- **`phone`** - контактный телефон
- **`price_level`** - уровень цен (0-4)
- **`business_status`** - статус работы (OPERATIONAL, CLOSED_TEMPORARILY)
- **`hours_json`** - детальные часы работы в JSON формате
- **`address`** - полный адрес из Google Maps
- **`interest_signals`** - JSON с булевыми флагами активностей (новое поле)

#### Interest Signals (детекция активностей)
Система автоматически определяет специфические активности и интересы для каждого места:

**Категории активностей:**
- `nightlife_music` - ночная жизнь и музыка (rooftop_sunset, live_jazz, edm_club_night)
- `food_drink` - еда и напитки (street_food_safari, michelin_bib_run, coffee_roastery_tour)
- `culture_art_heritage` - культура и искусство (temple_morning_walk, gallery_hop, street_art_tour)
- `workshops_makers` - мастер-классы (pottery_wheel_class, barista_foundations, mixology_masterclass)
- `active_adventure_city` - активный отдых (muay_thai_class, climbing, escape_room)
- `nature_daytrips` - природа и поездки (bang_krachao_bike_loop, ayutthaya_day_trip)
- `wellness_recovery` - здоровье и восстановление (thai_massage_course, luxury_spa_day)
- `family_kids_play` - семья и дети (aquarium_visit, theme_park_day, kids_cooking_class)
- `shopping_lifestyle` - шопинг (chatuchak_weekend_market, vinyl_record_digging)
- `urban_unique` - городские активности (rooftop_cinema, secret_supper_club)

**Пример:**
```json
{
  "food_drink": true,
  "family_kids_play": true,
  "nightlife_music": false,
  "culture_art_heritage": false
}
```

### Google API поля
- **`gmaps_place_id`** - уникальный ID места в Google Maps
- **`gmaps_url`** - прямая ссылка на место в Google Maps
- **`utc_offset_minutes`** - смещение времени от UTC

## 🚀 Использование

### Быстрый запуск (рекомендуется)

```bash
# Активировать виртуальное окружение
source ../venv/bin/activate

# Запустить полную цепочку обработки
./run_pipeline.sh

# Или отдельные этапы
./run_pipeline.sh gpt        # GPT обработка
./run_pipeline.sh google     # Google обогащение  
./run_pipeline.sh ai_editor  # AI верификация

# Справка
./run_pipeline.sh --help
```

### Прямые команды

```bash
# Полная цепочка
python run_full_pipeline.py

# Отдельные этапы
python run_full_pipeline.py --stage gpt
python run_full_pipeline.py --stage google
python run_full_pipeline.py --stage ai_editor

# Конкретные команды
python apps/places/commands/run_gpt_worker.py --batch-size 10
python apps/places/commands/enrich_google.py --batch-size 20
python apps/places/commands/run_ai_editor.py --batch-size 5
```

### Запуск агентской системы (новая архитектура)

```bash
# Включение новой архитектуры
export ORCH_V2_ENABLED=true
export CANARY_PERCENTAGE=100.0

# Обработка конкретного места
python -c "
from apps.places.orchestrator import process_place
result = process_place(place_id)
print(f'Результат: {result}')
"

# Обработка всех новых мест
python -c "
from apps.places.orchestrator import process_place
from apps.core.db import SessionLocal
from apps.places.models import Place

db = SessionLocal()
new_places = db.query(Place).filter(Place.processing_status == 'new').all()

for place in new_places:
    result = process_place(place.id)
    print(f'Место {place.name}: {result}')
"
```

### Мониторинг агентов

```bash
# Проверка статусов мест
python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
from collections import Counter

db = SessionLocal()
statuses = [p.processing_status for p in db.query(Place).all()]
print('Статусы:', Counter(statuses))
"

# Проверка качества данных
python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place

db = SessionLocal()
places_with_website = db.query(Place).filter(Place.website.isnot(None)).count()
places_with_phone = db.query(Place).filter(Place.phone.isnot(None)).count()
places_with_price = db.query(Place).filter(Place.price_level.isnot(None)).count()

print(f'Мест с сайтом: {places_with_website}')
print(f'Мест с телефоном: {places_with_phone}')
print(f'Мест с ценой: {places_with_price}')
"
```

## 🔧 Конфигурация

### Переменные окружения

```bash
# OpenAI API
OPENAI_API_KEY=sk-proj-...

# Google Maps API
GOOGLE_MAPS_API_KEY=AIza...

# Агентская система
ORCH_V2_ENABLED=true
CANARY_PERCENTAGE=100.0

# PYTHONPATH (уже настроен в ~/.zshrc)
export PYTHONPATH="/Users/user/entertainment planner/entertainment-planner-api"
```

### Удобные скрипты

**`run_pipeline.sh`** - основной скрипт для запуска цепочки обработки:
- Автоматически активирует виртуальное окружение
- Устанавливает PYTHONPATH
- Поддерживает все этапы обработки
- Показывает подробную информацию о процессе

**`PIPELINE_GUIDE.md`** - подробное руководство по использованию цепочки обработки

### Настройка агентов

```python
# apps/places/orchestrator.py
ORCH_V2_ENABLED = os.getenv('ORCH_V2_ENABLED', 'false').lower() == 'true'
CANARY_PERCENTAGE = float(os.getenv('CANARY_PERCENTAGE', '10.0'))
```

## 📈 Производительность

### Статистика обработки
- **Время обработки места**: 2-5 секунд
- **Успешность обработки**: 95%+
- **Качество данных**: 90%+ полных профилей

### Оптимизации
- **Кэширование** результатов Google API
- **Пакетная обработка** для массовых операций
- **Retry логика** для сетевых ошибок
- **Idempotency** для предотвращения дублирования

## 🐛 Отладка

### Логирование
```python
import logging
logging.basicConfig(level=logging.INFO)

# Логи агентов
logger = logging.getLogger('apps.places.workers')
```

### Проверка статусов
```python
# Проверка конкретного места
place = db.query(Place).get(place_id)
print(f'Статус: {place.processing_status}')
print(f'Попытки: {place.attempts}')
print(f'Ошибки: {place.last_error}')
```

### Тестирование агентов
```python
# Тестирование GPT Normalizer
from apps.places.workers.gpt_normalizer import GPTNormalizerWorker
worker = GPTNormalizerWorker()
result = worker.process_place(place_id)

# Тестирование Google Enricher
from apps.places.workers.google_enricher_worker import GoogleEnricherWorker
worker = GoogleEnricherWorker(mock_mode=False)
result = worker.enrich_place(place_name, place_address)

# Тестирование AI Editor
from apps.places.workers.ai_editor import AIEditorAgent
agent = AIEditorAgent()
result = agent.process_place(place_id)
```

## 🔮 Планы развития

### Краткосрочные (1-2 месяца)
- [ ] Улучшение качества фотографий
- [ ] Добавление большего количества полей из Google API
- [ ] Оптимизация производительности

### Среднесрочные (3-6 месяцев)
- [ ] Машинное обучение для улучшения классификации
- [ ] Автоматическое обновление данных
- [ ] Интеграция с другими источниками данных

### Долгосрочные (6+ месяцев)
- [ ] Полностью автономная система
- [ ] Предиктивная аналитика
- [ ] Интеграция с IoT устройствами

## 📚 Документация

- **API Docs**: http://localhost:8000/docs
- **Roadmap**: [docs/roadmap.md](../docs/roadmap.md)
- **Основной README**: [README.md](../README.md)

---

**Статус**: ✅ Активная разработка
**Версия**: 2.0.0
**Последнее обновление**: 2025-01-27
