#!/usr/bin/env python3
"""
Команда для пересбора всех описаний из BK Magazine с улучшенным алгоритмом
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from apps.core.db import SessionLocal
from apps.places.models import Place
from apps.places.ingestion.bk_magazine_adapter import BKMagazineAdapter
from sqlalchemy import func
import logging

logger = logging.getLogger(__name__)

def rebuild_bk_descriptions():
    """Пересобирает все описания из BK Magazine с улучшенным алгоритмом"""
    print("🔄 ПЕРЕСБОР ОПИСАНИЙ ИЗ BK MAGAZINE")
    print("=" * 60)
    
    db = SessionLocal()
    adapter = BKMagazineAdapter()
    
    try:
        # Получаем все места из BK Magazine
        bk_places = db.query(Place).filter(Place.source == 'bk_magazine').all()
        print(f"Найдено мест из BK Magazine: {len(bk_places)}")
        
        # Группируем по статьям
        articles = {}
        for place in bk_places:
            if place.source_url:
                article_url = place.source_url.split('#')[0]  # Убираем якорь
                if article_url not in articles:
                    articles[article_url] = []
                articles[article_url].append(place)
        
        print(f"Найдено статей: {len(articles)}")
        
        total_updated = 0
        total_errors = 0
        
        # Обрабатываем каждую статью
        for i, (article_url, places) in enumerate(articles.items(), 1):
            print(f"\n📰 СТАТЬЯ {i}: {article_url.split('/')[-1]}")
            print("-" * 50)
            
            try:
                # Парсим статью заново с улучшенным алгоритмом
                new_places = adapter.parse_article_page(article_url)
                print(f"   Парсинг: найдено {len(new_places)} мест")
                
                # Создаем словарь новых мест по названиям
                new_places_dict = {p['title']: p for p in new_places}
                
                # Обновляем существующие места
                updated_count = 0
                for place in places:
                    place_name = place.name
                    if place_name in new_places_dict:
                        new_place = new_places_dict[place_name]
                        
                        # Обновляем описание
                        old_description = place.description_full
                        new_description = new_place['teaser']
                        
                        if new_description and len(new_description) > 50:
                            place.description_full = new_description
                            place.processing_status = "new"  # Сбрасываем статус для переобработки
                            updated_count += 1
                            
                            # Логируем изменения
                            if old_description != new_description:
                                print(f"   ✅ {place_name}: обновлено описание")
                            else:
                                print(f"   ➡️ {place_name}: описание не изменилось")
                        else:
                            print(f"   ⚠️ {place_name}: нет описания в новом парсинге")
                    else:
                        print(f"   ❌ {place_name}: не найдено в новом парсинге")
                
                print(f"   Обновлено мест: {updated_count}")
                total_updated += updated_count
                
            except Exception as e:
                print(f"   ❌ Ошибка при обработке статьи: {e}")
                total_errors += 1
                logger.error(f"Ошибка при обработке статьи {article_url}: {e}")
        
        # Сохраняем изменения
        db.commit()
        
        print(f"\n📊 ИТОГИ ПЕРЕСБОРА:")
        print(f"   Всего мест: {len(bk_places)}")
        print(f"   Обновлено: {total_updated}")
        print(f"   Ошибок: {total_errors}")
        print(f"   Успешность: {total_updated/len(bk_places)*100:.1f}%")
        
        # Проверяем результат
        places_with_descriptions = db.query(Place).filter(
            Place.source == 'bk_magazine',
            Place.description_full.isnot(None),
            Place.description_full != ''
        ).count()
        
        print(f"\n📈 РЕЗУЛЬТАТ:")
        print(f"   Мест с описаниями: {places_with_descriptions} ({places_with_descriptions/len(bk_places)*100:.1f}%)")
        
        if places_with_descriptions >= len(bk_places) * 0.95:
            print("   🎉 ОТЛИЧНО! 95%+ мест имеют описания!")
        elif places_with_descriptions >= len(bk_places) * 0.9:
            print("   ✅ ХОРОШО! 90%+ мест имеют описания!")
        else:
            print("   ⚠️ Нужно еще улучшить алгоритм")
            
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        logger.error(f"Критическая ошибка в rebuild_bk_descriptions: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    rebuild_bk_descriptions()
