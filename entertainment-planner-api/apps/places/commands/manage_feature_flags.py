"""
Command-line tool for managing feature flags.
"""

import argparse
import os
import sys
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from apps.core.feature_flags import get_feature_flags, get_slotter_config, reset_feature_flags


def show_flags():
    """Show all feature flags."""
    flags = get_feature_flags()
    config = get_slotter_config()
    
    print("🔍 Feature Flags Status:")
    print()
    
    print("📊 All Flags:")
    for flag_name, value in flags.get_all_flags().items():
        status = "✅" if value else "❌"
        print(f"   - {flag_name}: {status} {value}")
    
    print()
    print("🎯 Slotter Configuration:")
    for key, value in config.items():
        print(f"   - {key}: {value}")
    
    print()
    print("🌍 Environment Variables:")
    env_vars = [
        'SLOTTER_WIDE', 'SLOTTER_SHADOW', 'SLOTTER_AB_TEST', 'SLOTTER_DEBUG',
        'SLOTTER_CACHE_TTL', 'SLOTTER_MAX_SLOTS', 'SLOTTER_MIN_CONFIDENCE', 'SLOTTER_AB_RATIO'
    ]
    for var in env_vars:
        value = os.getenv(var, 'not set')
        print(f"   - {var}: {value}")


def test_flags():
    """Test feature flag functionality."""
    from apps.core.feature_flags import (
        should_use_slotter, should_log_slotter, should_ab_test_slotter
    )
    
    print("🧪 Testing Feature Flag Functions:")
    print()
    
    # Show current flags first
    flags = get_feature_flags()
    print(f"Current SLOTTER_WIDE: {flags.is_enabled('SLOTTER_WIDE')}")
    print(f"Current SLOTTER_SHADOW: {flags.is_enabled('SLOTTER_SHADOW')}")
    print(f"Current SLOTTER_AB_TEST: {flags.is_enabled('SLOTTER_AB_TEST')}")
    print()
    
    test_queries = [
        "chill, tom yum, rooftop",
        "mode=vibe&vibe=chill",
        "gallery, tea, sushi",
        "romantic dinner with wine",
        "thai food in thonglor"
    ]
    
    for query in test_queries:
        print(f"Query: '{query}'")
        print(f"   - should_use_slotter: {should_use_slotter(query)}")
        print(f"   - should_log_slotter: {should_log_slotter(query)}")
        print(f"   - should_ab_test_slotter: {should_ab_test_slotter(query)}")
        print()


def set_flag(flag_name: str, value: str):
    """Set a feature flag value."""
    # Reset flags to get fresh instance
    reset_feature_flags()
    flags = get_feature_flags()
    
    # Convert string value to appropriate type
    if value.lower() in ['true', 'on', '1']:
        value = True
    elif value.lower() in ['false', 'off', '0']:
        value = False
    elif value.isdigit():
        value = int(value)
    elif '.' in value and value.replace('.', '').isdigit():
        value = float(value)
    
    flags.set_flag(flag_name, value)
    print(f"✅ Set {flag_name} = {value}")


def enable_slotter():
    """Enable slotter feature."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_WIDE', True)
    print("✅ Slotter enabled")


def disable_slotter():
    """Disable slotter feature."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_WIDE', False)
    print("✅ Slotter disabled")


def enable_shadow_mode():
    """Enable shadow mode."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_SHADOW', True)
    print("✅ Shadow mode enabled")


def disable_shadow_mode():
    """Disable shadow mode."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_SHADOW', False)
    print("✅ Shadow mode disabled")


def enable_ab_test():
    """Enable A/B testing."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_AB_TEST', True)
    print("✅ A/B testing enabled")


def disable_ab_test():
    """Disable A/B testing."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_AB_TEST', False)
    print("✅ A/B testing disabled")


def enable_debug():
    """Enable debug mode."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_DEBUG', True)
    print("✅ Debug mode enabled")


def disable_debug():
    """Disable debug mode."""
    reset_feature_flags()
    flags = get_feature_flags()
    flags.set_flag('SLOTTER_DEBUG', False)
    print("✅ Debug mode disabled")


def main():
    parser = argparse.ArgumentParser(description="Manage feature flags")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Show flags
    subparsers.add_parser('show', help='Show all feature flags')
    
    # Test flags
    subparsers.add_parser('test', help='Test feature flag functions')
    
    # Set flag
    set_parser = subparsers.add_parser('set', help='Set a feature flag')
    set_parser.add_argument('flag', help='Flag name')
    set_parser.add_argument('value', help='Flag value')
    
    # Enable/disable commands
    subparsers.add_parser('enable-slotter', help='Enable slotter')
    subparsers.add_parser('disable-slotter', help='Disable slotter')
    subparsers.add_parser('enable-shadow', help='Enable shadow mode')
    subparsers.add_parser('disable-shadow', help='Disable shadow mode')
    subparsers.add_parser('enable-ab-test', help='Enable A/B testing')
    subparsers.add_parser('disable-ab-test', help='Disable A/B testing')
    subparsers.add_parser('enable-debug', help='Enable debug mode')
    subparsers.add_parser('disable-debug', help='Disable debug mode')
    
    args = parser.parse_args()
    
    if args.command == 'show':
        show_flags()
    elif args.command == 'test':
        test_flags()
    elif args.command == 'set':
        set_flag(args.flag, args.value)
    elif args.command == 'enable-slotter':
        enable_slotter()
    elif args.command == 'disable-slotter':
        disable_slotter()
    elif args.command == 'enable-shadow':
        enable_shadow_mode()
    elif args.command == 'disable-shadow':
        disable_shadow_mode()
    elif args.command == 'enable-ab-test':
        enable_ab_test()
    elif args.command == 'disable-ab-test':
        disable_ab_test()
    elif args.command == 'enable-debug':
        enable_debug()
    elif args.command == 'disable-debug':
        disable_debug()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
