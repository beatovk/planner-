"""
Команда для массового парсинга каталога BK Magazine
"""
import logging
from typing import List, Dict, Any
from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.ingestion.bk_magazine_adapter import BKMagazineAdapter
from apps.places.workers.gpt_normalizer import GPTNormalizerWorker
from apps.places.commands.enrich_bk_google import enrich_bk_places
from datetime import datetime

logger = logging.getLogger(__name__)


def ingest_catalog(catalog_url: str, limit: int = None, max_pages: int = None, dry_run: bool = False):
    """
    Массовый парсинг каталога BK Magazine
    
    Args:
        catalog_url: URL страницы каталога
        limit: Ограничение количества статей (опционально)
        max_pages: Максимальное количество страниц для парсинга (опционально)
        dry_run: Режим тестирования без сохранения в БД
    """
    print(f"🚀 МАССОВЫЙ ПАРСИНГ КАТАЛОГА BK MAGAZINE")
    print(f"URL: {catalog_url}")
    print(f"Ограничение статей: {limit or 'Нет'}")
    print(f"Ограничение страниц: {max_pages or 'Нет'}")
    print(f"Режим: {'Тестирование' if dry_run else 'Продакшн'}")
    print("=" * 70)
    
    try:
        # Инициализация адаптера
        adapter = BKMagazineAdapter()
        
        # Парсинг каталога и статей
        print("\\n📖 ПАРСИНГ КАТАЛОГА И СТАТЕЙ...")
        places = adapter.parse_catalog_articles(catalog_url, limit=limit, max_pages=max_pages)
        
        if not places:
            print("❌ Места не найдены!")
            return
        
        print(f"\\n📊 НАЙДЕНО МЕСТ: {len(places)}")
        
        if dry_run:
            print("\\n🔍 РЕЖИМ ТЕСТИРОВАНИЯ - Показываем примеры:")
            for i, place in enumerate(places[:5], 1):
                print(f"{i:2d}. {place['title']}")
                print(f"    Статья: {place.get('article_title', 'Неизвестно')}")
                print(f"    Описание: {place['teaser'][:100]}...")
                print()
            return
        
        # Сохранение в БД
        print("\\n💾 СОХРАНЕНИЕ В БД...")
        db = SessionLocal()
        added_count = 0
        skipped_count = 0
        total_places = len(places)
        
        try:
            for i, place_data in enumerate(places, 1):
                # Показываем прогресс каждые 10 мест
                if i % 10 == 0 or i == total_places:
                    print(f"   Обработано: {i}/{total_places} мест...")
                
                # Проверяем, есть ли уже такое место
                existing = db.query(Place).filter(
                    Place.name == place_data['title'],
                    Place.source == 'bk_magazine'
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Создаем новое место
                place = Place(
                    source='bk_magazine',
                    source_url=place_data.get('article_url', catalog_url),
                    raw_payload=f"<article>{place_data['title']}</article>",
                    scraped_at=datetime.utcnow(),
                    name=place_data['title'],
                    category='Restaurant',
                    description_full=place_data['teaser'],
                    processing_status='new'
                )
                
                db.add(place)
                added_count += 1
                
                if added_count % 10 == 0:
                    print(f"   Добавлено: {added_count} мест...")
            
            db.commit()
            print(f"✅ Сохранено в БД: {added_count} новых мест")
            print(f"➡️ Пропущено: {skipped_count} существующих мест")
            
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка сохранения в БД: {e}")
            return
        finally:
            db.close()
        
        # Саммаризация через GPT
        print("\\n🤖 САММАРИЗАЦИЯ ЧЕРЕЗ GPT...")
        try:
            worker = GPTNormalizerWorker()
            worker.run()
            print("✅ Саммаризация завершена")
        except Exception as e:
            print(f"❌ Ошибка саммаризации: {e}")
        
        # Обогащение через Google API
        print("\\n🌍 ОБОГАЩЕНИЕ ЧЕРЕЗ GOOGLE API...")
        try:
            enrich_bk_places(batch_size=50, dry_run=False)
            print("✅ Обогащение завершено")
        except Exception as e:
            print(f"❌ Ошибка обогащения: {e}")
        
        # Финальная статистика
        print("\\n📈 ФИНАЛЬНАЯ СТАТИСТИКА:")
        db = SessionLocal()
        try:
            total_bk = db.query(Place).filter(Place.source == 'bk_magazine').count()
            with_coords = db.query(Place).filter(
                Place.source == 'bk_magazine',
                Place.lat.isnot(None),
                Place.lng.isnot(None)
            ).count()
            with_gmaps_id = db.query(Place).filter(
                Place.source == 'bk_magazine',
                Place.gmaps_place_id.isnot(None)
            ).count()
            
            print(f"Всего мест BK Magazine: {total_bk}")
            print(f"С координатами: {with_coords} ({with_coords/total_bk*100:.1f}%)")
            print(f"С Google ID: {with_gmaps_id} ({with_gmaps_id/total_bk*100:.1f}%)")
            
        finally:
            db.close()
        
        print("\\n🎉 МАССОВЫЙ ПАРСИНГ ЗАВЕРШЕН!")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        logger.error(f"Ошибка массового парсинга каталога: {e}")


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # Пример использования
    catalog_url = "https://bk.asia-city.com/search-news?type=restaurant"
    
    # Полный парсинг всех страниц (360 ресторанов)
    print("🚀 ПОЛНЫЙ ПАРСИНГ ВСЕХ СТРАНИЦ (360 ресторанов):")
    ingest_catalog(catalog_url, max_pages=None, dry_run=False)
    
    # Тестирование с ограничением (раскомментировать для тестов)
    # print("\\n🧪 ТЕСТИРОВАНИЕ С ОГРАНИЧЕНИЕМ 2 СТРАНИЦЫ (48 ресторанов):")
    # ingest_catalog(catalog_url, max_pages=2, dry_run=True)
    
    # Парсинг с ограничением по страницам
    # print("\\n🚀 ПАРСИНГ 5 СТРАНИЦ (120 ресторанов):")
    # ingest_catalog(catalog_url, max_pages=5, dry_run=False)
