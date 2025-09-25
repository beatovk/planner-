#!/usr/bin/env python3
"""Bangkok districts mapping with coordinates"""

# Маппинг районов Бангкока с координатами
BANGKOK_DISTRICTS = {
    # Основные районы
    'Ari': {
        'lat_min': 13.780, 'lat_max': 13.800,
        'lng_min': 100.520, 'lng_max': 100.550,
        'name': 'Phaya Thai District'
    },
    'Asok': {
        'lat_min': 13.720, 'lat_max': 13.750,
        'lng_min': 100.550, 'lng_max': 100.580,
        'name': 'Khlong Toei Nuea (Khwaeng, Watthana District)'
    },
    'Bang Na': {
        'lat_min': 13.600, 'lat_max': 13.700,
        'lng_min': 100.600, 'lng_max': 100.700,
        'name': 'Bang Na (Khet)'
    },
    'Chatuchak': {
        'lat_min': 13.800, 'lat_max': 13.850,
        'lng_min': 100.520, 'lng_max': 100.580,
        'name': 'Chatuchak (Khet)'
    },
    'Chinatown': {
        'lat_min': 13.730, 'lat_max': 13.750,
        'lng_min': 100.500, 'lng_max': 100.520,
        'name': 'Samphanthawong (Khet)'
    },
    'Dusit': {
        'lat_min': 13.770, 'lat_max': 13.800,
        'lng_min': 100.500, 'lng_max': 100.530,
        'name': 'Dusit (Khet)'
    },
    'Ekkamai': {
        'lat_min': 13.720, 'lat_max': 13.750,
        'lng_min': 100.580, 'lng_max': 100.620,
        'name': 'Phra Khanong Nuea (Khwaeng, Watthana District)'
    },
    'Khaosan Road': {
        'lat_min': 13.750, 'lat_max': 13.770,
        'lng_min': 100.490, 'lng_max': 100.510,
        'name': 'Talat Yot (Khwaeng, Phra Nakhon District)'
    },
    'Lat Phrao': {
        'lat_min': 13.800, 'lat_max': 13.850,
        'lng_min': 100.580, 'lng_max': 100.650,
        'name': 'Lat Phrao (Khet)'
    },
    'Old Town': {
        'lat_min': 13.750, 'lat_max': 13.770,
        'lng_min': 100.490, 'lng_max': 100.510,
        'name': 'Phra Nakhon (Khet)'
    },
    'On Nut': {
        'lat_min': 13.700, 'lat_max': 13.730,
        'lng_min': 100.580, 'lng_max': 100.620,
        'name': 'Phra Khanong Nuea (Khwaeng, Watthana District)'
    },
    'Phaya Thai': {
        'lat_min': 13.780, 'lat_max': 13.800,
        'lng_min': 100.520, 'lng_max': 100.550,
        'name': 'Phaya Thai (Khet)'
    },
    'Phra Khanong': {
        'lat_min': 13.700, 'lat_max': 13.730,
        'lng_min': 100.580, 'lng_max': 100.620,
        'name': 'Phra Khanong (Khet)'
    },
    'Phrom Phong': {
        'lat_min': 13.720, 'lat_max': 13.750,
        'lng_min': 100.550, 'lng_max': 100.580,
        'name': 'Khlong Toei (Khwaeng, Khlong Toei District)'
    },
    'Ratchada': {
        'lat_min': 13.750, 'lat_max': 13.780,
        'lng_min': 100.550, 'lng_max': 100.600,
        'name': 'Din Daeng (Khet) / Huai Khwang (Khet)'
    },
    'Ratchaprasong': {
        'lat_min': 13.740, 'lat_max': 13.760,
        'lng_min': 100.520, 'lng_max': 100.550,
        'name': 'Pathum Wan (Khet)'
    },
    'Riverside': {
        'lat_min': 13.720, 'lat_max': 13.750,
        'lng_min': 100.490, 'lng_max': 100.520,
        'name': 'Bang Rak (Khet) / Khlong San (Khet)'
    },
    'Sathorn': {
        'lat_min': 13.720, 'lat_max': 13.750,
        'lng_min': 100.520, 'lng_max': 100.550,
        'name': 'Sathon (Khet)'
    },
    'Siam': {
        'lat_min': 13.740, 'lat_max': 13.760,
        'lng_min': 100.520, 'lng_max': 100.550,
        'name': 'Pathum Wan (Khet)'
    },
    'Silom': {
        'lat_min': 13.720, 'lat_max': 13.750,
        'lng_min': 100.520, 'lng_max': 100.550,
        'name': 'Bang Rak (Khet)'
    },
    'Talad Noi': {
        'lat_min': 13.730, 'lat_max': 13.750,
        'lng_min': 100.500, 'lng_max': 100.520,
        'name': 'Samphanthawong (Khwaeng, Samphanthawong District)'
    },
    'Thonglor': {
        'lat_min': 13.720, 'lat_max': 13.750,
        'lng_min': 100.580, 'lng_max': 100.620,
        'name': 'Watthana (Khwaeng, Watthana District)'
    },
    'Victory Monument': {
        'lat_min': 13.760, 'lat_max': 13.780,
        'lng_min': 100.530, 'lng_max': 100.560,
        'name': 'Ratchathewi (Khwaeng, Ratchathewi District)'
    }
}

def get_district_bounds(district_name: str) -> dict:
    """Get district bounds by name"""
    return BANGKOK_DISTRICTS.get(district_name)

def get_all_districts() -> dict:
    """Get all districts"""
    return BANGKOK_DISTRICTS
