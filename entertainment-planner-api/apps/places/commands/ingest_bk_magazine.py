"""
Команда для ингестии данных из BK Magazine
"""
import logging
from typing import List
from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.ingestion.bk_magazine_adapter import BKMagazineAdapter
from datetime import datetime

logger = logging.getLogger(__name__)


def _determine_category(name: str, description: str) -> str:
    """
    Определяет категорию места на основе названия и описания
    """
    if not name and not description:
        return 'Unknown'
    
    text = f"{name} {description}".lower()
    
    # Спа-салоны
    spa_keywords = ['spa', 'massage', 'wellness', 'treatment', 'therapy', 'relaxation', 'onsen']
    if any(keyword in text for keyword in spa_keywords):
        return 'Spa'
    
    # Рестораны и кафе
    food_keywords = ['restaurant', 'cafe', 'coffee', 'dining', 'food', 'kitchen', 'bistro', 'eatery']
    if any(keyword in text for keyword in food_keywords):
        return 'Restaurant'
    
    # Бары
    bar_keywords = ['bar', 'cocktail', 'drink', 'rooftop', 'lounge', 'pub']
    if any(keyword in text for keyword in bar_keywords):
        return 'Bar'
    
    # По умолчанию
    return 'Entertainment'


def ingest_bk_magazine_article(article_url: str, limit: int = None) -> int:
    """
    Ингестия мест из статьи BK Magazine
    
    Args:
        article_url: URL статьи BK Magazine
        limit: Ограничение количества мест (опционально)
    
    Returns:
        Количество добавленных мест
    """
    logger.info(f"Начинаем ингестию из BK Magazine: {article_url}")
    
    # Создаем адаптер
    adapter = BKMagazineAdapter()
    
    # Парсим статью
    places_data = adapter.parse_article_page(article_url)
    
    if not places_data:
        logger.warning("Не найдено мест в статье")
        return 0
    
    logger.info(f"Спарсено {len(places_data)} мест")
    
    # Ограничиваем количество если нужно
    if limit:
        places_data = places_data[:limit]
        logger.info(f"Ограничено до {limit} мест")
    
    # Сохраняем в базу данных
    db = SessionLocal()
    added_count = 0
    skipped_count = 0
    
    try:
        for place_data in places_data:
            try:
                # Проверяем, существует ли место
                existing_place = db.query(Place).filter(
                    Place.name == place_data['title']
                ).first()
                
                if existing_place:
                    logger.info(f"Место уже существует: {place_data['title']}")
                    skipped_count += 1
                    continue
                
                # Создаем уникальный source_url для каждого места
                unique_source_url = f"{article_url}#{place_data['title'].replace(' ', '_')}"
                
                # Определяем категорию на основе содержимого
                category = _determine_category(place_data['title'], place_data['teaser'])
                
                # Создаем новое место
                place = Place(
                    source='bk_magazine',
                    source_url=unique_source_url,
                    raw_payload=f"<article>{place_data['title']}</article>",  # Минимальный payload
                    scraped_at=datetime.utcnow(),
                    name=place_data['title'],
                    category=category,
                    description_full=place_data['teaser'],
                    address=place_data['address_fallback'],
                    processing_status='new'
                )
                
                db.add(place)
                db.commit()
                
                logger.info(f"Добавлено место: {place_data['title']}")
                added_count += 1
                
            except Exception as e:
                logger.error(f"Ошибка добавления места {place_data['title']}: {e}")
                db.rollback()
                continue
        
        logger.info("Ингестия завершена:")
        logger.info(f"- Добавлено новых мест: {added_count}")
        logger.info(f"- Пропущено существующих: {skipped_count}")
        
        return added_count
        
    except Exception as e:
        logger.error(f"Ошибка ингестии: {e}")
        db.rollback()
        return 0
    finally:
        db.close()


def ingest_bk_magazine_articles(article_urls: List[str], limit: int = None) -> int:
    """
    Ингестия мест из нескольких статей BK Magazine
    
    Args:
        article_urls: Список URL статей BK Magazine
        limit: Ограничение количества мест на статью (опционально)
    
    Returns:
        Общее количество добавленных мест
    """
    total_added = 0
    
    for i, url in enumerate(article_urls, 1):
        logger.info(f"\\nОбрабатываем статью {i}/{len(article_urls)}: {url}")
        
        try:
            added = ingest_bk_magazine_article(url, limit)
            total_added += added
        except Exception as e:
            logger.error(f"Ошибка обработки статьи {url}: {e}")
            continue
    
    logger.info(f"\\nОбщая ингестия завершена. Всего добавлено: {total_added}")
    return total_added


if __name__ == "__main__":
    # Тестируем на одной статье
    test_url = 'https://bk.asia-city.com/nightlife/article/bangkoks-best-rooftop-bars'
    result = ingest_bk_magazine_article(test_url)
    print(f"Результат: {result} мест добавлено")
