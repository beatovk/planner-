# Entertainment Planner Bangkok

Умная система планирования развлечений в Бангкоке с AI-поиском, маршрутизацией и агентской системой обработки данных.

## 🎯 Обзор проекта

Entertainment Planner - это полнофункциональная система для поиска и планирования развлечений в Бангкоке. Проект включает в себя:

- **База данных** с 580+ реальными местами
- **AI-поиск** в стиле Netflix с умным ранжированием
- **Мобильный интерфейс** с живым поиском и якорями
- **API** с кэшированием и оптимизацией
- **Агентская система** для автоматической обработки и обогащения данных
- **Google Maps интеграция** для координат, фото, часов работы и контактов

## 🚀 Быстрый старт

> **📚 Краткая инструкция:** [QUICK_START.md](QUICK_START.md)

### Требования
- Python 3.8+
- PostgreSQL 12+ (обязательно)
- Node.js (для веб-интерфейса)

### Установка
```bash
# Клонирование репозитория
git clone <repository-url>
cd entertainment-planner

# Установка зависимостей
cd entertainment-planner-api
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл и добавьте ваши API ключи

# Настройка PostgreSQL базы данных
# Создайте базу данных 'ep' и пользователя 'ep' с паролем 'ep'
# Или измените DATABASE_URL в .env файле

# Создание таблиц (если нужно)
python -c "from apps.core.db import engine; from apps.places.models import Base; Base.metadata.create_all(engine)"

# Запуск API сервера
uvicorn apps.api.main:app --host 0.0.0.0 --port 3000 --reload
```

### 🔑 API Ключи и конфигурация

**Расположение файлов:**
- **Виртуальное окружение**: `/Users/user/entertainment planner/venv/`
- **API ключи**: `entertainment-planner-api/.env`
- **База данных**: PostgreSQL `ep` на localhost:5432

**Необходимые API ключи в `.env`:**
```bash
# PostgreSQL база данных (обязательно)
DATABASE_URL=postgresql+psycopg://ep:ep@localhost:5432/ep

# OpenAI API для GPT обработки
OPENAI_API_KEY=sk-proj-...

# Google Places API для обогащения данных
GOOGLE_MAPS_API_KEY=AIza...
```

**Важно:** Виртуальное окружение находится в **родительской директории** относительно API проекта!

### Обработка данных
```bash
# Перейти в директорию API
cd entertainment-planner-api

# Активировать виртуальное окружение (из родительской директории!)
source ../venv/bin/activate

# Установить PYTHONPATH
export PYTHONPATH=/Users/user/entertainment\ planner/entertainment-planner-api

# Запустить цепочку обработки данных
./run_pipeline.sh

# Или отдельные этапы
./run_pipeline.sh gpt        # GPT обработка
./run_pipeline.sh google     # Google обогащение  
./run_pipeline.sh ai_editor  # AI верификация
```

### Доступ к интерфейсам
- **API**: http://localhost:3000
- **API Docs**: http://localhost:3000/docs
- **Мобильный интерфейс**: http://localhost:8080 (web2/)
- **Админка**: http://localhost:3000/admin

## 📱 Интерфейсы

### 1. Мобильный интерфейс (web2/)
**Современный Netflix-style UI для мобильных устройств**

- **Живой поиск** с debouncing
- **Система якорей** для динамических расстояний
- **High Experience режим** (✨) - качественные места для ценителей
- **Surprise Me режим** (🎲) - неординарные активности и кластеры
- **Google Maps интеграция**
- **Автоматическая геолокация**

**Запуск:**
```bash
cd apps/web-mobile/web2
python3 -m http.server 8080
```

### 2. API (FastAPI)
**RESTful API с кэшированием и оптимизацией**

**Основные эндпоинты:**
- `GET /api/places/search` - поиск мест
- `GET /api/places/{id}` - детали места
- `GET /api/routes` - построение маршрутов
- `GET /api/compose` - Netflix-style рельсы с режимами ранжирования
- `GET /api/compose/rails` - упрощенный доступ к рельсам
- `GET /api/admin/places` - админка

**Новые возможности:**
- **Mode-aware ранжирование**: `light`, `vibe`, `surprise` режимы
- **Extraordinary кластеры**: VR arena, Trampoline park, Planetarium и др.
- **Quality фильтр**: `quality=high` для Michelin, specialty coffee, chef's table
- **Slotting система**: автоматическое извлечение 3 слотов из запросов
- **Badges & Why**: объяснения для пользователей ("trending", "editor pick")

**Технические особенности:**
- PostgreSQL Full-Text Search с ts_rank ранжированием
- Кэширование результатов (85x ускорение)
- Гео-фильтрация по радиусу с BBOX prefilter
- Debug headers (`X-Rails`, `X-Mode`, `X-Rails-Cache`) для мониторинга
- Фиксированный порядок битсета для стабильности
- Co-occurrence добор через materialized view
- Обновленная структура signals с extraordinary детекцией

**Примеры использования:**
```bash
# Обычные рельсы в light режиме
GET /api/compose/rails?mode=light&user_lat=13.7563&user_lng=100.5018

# Surprise режим с кластерами неординарных мест
GET /api/compose/rails?mode=surprise&limit=8

# Качественные места для ценителей
GET /api/compose/rails?mode=surprise&quality=high

# Slotting из свободного текста
GET /api/compose/rails?query=tom yum rooftop spa&mode=vibe

# Режимы ранжирования:
# - light: консервативный (поиск 50%, vibe 20%, scenario 20%)
# - vibe: эмоциональный (поиск 30%, vibe 40%, scenario 20%) 
# - surprise: экспериментальный (все веса равны 25%)
```

## 🗄️ База данных

### Структура
- **Таблица `places`**: основная таблица с местами (PostgreSQL)
- **Materialized View `epx.places_search_mv`**: для быстрого полнотекстового поиска (PostgreSQL)
- **Статусы**: new → summarized → enriched → published

### Статистика
- **Всего мест**: 1873
- **📝 С описанием**: 1873 (100.0%) ✅
- **📄 С саммари**: 1860 (99.3%) ✅
- **🌐 Веб-скрапинг**: 129+ описаний получено из интернета
- **🤖 Enhanced AI Editor**: 100% успешность обработки
- **С координатами**: 1867 (99.7%)
- **С Google ID**: 1867 (99.7%)

### Источники данных
1. **TimeOut Bangkok** - парсинг статей
2. **BK Magazine** - парсинг каталога и статей
3. **Google Maps API** - обогащение координатами, фото, часами работы и контактами
4. **GPT** - категоризация и саммаризация
5. **Агентская система** - автоматическая обработка и верификация данных

## 🤖 Агентская система

### Архитектура агентов
Система использует многоагентную архитектуру для автоматической обработки данных:

1. **Парсеры (Data Ingestion Agents)**
   - TimeOut Bangkok Adapter
   - BK Magazine Adapter
   - Извлекают сырые данные из веб-источников

2. **GPT Normalizer (Summarizer Agent)**
   - Обрабатывает сырые данные через GPT-4o-mini
   - Генерирует саммари, теги и категории
   - Универсальная классификация для разных типов развлечений
   - **Новая структура signals**: extraordinary детекция, quality triggers, scores
   - **Evidence & hooks**: обоснования и UX объяснения для пользователей

3. **Google API Enrichment Agent**
   - Обогащает данные через Google Places API
   - Добавляет точные координаты, адреса, фото
   - Извлекает часы работы, цены, контакты

4. **Enhanced AI Editor (Final Verification Agent)**
   - Финальная верификация и улучшение данных
   - Поиск качественных фотографий
   - Проверка точности информации
   - **Веб-скрапинг описаний** с TimeOut Bangkok, BK Magazine
   - **DuckDuckGo поиск** для мест без валидных URL
   - **Автоматическое сжатие** описаний до 6-10 предложений
   - **Полная автоматизация** без вмешательства человека

### Статусы обработки
- `new` → `summarized` → `enriched` → `published`
- `needs_revision` → `review_pending` → `published`
- `failed` (при критических ошибках)

### Новые поля данных
- **website** - официальный сайт заведения
- **phone** - контактный телефон
- **price_level** - уровень цен (0-4)
- **business_status** - статус работы (OPERATIONAL, CLOSED_TEMPORARILY)
- **hours_json** - детальные часы работы
- **address** - полный адрес из Google Maps

## 🔍 Поиск и ранжирование

### Netflix-style поиск
- **Множественные стратегии**: точные совпадения, частичные, семантические
- **BM25 ранжирование** с весами для полей
- **Гео-фильтрация** по радиусу
- **Кэширование** результатов

### Умная категоризация
- **200+ категорий** через Google API
- **Автоматическое определение** типа заведения
- **Fallback категории** для мест без Google ID

### Маршрутизация
- **Beam search алгоритм** для оптимизации
- **Учет пешеходных расстояний**
- **Диверсификация** по категориям и районам
- **Реалистичные ETA** расчеты

## 🛠️ Архитектура

### Backend (Python + FastAPI)
```
entertainment-planner-api/
├── apps/
│   ├── api/           # FastAPI приложение
│   ├── core/          # Конфигурация и БД
│   └── places/        # Модели и сервисы
├── config/            # Конфигурационные файлы
│   ├── synonyms.yml   # Синонимы для поиска
│   ├── bitset_order.yml      # Фиксированный порядок битсета
│   ├── extraordinary.yml     # Кластеры неординарных мест
│   └── vibes.yml      # Онтология вайбов и категорий
├── requirements.txt
└── README.md
```

### Frontend (HTML/CSS/JS)
```
apps/web-mobile/
├── web2/              # Mood-style интерфейс
│   ├── index.html
│   ├── styles.css
│   ├── app1.js
│   └── README.md
└── README.md
```

### Парсеры
```
entertainment-planner-api/
├── apps/places/ingestion/
│   ├── timeout_adapter.py    # TimeOut Bangkok
│   └── bk_magazine_adapter.py # BK Magazine
└── apps/places/commands/
    ├── ingest_timeout.py
    ├── summarize_places.py
    └── enrich_places.py
```

## 📊 Производительность

### Кэширование
- **Поиск**: 85x ускорение
- **Маршруты**: 68x ускорение
- **Районы**: статический кэш

### Оптимизация
- **PostgreSQL Materialized View** для быстрого поиска
- **Гео-BBOX фильтрация** для производительности
- **Lazy loading** изображений
- **Debouncing** для живого поиска

## 🔧 Разработка

### Команды

#### Быстрый запуск (рекомендуется)
```bash
# Перейти в директорию API
cd entertainment-planner-api

# Активировать виртуальное окружение (из родительской директории!)
source ../venv/bin/activate

# Установить PYTHONPATH
export PYTHONPATH=/Users/user/entertainment\ planner/entertainment-planner-api

# Запустить полную цепочку обработки
./run_pipeline.sh

# Или отдельные этапы
./run_pipeline.sh gpt        # GPT обработка
./run_pipeline.sh google     # Google обогащение  
./run_pipeline.sh ai_editor  # AI верификация
```

#### Прямые команды
```bash
# Парсинг TimeOut Bangkok
python apps/places/commands/ingest_timeout.py

# Парсинг BK Magazine
python apps/places/commands/ingest_bk_magazine.py

# Саммаризация через GPT
python apps/places/commands/run_gpt_worker.py --batch-size 10

# Обогащение через Google API
python apps/places/commands/enrich_google.py --batch-size 20

# AI верификация (базовый редактор)
python apps/places/commands/run_ai_editor.py --batch-size 5

# Enhanced AI Editor (веб-скрапинг + сжатие)
python enhanced_ai_editor.py --batch-size 50

# GPT Normalizer (саммаризация)
python -m apps.places.workers.gpt_normalizer

# Запуск агентской системы (новая архитектура)
ORCH_V2_ENABLED=true CANARY_PERCENTAGE=100.0 python -c "
from apps.places.orchestrator import process_place
# Обработка конкретного места
result = process_place(place_id)
"

# Очистка кэша
python -c "from apps.places.services.search import SearchService; SearchService().clear_cache()"
```

### Тестирование
```bash
# Запуск тестов
pytest

# Проверка API
curl http://localhost:3000/api/health

# Проверка поиска
curl "http://localhost:3000/api/places/search?q=tom%20yum&limit=5"
```

## 📈 Мониторинг

### Debug Headers
API возвращает debug информацию:
- `X-Cache-Status`: HIT/MISS
- `X-Query-Time`: время выполнения
- `X-Results-Count`: количество результатов
- `X-Strategy-Used`: использованная стратегия
- `X-Rails`: содержимое рельс и их происхождение
- `X-Mode`: текущий режим ранжирования
- `X-Rails-Cache`: статус кэша рельс (HIT/MISS)

### Логирование
- **Structured logging** для всех операций
- **Performance metrics** для мониторинга
- **Error tracking** с детальной информацией

## 🚧 Известные ограничения

1. **HTTPS для Safari**: требуется для геолокации
2. **Google API лимиты**: 1000 запросов/день
3. **Кэш браузера**: может показывать устаревшие данные
4. **Мобильная оптимизация**: тестировалось на iPhone

## 🔮 Планы развития

### Краткосрочные (1-2 месяца)
- [x] **Extraordinary кластеры** - VR arena, Planetarium, Trampoline park и др.
- [x] **Mode-aware ранжирование** - light/vibe/surprise режимы
- [x] **Quality фильтры** - Michelin, specialty coffee, chef's table
- [x] **Slotting система** - автоматическое извлечение намерений
- [x] **Фиксированный битсет** - стабильные позиции тегов
- [x] **Обновленная структура signals** - extraordinary детекция + quality triggers
- [x] **Новый интерфейс** - High Experience (✨) и Surprise Me (🎲) режимы
- [x] **Enhanced AI Editor** - веб-скрапинг описаний + автоматическое сжатие
- [x] **100% покрытие данными** - все места имеют описания и саммари
- [ ] PWA поддержка
- [ ] Офлайн режим
- [ ] Push уведомления
- [ ] Темная тема

### Среднесрочные (3-6 месяцев)
- [ ] React веб-интерфейс
- [ ] Пользовательские аккаунты
- [ ] Персональные рекомендации на основе badges/why
- [ ] Open-now функциональность с time_slot
- [ ] Социальные функции

### Долгосрочные (6+ месяцев)
- [ ] Мульти-город поддержка
- [ ] AI-ассистент для планирования
- [ ] Интеграция с календарями
- [ ] Мобильное приложение

## 📞 Поддержка

### Документация
- **API Docs**: http://localhost:3000/docs
- **Roadmap**: [docs/roadmap.md](docs/roadmap.md)
- **Enhanced AI Editor**: [entertainment-planner-api/ENHANCED_AI_EDITOR.md](entertainment-planner-api/ENHANCED_AI_EDITOR.md)
- **Web2 README**: [apps/web-mobile/web2/README.md](apps/web-mobile/web2/README.md)
- **Pipeline Guide**: [entertainment-planner-api/PIPELINE_GUIDE.md](entertainment-planner-api/PIPELINE_GUIDE.md)
- **Agent System**: [docs/AGENT_SYSTEM_README.md](docs/AGENT_SYSTEM_README.md)
- **Quick Start**: [QUICK_START.md](QUICK_START.md)

### Контакты
- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Email**: [your-email@example.com]

## 📄 Лицензия

MIT License - см. [LICENSE](LICENSE) для деталей.

---

**Статус проекта**: ✅ MVP завершен, в активной разработке
**Последнее обновление**: 2025-01-27
**Версия**: 1.0.0
