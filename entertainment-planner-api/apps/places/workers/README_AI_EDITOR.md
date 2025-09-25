# AI Editor Agent

AI Editor Agent - это финальный этап в цепочке обработки данных, который выполняет роль "шефа" всей операции. Он проверяет достоверность собранной информации, ищет качественные изображения и дополняет недостающие поля.

## Быстрый старт (PostgreSQL)

- База данных: используем PostgreSQL по `DATABASE_URL` из `.env`.
- Обязательные переменные:
  - `DATABASE_URL=postgresql+psycopg://ep:ep@localhost:5432/ep`
  - `OPENAI_API_KEY=...`
  - Писатель выставляет `EP_API_READONLY=1` для API на время записи.

### Пути БД
- Текущая рабочая БД: PostgreSQL (см. `.env`).
- Историческая SQLite (для миграций/бэкапов):
  - `~/Library/Application Support/entertainment-planner/db/app.db`

### Запуск GPT Normalizer Worker
```bash
source "/Users/user/entertainment planner/venv/bin/activate"
export PYTHONPATH="/Users/user/entertainment planner/entertainment-planner-api"
set -a; source .env; set +a
nohup python -m apps.places.workers.gpt_normalizer > /tmp/gpt_normalizer.log 2>&1 & echo $!
tail -f /tmp/gpt_normalizer.log
```

### Прогресс и выборка примеров
```bash
python - <<'PY'
from apps.core.db import SessionLocal
from apps.places.models import Place
db = SessionLocal()
processed = db.query(Place).filter(Place.summary.isnot(None)).count()
total = db.query(Place).count()
print(f"progress: {processed}/{total}")
for p in db.query(Place).filter(Place.summary.isnot(None)).order_by(Place.updated_at.desc()).limit(5):
    print(p.name, p.tags_csv, p.interest_signals)
db.close()
PY
```

### Формат interest_signals
- Сохраняются только положительные сигналы в виде списка строк, например: `['food_drink']` или `['culture_art_heritage','urban_unique']`.
- Пустой список не хранится (значение `NULL`).
- Старые записи с форматами-словари мигрируются в списки по true-ключам.

## Функции

### 1. Проверка достоверности данных
- **Веб-поиск**: Проверяет существование места через поисковые системы
- **GPT анализ**: Анализирует соответствие названия, категории и описания
- **Верификация**: Сверяется с 2-3 источниками максимум для экономии токенов

### 2. Поиск качественных изображений
- **Оценка существующих**: Проверяет качество уже имеющихся изображений
- **Веб-поиск**: Ищет профессиональные фотографии мест
- **Фильтрация**: Исключает любительские снимки и аватары

### 3. Дополнение недостающих полей
- **Описания**: Генерирует качественные описания мест
- **Теги**: Создает релевантные теги
- **Часы работы**: Структурирует информацию о времени работы
- **Ценовой уровень**: Определяет ценовую категорию

## Архитектура

```
AI Editor Agent
├── WebVerifier - веб-поиск и проверка достоверности
├── GPT 4o mini - анализ и генерация контента
└── Place Model - обновление данных в БД
```

## Использование

### Запуск отдельно
```bash
python apps/places/commands/run_ai_editor.py --batch-size 5 --verbose
```

### Запуск в полной цепочке
```bash
python run_full_pipeline.py
```

### Запуск только AI Editor этапа
```bash
python run_full_pipeline.py --stage ai_editor
```

## Параметры

- `--batch-size`: Размер батча для обработки (по умолчанию: 5)
- `--api-key`: OpenAI API ключ (или через OPENAI_API_KEY env)
- `--verbose`: Подробное логирование

## Статусы обработки

1. **new** → **summarized** (GPT Worker)
2. **summarized** → **published** (Google API)
3. **published** → **ai_verified** (AI Editor Agent)

## Новые поля в БД

- `ai_verified`: Проверен ли AI-агентом (true/false)
- `ai_verification_date`: Дата проверки AI-агентом
- `ai_verification_data`: JSON с результатами проверки

## Экономия токенов

- Использует веб-поиск для первичной проверки
- GPT вызывается только при низкой уверенности веб-поиска
- Ограничивает количество источников проверки (2-3 максимум)
- Использует GPT 4o mini для экономии

## Логирование

Агент ведет подробные логи:
- Количество обработанных мест
- Результаты верификации
- Найденные изображения
- Обновленные поля
- Ошибки и предупреждения

## Интеграция

AI Editor Agent интегрирован в общую цепочку обработки:

1. **Парсеры** → `new`
2. **GPT Worker** → `summarized` 
3. **Google API** → `published`
4. **AI Editor** → `ai_verified` ✅

## Примеры использования

### Проверка конкретного места
```python
from apps.places.workers.ai_editor import AIEditorAgent

agent = AIEditorAgent()
# Обработает все места со статусом 'published' и ai_verified = NULL
agent.run()
```

### Веб-поиск отдельно
```python
from apps.places.workers.web_verifier import WebVerifier

verifier = WebVerifier()
result = verifier.verify_place_data("Sirocco Sky Bar", "Bar", "Lebua at State Tower")
print(result)
```
