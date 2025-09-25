# AI Editor Agent - Руководство по использованию

## 🎯 Что это?

AI Editor Agent - это финальный этап в цепочке обработки данных, который работает как "шеф" всей операции. Он проверяет достоверность собранной информации, ищет качественные изображения и дополняет недостающие поля.

## 🚀 Быстрый старт

### 1. Установка API ключа
```bash
export OPENAI_API_KEY="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"
```

### 2. Запуск полной цепочки
```bash
python run_full_pipeline.py
```

### 3. Запуск только AI Editor
```bash
python run_full_pipeline.py --stage ai_editor
```

## 🔧 Команды

### AI Editor Agent
```bash
python apps/places/commands/run_ai_editor.py --batch-size 5 --verbose
```

### Тестирование
```bash
python test_ai_editor.py
```

## 📊 Что делает AI Editor?

### 1. Проверка достоверности
- ✅ Веб-поиск существования места
- ✅ Проверка соответствия названия и описания
- ✅ Верификация категории
- ✅ Анализ через GPT при низкой уверенности

### 2. Поиск изображений
- 🖼️ Оценка качества существующих фото
- 🔍 Поиск профессиональных изображений
- 🚫 Фильтрация любительских снимков

### 3. Дополнение полей
- 📝 Генерация описаний
- 🏷️ Создание тегов
- ⏰ Структурирование часов работы
- 💰 Определение ценового уровня

## 🗄️ Новые поля в БД

- `ai_verified` - проверен ли AI-агентом
- `ai_verification_date` - дата проверки
- `ai_verification_data` - JSON с результатами

## 🔄 Цепочка обработки

```
Парсеры → GPT Worker → Google API → AI Editor Agent
   ↓           ↓           ↓            ↓
  new    → summarized → published → ai_verified
```

## ⚡ Экономия токенов

- Веб-поиск для первичной проверки
- GPT только при необходимости
- Максимум 2-3 источника проверки
- Использование GPT 4o mini

## 📈 Статистика

AI Editor выводит подробную статистику:
- Обработано мест
- Проверено
- Обновлено
- Ошибок

## 🛠️ Настройка

### Размер батча
```bash
--batch-size 5  # По умолчанию
```

### Подробное логирование
```bash
--verbose
```

### API ключ
```bash
--api-key YOUR_KEY
```

## 🚨 Устранение проблем

### Ошибка API ключа
```bash
export OPENAI_API_KEY="your-key-here"
```

### Проблемы с БД
```bash
# Проверка структуры
sqlite3 entertainment.db ".schema places"
```

### Ошибки веб-поиска
- Проверьте интернет-соединение
- Возможны временные блокировки

## 📚 Дополнительно

- [README AI Editor](apps/places/workers/README_AI_EDITOR.md)
- [Документация парсеров](docs/parser_documentation.md)
- [Схема БД](SCHEMA.md)
