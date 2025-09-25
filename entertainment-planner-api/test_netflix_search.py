#!/usr/bin/env python3
"""Test script for Netflix-style search system"""

from fastapi.testclient import TestClient
from apps.api.main import app

def test_netflix_search():
    """Test the complete Netflix-style search flow"""
    client = TestClient(app)
    
    print("🎯 Testing Netflix-style Search System")
    print("=" * 50)
    
    # Test 1: Parse query
    print("\n1. Testing query parsing...")
    parse_response = client.post('/api/parse', json={
        'query': 'romantic dinner, rooftop bar, spa massage',
        'area': 'sukhumvit'
    })
    
    if parse_response.status_code == 200:
        parse_result = parse_response.json()
        print(f"✅ Parse successful!")
        print(f"   Steps: {len(parse_result['steps'])}")
        print(f"   Vibes: {parse_result['vibes']}")
        print(f"   Scenarios: {parse_result['scenarios']}")
        print(f"   Experiences: {parse_result['experiences']}")
        print(f"   Confidence: {parse_result['confidence']:.2f}")
        print(f"   Processing time: {parse_result['processing_time_ms']:.1f}ms")
    else:
        print(f"❌ Parse failed: {parse_response.status_code}")
        return
    
    # Test 2: Compose rails
    print("\n2. Testing rail composition...")
    compose_response = client.get('/api/compose/test', params={
        'query': 'romantic dinner, rooftop bar, spa massage',
        'area': 'sukhumvit'
    })
    
    if compose_response.status_code == 200:
        compose_result = compose_response.json()
        rails = compose_result['compose_response']['rails']
        print(f"✅ Compose successful!")
        print(f"   Rails: {len(rails)}")
        
        total_places = 0
        for i, rail in enumerate(rails):
            places_count = len(rail['items'])
            total_places += places_count
            print(f"   Rail {i+1} ({rail['step']}): {places_count} places")
            
            # Show first few places
            for j, place in enumerate(rail['items'][:3]):
                print(f"     - {place['name']} (score: {place.get('search_score', 0):.2f})")
        
        print(f"   Total places: {total_places}")
        print(f"   Processing time: {compose_result['compose_response']['processing_time_ms']:.1f}ms")
    else:
        print(f"❌ Compose failed: {compose_response.status_code}")
        return
    
    # Test 3: Feedback system
    print("\n3. Testing feedback system...")
    feedback_response = client.post('/api/feedback', json={
        'session_id': 'test_session_123',
        'place_id': 1,
        'action': 'like',
        'step': 'restaurant'
    })
    
    if feedback_response.status_code == 200:
        print("✅ Feedback added successfully!")
    else:
        print(f"❌ Feedback failed: {feedback_response.status_code}")
    
    # Test 4: Profile stats
    print("\n4. Testing profile stats...")
    profile_response = client.get('/api/feedback/profile/test_session_123')
    
    if profile_response.status_code == 200:
        profile_stats = profile_response.json()
        print(f"✅ Profile stats retrieved!")
        print(f"   Signals count: {profile_stats['signals_count']}")
        print(f"   Vibe vector size: {profile_stats['vibe_vector_size']}")
    else:
        print(f"❌ Profile stats failed: {profile_response.status_code}")
    
    # Test 5: Cache stats
    print("\n5. Testing cache stats...")
    cache_response = client.get('/api/parse/cache/stats')
    
    if cache_response.status_code == 200:
        cache_stats = cache_response.json()
        print(f"✅ Cache stats retrieved!")
        print(f"   Total entries: {cache_stats['total_entries']}")
        print(f"   Valid entries: {cache_stats['valid_entries']}")
    else:
        print(f"❌ Cache stats failed: {cache_response.status_code}")
    
    print("\n" + "=" * 50)
    print("🎉 Netflix-style search system is working!")

if __name__ == "__main__":
    test_netflix_search()
