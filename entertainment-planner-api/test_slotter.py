#!/usr/bin/env python3
"""
Test slotter functionality
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from apps.core.feature_flags import get_feature_flags, should_use_slotter
from apps.places.services.query_builder import create_query_builder

def test_feature_flags():
    """Test feature flags"""
    print("🔍 Testing Feature Flags:")
    flags = get_feature_flags()
    print(f"   - SLOTTER_WIDE: {flags.is_enabled('SLOTTER_WIDE')}")
    print(f"   - SLOTTER_SHADOW: {flags.is_enabled('SLOTTER_SHADOW')}")
    print(f"   - SLOTTER_DEBUG: {flags.is_enabled('SLOTTER_DEBUG')}")
    print(f"   - All flags: {flags.get_all_flags()}")
    
    # Test utility functions
    test_queries = [
        "chill coffee rooftop",
        "coffee rooftop",
        "chill coffee",
        "mode=vibe&vibe=chill"
    ]
    
    print("\n🎯 Testing Utility Functions:")
    for query in test_queries:
        print(f"   - Query: '{query}'")
        print(f"     - should_use_slotter: {should_use_slotter(query)}")

def test_query_builder():
    """Test query builder"""
    print("\n🔧 Testing Query Builder:")
    try:
        query_builder = create_query_builder()
        print(f"   - Synonyms loaded: {len(query_builder.synonyms)}")
        
        # Test slot extraction
        test_queries = [
            "chill coffee rooftop",
            "coffee rooftop",
            "chill coffee",
            "romantic dinner"
        ]
        
        for query in test_queries:
            print(f"\n   - Testing query: '{query}'")
            result = query_builder.build_slots(query)
            print(f"     - Slots found: {len(result.slots)}")
            for slot in result.slots:
                print(f"       - {slot.type}: {slot.canonical} (confidence: {slot.confidence:.2f})")
            print(f"     - Fallback used: {result.fallback_used}")
            if result.fallback_reason:
                print(f"     - Fallback reason: {result.fallback_reason}")
                
    except Exception as e:
        print(f"   - Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_feature_flags()
    test_query_builder()
