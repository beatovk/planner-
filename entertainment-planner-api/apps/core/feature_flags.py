"""
Feature flags for controlling system behavior.
"""

import os
import logging
from typing import Dict, Any, Optional
from functools import lru_cache

logger = logging.getLogger(__name__)


class FeatureFlags:
    """Feature flags manager."""
    
    def __init__(self):
        self._flags = {}
        self._load_from_env()
    
    def _load_from_env(self) -> None:
        """Load feature flags from environment variables."""
        # Slotter feature flags
        self._flags['SLOTTER_WIDE'] = os.getenv('SLOTTER_WIDE', 'off').lower() in ['on', 'true', '1']
        self._flags['SLOTTER_SHADOW'] = os.getenv('SLOTTER_SHADOW', 'off').lower() in ['on', 'true', '1']
        self._flags['SLOTTER_AB_TEST'] = os.getenv('SLOTTER_AB_TEST', 'off').lower() in ['on', 'true', '1']
        self._flags['SLOTTER_DEBUG'] = os.getenv('SLOTTER_DEBUG', 'off').lower() in ['on', 'true', '1']
        
        # Performance flags
        self._flags['SLOTTER_CACHE_TTL'] = int(os.getenv('SLOTTER_CACHE_TTL', '300'))  # 5 minutes
        self._flags['SLOTTER_MAX_SLOTS'] = int(os.getenv('SLOTTER_MAX_SLOTS', '3'))
        self._flags['SLOTTER_MIN_CONFIDENCE'] = float(os.getenv('SLOTTER_MIN_CONFIDENCE', '0.3'))
        
        # A/B testing flags
        self._flags['SLOTTER_AB_RATIO'] = float(os.getenv('SLOTTER_AB_RATIO', '0.1'))  # 10% traffic
        
        logger.info(f"Feature flags loaded: {self._flags}")
    
    def is_enabled(self, flag_name: str) -> bool:
        """Check if a feature flag is enabled."""
        return self._flags.get(flag_name, False)
    
    def get_value(self, flag_name: str, default: Any = None) -> Any:
        """Get feature flag value."""
        return self._flags.get(flag_name, default)
    
    def set_flag(self, flag_name: str, value: Any) -> None:
        """Set feature flag value (runtime override)."""
        self._flags[flag_name] = value
        logger.info(f"Feature flag {flag_name} set to {value}")
    
    def get_all_flags(self) -> Dict[str, Any]:
        """Get all feature flags."""
        return self._flags.copy()
    
    def reload_from_env(self) -> None:
        """Reload feature flags from environment."""
        self._load_from_env()
        logger.info("Feature flags reloaded from environment")


# Global instance
_feature_flags = None


def get_feature_flags() -> FeatureFlags:
    """Get global feature flags instance."""
    global _feature_flags
    if _feature_flags is None:
        _feature_flags = FeatureFlags()
    return _feature_flags


def reset_feature_flags() -> None:
    """Reset global feature flags instance."""
    global _feature_flags
    _feature_flags = None


def is_slotter_enabled() -> bool:
    """Check if slotter is enabled."""
    return get_feature_flags().is_enabled('SLOTTER_WIDE')


def is_slotter_shadow_mode() -> bool:
    """Check if slotter is in shadow mode."""
    return get_feature_flags().is_enabled('SLOTTER_SHADOW')


def is_slotter_ab_test() -> bool:
    """Check if slotter A/B testing is enabled."""
    return get_feature_flags().is_enabled('SLOTTER_AB_TEST')


def is_slotter_debug() -> bool:
    """Check if slotter debug mode is enabled."""
    return get_feature_flags().is_enabled('SLOTTER_DEBUG')


def get_slotter_config() -> Dict[str, Any]:
    """Get slotter configuration from feature flags."""
    flags = get_feature_flags()
    return {
        'enabled': flags.is_enabled('SLOTTER_WIDE'),
        'shadow_mode': flags.is_enabled('SLOTTER_SHADOW'),
        'ab_test': flags.is_enabled('SLOTTER_AB_TEST'),
        'debug': flags.is_enabled('SLOTTER_DEBUG'),
        'cache_ttl': flags.get_value('SLOTTER_CACHE_TTL', 300),
        'max_slots': flags.get_value('SLOTTER_MAX_SLOTS', 3),
        'min_confidence': flags.get_value('SLOTTER_MIN_CONFIDENCE', 0.3),
        'ab_ratio': flags.get_value('SLOTTER_AB_RATIO', 0.1)
    }


# Utility functions for common checks
def should_use_slotter(query: str) -> bool:
    """Determine if slotter should be used for a query."""
    flags = get_feature_flags()
    if not flags.is_enabled('SLOTTER_WIDE'):
        return False
    
    # Check if query looks like free-text (not structured)
    if not query or len(query.strip()) < 3:
        return False
    
    # Check for obvious structured queries
    structured_indicators = ['mode=', 'vibe=', 'energy=', 'area=']
    if any(indicator in query.lower() for indicator in structured_indicators):
        return False
    
    return True


def should_log_slotter(query: str) -> bool:
    """Determine if slotter should be logged (shadow mode)."""
    flags = get_feature_flags()
    return flags.is_enabled('SLOTTER_SHADOW') or flags.is_enabled('SLOTTER_DEBUG')


def should_ab_test_slotter(query: str) -> bool:
    """Determine if query should be A/B tested."""
    flags = get_feature_flags()
    if not flags.is_enabled('SLOTTER_AB_TEST'):
        return False
    
    # Simple hash-based A/B testing
    import hashlib
    hash_value = int(hashlib.md5(query.encode()).hexdigest()[:8], 16)
    ratio = flags.get_value('SLOTTER_AB_RATIO', 0.1)
    
    return (hash_value % 100) < (ratio * 100)


if __name__ == "__main__":
    # Test feature flags
    flags = get_feature_flags()
    print("🔍 Feature Flags Test:")
    print(f"   - SLOTTER_WIDE: {flags.is_enabled('SLOTTER_WIDE')}")
    print(f"   - SLOTTER_SHADOW: {flags.is_enabled('SLOTTER_SHADOW')}")
    print(f"   - SLOTTER_AB_TEST: {flags.is_enabled('SLOTTER_AB_TEST')}")
    print(f"   - SLOTTER_DEBUG: {flags.is_enabled('SLOTTER_DEBUG')}")
    print(f"   - Config: {get_slotter_config()}")
    
    # Test utility functions
    test_queries = [
        "chill, tom yum, rooftop",
        "mode=vibe&vibe=chill",
        "gallery, tea, sushi"
    ]
    
    print("\n🎯 Utility Functions Test:")
    for query in test_queries:
        print(f"   - Query: '{query}'")
        print(f"     - should_use_slotter: {should_use_slotter(query)}")
        print(f"     - should_log_slotter: {should_log_slotter(query)}")
        print(f"     - should_ab_test_slotter: {should_ab_test_slotter(query)}")
