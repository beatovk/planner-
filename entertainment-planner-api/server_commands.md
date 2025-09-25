# Команды для управления сервером

## Запуск сервера
```bash
screen -S fastapi-server -d -m ./start_server.sh
```

## Просмотр логов сервера
```bash
screen -r fastapi-server
```
(Для выхода из просмотра логов нажмите `Ctrl+A`, затем `D`)

## Остановка сервера
```bash
screen -S fastapi-server -X quit
```

## Проверка статуса сервера
```bash
screen -list
```

## Тестирование API
```bash
# Health check
curl http://localhost:8000/api/health

# Список мест
curl http://localhost:8000/api/places

# Корневой эндпоинт
curl http://localhost:8000/
```

## Перезапуск сервера
```bash
# Остановить
screen -S fastapi-server -X quit

# Запустить заново
screen -S fastapi-server -d -m ./start_server.sh
```

## Просмотр документации API
Откройте в браузере: http://localhost:8000/docs
