#!/bin/bash
# Скрипт для запуска FastAPI сервера

# Активируем виртуальное окружение
source ../venv/bin/activate

# Переходим в директорию проекта
cd "/Users/user/entertainment planner/entertainment-planner-api"

# Запускаем сервер с автоперезагрузкой
echo "Запуск FastAPI сервера на http://localhost:8000"
echo "Для остановки нажмите Ctrl+C"
echo "================================================"

uvicorn apps.api.main:app --host 0.0.0.0 --port 8000 --reload
