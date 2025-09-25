#!/usr/bin/env python3
"""Заполняет description_full для мест, где оно пустое, и пишет summary.

- Берёт из Postgres места с пустым description_full
- Для каждого вызывает GPTClient.generate_description_and_summary
- Сохраняет description_full и summary, обновляет updated_at
"""

import logging
from datetime import datetime, timezone, timedelta

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.workers.gpt_client import GPTClient


logger = logging.getLogger(__name__)


def run(batch_size: int = 5):
    db = SessionLocal()
    try:
        client = GPTClient(api_key=_get_api_key())
        while True:
            cutoff = datetime.now(timezone.utc) - timedelta(hours=2)
            items = (
                db.query(Place)
                .filter((Place.description_full.is_(None)) | (Place.description_full == ""))
                .filter((Place.updated_at.is_(None)) | (Place.updated_at < cutoff))
                .limit(batch_size)
                .all()
            )
            if not items:
                logger.info("Нет записей для дополнения описаний")
                break

            for p in items:
                payload = {
                    "id": p.id,
                    "name": p.name,
                    "area": _infer_area(p),
                }
                res = client.generate_description_and_summary(payload)
                # записываем только если нашли реальный веб-контент
                if res.get("description_full"):
                    p.description_full = res["description_full"].strip()
                if res.get("summary"):
                    p.summary = res["summary"].strip()
                p.updated_at = datetime.now(timezone.utc)
                db.flush()
                db.commit()
                logger.info(f"Place {p.id} updated (desc & summary)")
    finally:
        db.close()


def _get_api_key() -> str:
    import os
    k = os.getenv("OPENAI_API_KEY")
    if not k:
        raise ValueError("OPENAI_API_KEY не найден в окружении")
    return k


def _infer_area(p: Place) -> str:
    # Простая эвристика: из адреса вытянуть район, иначе пусто
    addr = (p.address or "").lower()
    for token in [
        "sukhumvit",
        "thonglor",
        "sathorn",
        "silom",
        "ari",
        "ratchathewi",
        "phra nakhon",
        "bang rak",
        "pathum wan",
    ]:
        if token in addr:
            return token
    return "Bangkok"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(batch_size=5)


