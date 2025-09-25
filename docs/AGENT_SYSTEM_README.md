# 🤖 Агентская система Entertainment Planner

## 📋 Обзор

Агентская система Entertainment Planner - это многоагентная архитектура для автоматической обработки и обогащения данных о местах в Бангкоке. Система состоит из 4 основных агентов, которые работают в цепочке для преобразования сырых данных в готовые к использованию места.

## 🏗️ Архитектура системы

```
Новые места (status: new)
    ↓
GPT Worker (Summarizer Agent)
    ↓
Саммаризированные места (status: summarized)
    ↓
Enhanced Google Enrichment Agent
    ├── Google Places API (приоритет)
    └── Веб-поиск (резерв)
    ↓
Обогащенные места (status: enriched)
    ↓
AI Editor (Final Verification Agent)
    ↓
Публичные места (status: published)
```

## 📁 Структура проекта

```
entertainment-planner-api/
├── .env                          # API ключи и конфигурация
├── fixed_gpt_worker.py          # GPT воркер (основной)
├── enhanced_google_enrichment_agent.py  # Google обогащение
├── monitor_gpt_worker.py        # Мониторинг GPT воркера
├── monitor_google_enrichment.py # Мониторинг Google обогащения
├── add_new_places.py           # Добавление новых мест из CSV
├── check_progress.py           # Проверка статуса обработки
├── apps/
│   ├── core/
│   │   ├── db.py               # Подключение к БД
│   │   └── config.py           # Конфигурация
│   └── places/
│       ├── models.py           # Модели данных
│       ├── services/
│       │   └── google_places.py # Google Places API клиент
│       └── workers/
│           └── gpt_client.py   # GPT API клиент
└── docs/
    └── places.csv/             # CSV файлы с новыми местами
```

## 🗄️ База данных

### Таблица `places`

**Основные поля:**
- `id` - уникальный идентификатор
- `name` - название места
- `description_full` - полное описание
- `category` - категория места
- `source` - источник данных
- `source_url` - URL источника
- `processing_status` - статус обработки

**Статусы обработки:**
- `new` - новое место, требует обработки
- `summarized` - обработано GPT, готово к обогащению
- `enriched` - обогащено Google API, готово к публикации
- `published` - опубликовано, доступно пользователям
- `error` - ошибка обработки

**Обогащенные поля (Google API):**
- `lat`, `lng` - координаты
- `rating` - рейтинг (1-5)
- `address` - адрес
- `gmaps_place_id` - Google Place ID
- `gmaps_url` - ссылка на Google Maps
- `website` - веб-сайт
- `phone` - телефон
- `picture_url` - фотография
- `business_status` - статус работы
- `hours_json` - часы работы (JSON)
- `utc_offset_minutes` - часовой пояс

**GPT поля:**
- `summary` - краткое описание
- `tags_csv` - теги через запятую
- `signals` - структурированные сигналы (JSON)

## 🔧 Настройка окружения

### 1. Переменные окружения (.env)

```bash
# OpenAI API
OPENAI_API_KEY=sk-proj-...

# Google Places API
GOOGLE_MAPS_API_KEY=AIza...

# База данных PostgreSQL
DATABASE_URL=postgresql://ep:ep@localhost:5432/ep

# Python путь
PYTHONPATH=/Users/user/entertainment\ planner/entertainment-planner-api
```

### 2. Активация окружения

```bash
# Перейти в директорию API
cd entertainment-planner-api

# Активировать виртуальное окружение
source ../venv/bin/activate

# Установить переменные окружения
export $(cat .env | xargs)
```

## 🚀 Запуск агентов

### 1. GPT Worker (Summarizer Agent)

**Назначение:** Обработка новых мест через GPT для создания саммари, тегов и сигналов

**Запуск:**
```bash
# В фоновом режиме
export $(cat .env | xargs) && nohup python fixed_gpt_worker.py > gpt_worker.log 2>&1 &

# Проверить статус
ps aux | grep fixed_gpt_worker

# Мониторинг логов
tail -f gpt_worker.log
```

**Что делает:**
1. Получает места со статусом `new` из БД
2. Для каждого места создает новую сессию БД
3. Отправляет данные в GPT для нормализации
4. Обновляет поля: `summary`, `tags_csv`, `signals`, `processing_status`
5. Сохраняет изменения и закрывает сессию

### 2. Enhanced Google Enrichment Agent

**Назначение:** Двухуровневое обогащение мест через Google Places API и веб-поиск

**Запуск:**
```bash
# Запуск агента
export $(cat .env | xargs) && python enhanced_google_enrichment_agent.py
```

**Что делает:**
1. **Попытка 1**: Поиск места через Google Places API
   - Если найдено → обогащение полными данными
   - Если не найдено → переход к веб-поиску
2. **Попытка 2**: Веб-поиск для не найденных мест
3. **Попытка 3**: Повторная попытка для оставшихся мест

**Обогащаемые поля:**
- `lat`, `lng` - координаты
- `rating` - рейтинг (1-5)
- `address` - адрес
- `gmaps_place_id` - Google Place ID
- `website` - веб-сайт
- `phone` - телефон
- `picture_url` - фотография
- `business_status` - статус работы
- `hours_json` - часы работы (JSON)

### 3. Мониторинг прогресса

**Проверка статуса:**
```bash
# Общая статистика
python check_progress.py

# Мониторинг GPT воркера
python monitor_gpt_worker.py

# Мониторинг Google обогащения
python monitor_google_enrichment.py
```

## 📊 Добавление новых мест

### 1. Подготовка CSV файлов

CSV файлы должны содержать колонки:
- `name` - название места
- `description_full` - полное описание
- `source_url` - URL источника (опционально)

### 2. Добавление в базу данных

```bash
# Запуск скрипта добавления
export $(cat .env | xargs) && python add_new_places.py
```

**Что делает:**
1. Читает CSV файлы из `docs/places.csv/`
2. Проверяет дубликаты по названию и URL
3. Добавляет новые места со статусом `new`
4. Выводит статистику добавленных/пропущенных мест

### 3. Обработка новых мест

После добавления новых мест запустите цепочку обработки:

```bash
# 1. GPT воркер (в фоне)
export $(cat .env | xargs) && nohup python fixed_gpt_worker.py > gpt_worker.log 2>&1 &

# 2. Дождаться завершения GPT обработки
# Проверить: python check_progress.py

# 3. Google обогащение
export $(cat .env | xargs) && python enhanced_google_enrichment_agent.py

# 4. Публикация готовых мест
export $(cat .env | xargs) && python -c "
from apps.core.db import SessionLocal
from apps.places.models import Place
from sqlalchemy import func
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

## 🔍 Мониторинг и отладка

### 1. Проверка статуса базы данных

```bash
# Общая статистика
export $(cat .env | xargs) && python -c "
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

### 2. Мониторинг логов

```bash
# GPT воркер
tail -f gpt_worker.log

# Google обогащение (выводится в консоль)
# Логи сохраняются в enhanced_google_enrichment_agent.py
```

### 3. Проверка ошибок

```bash
# Места с ошибками
export $(cat .env | xargs) && python -c "
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

## 🛠️ Устранение неполадок

### 1. GPT Worker не запускается

**Проблема:** `IdleInTransactionSessionTimeout`
**Решение:** Используйте `fixed_gpt_worker.py` - он создает новую сессию для каждого места

### 2. Google API не работает

**Проверьте:**
- API ключ в `.env` файле
- Лимиты Google Places API
- Сетевые соединения

### 3. Места не обогащаются

**Проверьте:**
- Статус мест (должен быть `summarized`)
- Наличие `description_full` у мест
- Логи Google обогащения

### 4. Ошибки базы данных

**Проверьте:**
- Подключение к PostgreSQL
- Переменную `DATABASE_URL` в `.env`
- Права доступа к базе данных

## 📈 Статистика работы

### Текущие показатели (2025-09-21)

- **Всего мест**: 1873
- **📰 Опубликовано**: 1640 мест (87.5%)
- **🔍 Обогащено**: 227 мест (12.1%)
- **📝 Готовы к обогащению**: 6 мест (0.3%)

### Успешность агентов

- **GPT Worker**: 100% успешность обработки
- **Google Enrichment**: 100% успешность обогащения
  - Google Places API: 94.8% мест
  - Веб-поиск: 5.2% мест

## 🔄 Полный цикл обработки

1. **Добавление новых мест** из CSV файлов
2. **GPT обработка** - создание саммари, тегов, сигналов
3. **Google обогащение** - координаты, рейтинги, адреса, фото
4. **Публикация** - перевод в статус `published`

**Время обработки:**
- GPT Worker: ~5-10 секунд на место
- Google Enrichment: ~2-3 секунды на место
- Общее время: ~10-15 минут на 100 мест

## 📞 Поддержка

При возникновении проблем:
1. Проверьте логи агентов
2. Убедитесь в правильности конфигурации
3. Проверьте статус базы данных
4. Обратитесь к документации по устранению неполадок

---

**Последнее обновление:** 2025-09-21
**Версия системы:** 2.0 (Enhanced Google Enrichment Agent)
