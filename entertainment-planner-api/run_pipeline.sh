#!/bin/bash
# Скрипт для запуска цепочки обработки данных

# Активируем виртуальное окружение
source ../venv/bin/activate

# Устанавливаем PYTHONPATH
export PYTHONPATH="/Users/user/entertainment planner/entertainment-planner-api"

echo "🚀 Запуск цепочки обработки данных Entertainment Planner"
echo "📁 Рабочая директория: $(pwd)"
echo "🐍 Python: $(which python)"
echo "📦 PYTHONPATH: $PYTHONPATH"
echo ""

# Проверяем аргументы
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Использование:"
    echo "  ./run_pipeline.sh                    # Полная цепочка"
    echo "  ./run_pipeline.sh gpt                # Только GPT обработка"
    echo "  ./run_pipeline.sh google             # Только Google обогащение"
    echo "  ./run_pipeline.sh ai_editor          # Только AI Editor"
    echo "  ./run_pipeline.sh --help             # Эта справка"
    exit 0
fi

# Запускаем соответствующую команду
if [ -z "$1" ]; then
    echo "🔄 Запуск полной цепочки обработки..."
    python run_full_pipeline.py
elif [ "$1" = "gpt" ]; then
    echo "🤖 Запуск GPT Normalizer..."
    python run_full_pipeline.py --stage gpt
elif [ "$1" = "google" ]; then
    echo "🗺️ Запуск Google API Enricher..."
    python run_full_pipeline.py --stage google
elif [ "$1" = "ai_editor" ]; then
    echo "✏️ Запуск AI Editor Agent..."
    python run_full_pipeline.py --stage ai_editor
else
    echo "❌ Неизвестный этап: $1"
    echo "Используйте --help для справки"
    exit 1
fi

echo ""
echo "✅ Выполнение завершено!"
