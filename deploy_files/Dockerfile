# Python slim, без глобальных кешей
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Системные зависимости по необходимости (psycopg, gcc не нужен для psycopg-binary)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates && rm -rf /var/lib/apt/lists/*

# Копируем зависимости и ставим
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем приложение
COPY . /app

# Вписываем git-хеш в ENV (передаём через --build-arg BUILD_REF)
ARG BUILD_REF=unknown
ENV APP_BUILD=${BUILD_REF}

# Порт для uvicorn
ENV PORT=8000
EXPOSE 8000

# Важно: без statement_timeout в options (PgBouncer)
# Запуск
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]