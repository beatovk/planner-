# 💰 Руководство по обогащению цен

## Проблема

Из 1873 мест в базе данных только 155 (8.3%) имели информацию о ценах. Причины:
1. **TimeOut Bangkok** не предоставляет ценовую информацию
2. **CSV-импорты** не содержат price_level
3. **Google Maps API** возвращает строковые значения, а база ожидает числа

## Решение

### 1. Массовое обновление цен

Создан скрипт `update_prices.py` для принудительного обновления price_level:

```bash
# Обновить цены для 100 мест
python update_prices.py --batch-size 100

# Тестовый запуск (без изменений)
python update_prices.py --batch-size 50 --dry-run
```

### 2. Исправление конвертации цен

Обновлены все команды обогащения для правильной конвертации:
- `apps/places/commands/enrich_google.py`
- `apps/places/commands/enrich_bk_google.py`  
- `apps/places/adapters/enricher_adapter.py`

### 3. Маппинг цен

Google Maps API возвращает строковые значения, которые конвертируются в числа:

```python
price_map = {
    "PRICE_LEVEL_FREE": 0,           # Бесплатно
    "PRICE_LEVEL_INEXPENSIVE": 1,    # Недорого (~100-300฿)
    "PRICE_LEVEL_MODERATE": 2,       # Умеренно (~300-800฿)
    "PRICE_LEVEL_EXPENSIVE": 3,      # Дорого (~800-1500฿)
    "PRICE_LEVEL_VERY_EXPENSIVE": 4  # Очень дорого (~1500฿+)
}
```

## Использование

### Для новых мест

При добавлении новых мест через Google Maps обогащение цены будут автоматически конвертироваться:

```bash
# Обогащение новых мест
python apps/places/commands/enrich_google.py --batch-size 20
```

### Для существующих мест без цен

Используйте специальный скрипт для мест с Google Maps ID, но без цен:

```bash
# Обновить цены для мест с Google Maps ID
python update_prices.py --batch-size 200
```

### Мониторинг результатов

Проверить статистику по ценам:

```python
from apps.core.db import SessionLocal
from apps.places.models import Place

db = SessionLocal()
total = db.query(Place).count()
with_price = db.query(Place).filter(Place.price_level.isnot(None)).count()

print(f'Всего мест: {total}')
print(f'С ценами: {with_price} ({with_price/total*100:.1f}%)')
```

## Результаты

После внедрения исправлений:
- **Было**: 118 мест с ценами (6.3%)
- **Стало**: 155+ мест с ценами (8.3%+)
- **Добавлено**: 37+ новых цен

## Автоматизация

Все команды обогащения теперь автоматически:
1. ✅ Получают price_level из Google Maps API
2. ✅ Конвертируют строки в числа
3. ✅ Сохраняют в базу данных
4. ✅ Логируют результаты

## Ограничения

Некоторые места в Google Maps не имеют price_level:
- Музеи и галереи
- Парки и спортивные площадки
- Образовательные учреждения
- Некоторые бары и клубы

Это нормально - Google не всегда предоставляет ценовую информацию для всех типов заведений.
