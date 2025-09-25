#!/usr/bin/env python3
"""
Скрипт для обработки мест из CSV файла с новым промптом саммаризатора
"""

import csv
import json
import requests
import time
from datetime import datetime
from typing import Dict, Any

# Настройки
CSV_FILE = "/Users/user/entertainment planner/docs/places.csv/racquet___Muay_Thai___Batch_01.csv"
API_BASE = "http://127.0.0.1:8001/api"
BATCH_SIZE = 5  # Обрабатываем по 5 мест за раз

def load_places_from_csv(file_path: str) -> list:
    """Загружаем места из CSV файла"""
    places = []
    
    with open(file_path, 'r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if row['name'].strip():  # Пропускаем пустые строки
                places.append({
                    'name': row['name'].strip(),
                    'description_full': row['description_full'].strip(),
                    'source_url': row['source_url'].strip()
                })
    
    return places

def create_place_payload(place_data: Dict[str, Any], place_id: str) -> Dict[str, Any]:
    """Создаем payload для обработки места"""
    return {
        "id": place_id,
        "name": place_data['name'],
        "description_full": place_data['description_full'],
        "category": "fitness_gym",  # Muay Thai gyms
        "tags_csv": "",
        "summary": "",
        "hours_json": None,
        "gmaps_url": ""
    }

def process_place_with_gpt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Отправляем место на обработку через GPT API"""
    try:
        response = requests.post(
            f"{API_BASE}/places/summarize",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Ошибка API для {payload['name']}: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Исключение при обработке {payload['name']}: {e}")
        return None

def save_processed_place(place_data: Dict[str, Any], gpt_result: Dict[str, Any]) -> None:
    """Сохраняем обработанное место в базу данных"""
    try:
        # Создаем новое место в базе
        create_payload = {
            "name": place_data['name'],
            "description": gpt_result.get('summary', ''),
            "category": gpt_result.get('tags', [{}])[0].split(':')[1] if gpt_result.get('tags') else 'fitness_gym',
            "tags_csv": ','.join(gpt_result.get('tags', [])),
            "summary": gpt_result.get('summary', ''),
            "lat": 13.7563,  # Bangkok center
            "lng": 100.5018,
            "source": "muay_thai_batch_01",
            "source_url": place_data['source_url'],
            "processing_status": "published"
        }
        
        response = requests.post(
            f"{API_BASE}/places",
            json=create_payload,
            timeout=10
        )
        
        if response.status_code == 200:
            print(f"✅ Сохранено: {place_data['name']}")
        else:
            print(f"❌ Ошибка сохранения {place_data['name']}: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка сохранения {place_data['name']}: {e}")

def main():
    """Основная функция"""
    print("🏋️‍♂️ Начинаем обработку Muay Thai мест...")
    
    # Загружаем места из CSV
    places = load_places_from_csv(CSV_FILE)
    print(f"📊 Загружено {len(places)} мест из CSV")
    
    # Обрабатываем места батчами
    for i in range(0, len(places), BATCH_SIZE):
        batch = places[i:i+BATCH_SIZE]
        print(f"\n🔄 Обрабатываем батч {i//BATCH_SIZE + 1} ({len(batch)} мест)")
        
        for j, place_data in enumerate(batch):
            place_id = f"muay_thai_{i+j+1:03d}"
            print(f"\n📍 {j+1}/{len(batch)}: {place_data['name']}")
            
            # Создаем payload
            payload = create_place_payload(place_data, place_id)
            
            # Обрабатываем через GPT
            gpt_result = process_place_with_gpt(payload)
            
            if gpt_result:
                print(f"🤖 GPT результат:")
                print(f"   Summary: {gpt_result.get('summary', 'N/A')[:100]}...")
                print(f"   Tags: {len(gpt_result.get('tags', []))} тегов")
                print(f"   Confidence: {gpt_result.get('confidence', 'N/A')}")
                
                # Сохраняем в базу
                save_processed_place(place_data, gpt_result)
            else:
                print(f"❌ Пропускаем {place_data['name']} из-за ошибки обработки")
            
            # Небольшая пауза между запросами
            time.sleep(1)
        
        # Пауза между батчами
        if i + BATCH_SIZE < len(places):
            print(f"\n⏳ Пауза 3 секунды перед следующим батчем...")
            time.sleep(3)
    
    print(f"\n🎉 Обработка завершена! Обработано {len(places)} мест.")

if __name__ == "__main__":
    main()
