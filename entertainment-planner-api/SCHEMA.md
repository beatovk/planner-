# Схема базы данных - Entertainment Planner API

## Таблица `places` (MVP)

### Primary Key
- `id` — INTEGER PRIMARY KEY

### Источник и аудит
- `source` — TEXT — метка источника (timeout)
- `source_url` — TEXT UNIQUE — оригинальная страница
- `raw_payload` — TEXT — сырые данные (JSON-строка, никогда не трогаем)
- `scraped_at` — DATETIME

### Координаты и адрес
- `lat` — REAL — широта (удобно для Haversine)
- `lng` — REAL — долгота
- `address` — TEXT NULL — если доступно
- `gmaps_place_id` — TEXT NULL — если подтянем GMaps позже
- `gmaps_url` — TEXT NULL — можно хранить сразу, но допустимо генерировать на лету

### Чистые поля (после нормализации)
- `name` — TEXT — название места
- `category` — TEXT — базовая рубрика (e.g., food, park, bar)
- `description_full` — TEXT — полное очищенное описание
- `summary` — TEXT — краткое саммари для карточек
- `tags_csv` — TEXT — простые теги через запятую (thai,rooftop,romantic)
- `price_level` — INTEGER NULL — 0–4 (как в GMaps), если известен
- `hours_json` — TEXT — JSON со временем работы (на будущее)
- `picture_url` — TEXT NULL — ссылка на главную фотографию места

### Процесс/модерация
- `processing_status` — TEXT — new | summarized | published | error
- `last_error` — TEXT NULL
- `published_at` — DATETIME NULL
- `updated_at` — DATETIME

## Статусы обработки

1. **new** — вставлено при ингестии
2. **summarized** — нормализовано GPT (заполнены чистые поля)
3. **published** — видно в публичном API
4. **error** — обработка не удалась, `last_error` заполнен

## API Endpoints

### GET /api/places
Получить список мест с фильтрацией по статусу.

**Параметры:**
- `skip` (int, default=0) — пропустить записей
- `limit` (int, default=100) — лимит записей
- `status` (str, default="published") — статус фильтрации

**Ответ:** `List[PlaceResponse]`

### GET /api/places/{place_id}
Получить детальную информацию о месте.

**Ответ:** `PlaceDetail`

## Примеры данных

### PlaceResponse (публичный API)
```json
{
  "id": 1,
  "name": "Test Thai Restaurant",
  "category": "food",
  "summary": "Authentic Thai restaurant famous for pad thai",
  "tags_csv": "thai,authentic,pad-thai,tom-yum",
  "lat": 13.7563,
  "lng": 100.5018,
  "address": "123 Sukhumvit Road, Bangkok",
  "price_level": 2,
  "picture_url": "https://images.unsplash.com/photo-1551218808-94e220e084d2?w=800",
  "processing_status": "published",
  "updated_at": "2025-09-05T14:03:57.980020",
  "published_at": "2025-09-05T14:03:57.980020"
}
```

### PlaceDetail (админка)
```json
{
  "id": 1,
  "name": "Test Thai Restaurant",
  "category": "food",
  "description_full": "Authentic Thai cuisine with traditional recipes...",
  "summary": "Authentic Thai restaurant famous for pad thai",
  "tags_csv": "thai,authentic,pad-thai,tom-yum",
  "lat": 13.7563,
  "lng": 100.5018,
  "address": "123 Sukhumvit Road, Bangkok",
  "price_level": 2,
  "hours_json": "{\"monday\": \"10:00-22:00\", \"tuesday\": \"10:00-22:00\"}",
  "picture_url": "https://images.unsplash.com/photo-1551218808-94e220e084d2?w=800",
  "processing_status": "published",
  "source": "timeout",
  "source_url": "https://timeout.com/bangkok/restaurants/example1",
  "raw_payload": "{\"title\": \"Test Restaurant 1\", \"description\": \"Amazing Thai food\"}",
  "scraped_at": "2025-09-05T14:03:57.980020",
  "updated_at": "2025-09-05T14:03:57.980020",
  "published_at": "2025-09-05T14:03:57.980020"
}
```
