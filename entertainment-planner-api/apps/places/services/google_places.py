#!/usr/bin/env python3
"""Google Places API service for enriching place data"""

import os
import time
import logging
import requests
from typing import Optional, Dict, Any, List, Tuple
from collections import Counter
from apps.core.config import settings

logger = logging.getLogger(__name__)

API_KEY = settings.google_maps_api_key
BASE_URL = "https://places.googleapis.com/v1"


class GooglePlacesError(Exception):
    """Custom exception for Google Places API errors"""
    pass


class GooglePlaces:
    """Google Places API client with error handling and rate limiting"""
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 8, mock_mode: bool = False):
        self.key = api_key or API_KEY
        self.timeout = timeout
        self.stats = Counter()
        self.logger = logging.getLogger(__name__)
        self.mock_mode = mock_mode
        
        if not self.key and not mock_mode:
            raise ValueError("Google Maps API key is required")
    
    def _post(self, path: str, data: Dict[str, Any], headers: Dict[str, str] = None, retries: int = 3) -> Dict[str, Any]:
        """Make POST request to Google Places API with error handling"""
        if headers is None:
            headers = {}
        
        # Add API key to headers for new API
        headers["X-Goog-Api-Key"] = self.key
        headers["Content-Type"] = "application/json"
        
        # Add FieldMask for searchText
        if "searchText" in path:
            headers["X-Goog-FieldMask"] = (
                "places.id,places.displayName,places.formattedAddress,places.location,"
                "places.types,places.regularOpeningHours,places.priceLevel,places.businessStatus,"
                "places.utcOffsetMinutes,places.websiteUri,places.nationalPhoneNumber,"
                "places.rating,places.userRatingCount,"
                "places.photos.name,places.photos.widthPx,places.photos.heightPx,places.photos.authorAttributions"
            )
        
        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.post(f"{BASE_URL}/{path}", json=data, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                result = response.json()
                
                # New API doesn't have status field in the same way
                if "error" in result:
                    error = result["error"]
                    status = error.get("status", "UNKNOWN")
                    self.stats[status] += 1
                    
                    if status == "RESOURCE_EXHAUSTED":
                        self.logger.warning("Rate limit exceeded, sleeping 2 seconds")
                        time.sleep(2.0)
                        raise GooglePlacesError("Rate limit exceeded")
                    elif status == "PERMISSION_DENIED":
                        raise GooglePlacesError("API key invalid or request denied")
                    elif status == "INVALID_ARGUMENT":
                        raise GooglePlacesError("Invalid request parameters")
                    else:
                        raise GooglePlacesError(f"API error: {status} - {error.get('message', 'Unknown error')}")
                
                return result
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    time.sleep(min(2 * attempt, 6))
                    continue
                self.logger.error(f"Request failed: {e}")
                raise GooglePlacesError(f"Request failed: {e}")
    
    def _get(self, path: str, params: Dict[str, Any], headers: Dict[str, str] = None, retries: int = 3) -> Dict[str, Any]:
        """Make GET request to Google Places API with error handling"""
        if headers is None:
            headers = {}
        
        # Add API key to headers for new API
        headers["X-Goog-Api-Key"] = self.key
        
        attempt = 0
        while True:
            attempt += 1
            try:
                response = requests.get(f"{BASE_URL}/{path}", params=params, headers=headers, timeout=self.timeout)
                response.raise_for_status()
                data = response.json()
                
                # New API doesn't have status field in the same way
                if "error" in data:
                    error = data["error"]
                    status = error.get("status", "UNKNOWN")
                    self.stats[status] += 1
                    
                    if status == "RESOURCE_EXHAUSTED":
                        self.logger.warning("Rate limit exceeded, sleeping 2 seconds")
                        time.sleep(2.0)
                        raise GooglePlacesError("Rate limit exceeded")
                    elif status == "PERMISSION_DENIED":
                        raise GooglePlacesError("API key invalid or request denied")
                    elif status == "INVALID_ARGUMENT":
                        raise GooglePlacesError("Invalid request parameters")
                    else:
                        raise GooglePlacesError(f"API error: {status} - {error.get('message', 'Unknown error')}")
                
                return data
            except requests.exceptions.RequestException as e:
                if attempt < retries:
                    time.sleep(min(2 * attempt, 6))
                    continue
                self.logger.error(f"Request failed: {e}")
                raise GooglePlacesError(f"Request failed: {e}")
    
    def find_place(self, text: str, lat: Optional[float] = None, lng: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Find place by text query using new Places API"""
        if not text or not text.strip():
            return None
        
        # Mock mode for testing
        if self.mock_mode:
            self.logger.info(f"MOCK: Finding place for '{text}'")
            return {
                "id": f"mock_place_{hash(text) % 10000}",
                "displayName": {"text": text.strip()},
                "formattedAddress": f"{text.strip()}, Bangkok, Thailand",
                "location": {
                    "latitude": lat or 13.7563,
                    "longitude": lng or 100.5018
                }
            }
        
        # Use Text Search with POST request for new API
        data = {
            "textQuery": text.strip(),
            "languageCode": "en",
            "regionCode": "TH",
        }
        
        # Add location bias if coordinates provided
        if lat is not None and lng is not None:
            data["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": 4000.0
                }
            }
        
        try:
            result = self._post("places:searchText", data)
            if not result:
                return None
                
            places = result.get("places", [])
            if not places:
                return None
                
            # Return first place
            return places[0]
            
        except GooglePlacesError:
            raise
        except Exception as e:
            self.logger.error(f"Find place failed: {e}")
            return None
    
    def place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a place using new Places API"""
        if not place_id or not place_id.strip():
            return None
        
        # Mock mode for testing
        if self.mock_mode:
            self.logger.info(f"MOCK: Getting details for place {place_id}")
            return {
                "id": place_id,
                "displayName": {"text": f"Mock Place {place_id}"},
                "formattedAddress": "Mock Address, Bangkok, Thailand",
                "location": {
                    "latitude": 13.7563,
                    "longitude": 100.5018
                },
                "priceLevel": 2,
                "businessStatus": "OPERATIONAL",
                "utcOffsetMinutes": 420,  # +7 hours
                "rating": 4.2,
                "userRatingTotal": 150,
                "regularOpeningHours": {
                    "weekdayDescriptions": [
                        "Monday: 9:00 AM – 6:00 PM",
                        "Tuesday: 9:00 AM – 6:00 PM",
                        "Wednesday: 9:00 AM – 6:00 PM",
                        "Thursday: 9:00 AM – 6:00 PM",
                        "Friday: 9:00 AM – 6:00 PM",
                        "Saturday: 10:00 AM – 4:00 PM",
                        "Sunday: Closed"
                    ]
                }
            }
        
        # New API uses GET with FieldMask header
        headers = {
            "X-Goog-Api-Key": self.key,
            "X-Goog-FieldMask": (
                "id,displayName,formattedAddress,location,regularOpeningHours,priceLevel,types,"
                "websiteUri,nationalPhoneNumber,businessStatus,utcOffsetMinutes,photos.widthPx,photos.heightPx,"
                "photos.authorAttributions,photos.name,rating,userRatingCount"
            )
        }
        
        params = {
            "languageCode": "en"
        }
        
        try:
            response = requests.get(f"{BASE_URL}/places/{place_id.strip()}", params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                error = data["error"]
                status = error.get("status", "UNKNOWN")
                self.stats[status] += 1
                
                if status == "RESOURCE_EXHAUSTED":
                    self.logger.warning("Rate limit exceeded, sleeping 2 seconds")
                    time.sleep(2.0)
                    raise GooglePlacesError("Rate limit exceeded")
                elif status == "PERMISSION_DENIED":
                    raise GooglePlacesError("API key invalid or request denied")
                elif status == "INVALID_ARGUMENT":
                    raise GooglePlacesError("Invalid request parameters")
                else:
                    raise GooglePlacesError(f"API error: {status} - {error.get('message', 'Unknown error')}")
            
            return data
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request failed: {e}")
            raise GooglePlacesError(f"Request failed: {e}")
        except Exception as e:
            self.logger.error(f"Place details failed: {e}")
            return None
    
    def get_district_viewport(self, district_name: str) -> Optional[Dict[str, float]]:
        """Get viewport bounds for a district using Google Geocoding API"""
        if not district_name or not district_name.strip():
            return None
        
        # Mock mode for testing
        if self.mock_mode:
            self.logger.info(f"MOCK: Getting viewport for district {district_name}")
            # Mock viewport for Chinatown - расширенный для тестирования
            return {
                "lat_min": 13.600,
                "lat_max": 13.800,
                "lng_min": 100.300,
                "lng_max": 100.700
            }
        
        # Use Google Geocoding API
        geocoding_url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": f"{district_name} Bangkok Thailand",
            "key": self.key
        }
        
        try:
            response = requests.get(geocoding_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") != "OK" or not data.get("results"):
                self.logger.warning(f"No results for district: {district_name}")
                return None
            
            # Get viewport from first result
            result = data["results"][0]
            geometry = result.get("geometry", {})
            viewport = geometry.get("viewport", {})
            
            if not viewport:
                self.logger.warning(f"No viewport for district: {district_name}")
                return None
            
            # Extract bounds
            northeast = viewport.get("northeast", {})
            southwest = viewport.get("southwest", {})
            
            if not northeast or not southwest:
                self.logger.warning(f"Incomplete viewport for district: {district_name}")
                return None
            
            return {
                "lat_min": southwest.get("lat"),
                "lat_max": northeast.get("lat"),
                "lng_min": southwest.get("lng"),
                "lng_max": northeast.get("lng")
            }
            
        except Exception as e:
            self.logger.error(f"Geocoding failed for district {district_name}: {e}")
            return None
    
    def get_place_photos(self, place_id: str) -> Optional[str]:
        """Get best photo for a place using Google Places API"""
        try:
            if not place_id or not place_id.strip():
                return None
            
            # Mock mode for testing
            if self.mock_mode:
                self.logger.info(f"MOCK: Getting photos for place {place_id}")
                return "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400"
            
            # Get place details with photos
            headers = {
                "X-Goog-Api-Key": self.key,
                "X-Goog-FieldMask": "photos.name,photos.widthPx,photos.heightPx,photos.authorAttributions"
            }
            params = { "languageCode": "en" }
            response = requests.get(f"{BASE_URL}/places/{place_id.strip()}", params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                error = data["error"]
                status = error.get("status", "UNKNOWN")
                self.stats[status] += 1
                
                if status == "RESOURCE_EXHAUSTED":
                    self.logger.warning("Rate limit exceeded, sleeping 2 seconds")
                    time.sleep(2.0)
                    raise GooglePlacesError("Rate limit exceeded")
                elif status == "PERMISSION_DENIED":
                    raise GooglePlacesError("API key invalid or request denied")
                elif status == "INVALID_ARGUMENT":
                    raise GooglePlacesError("Invalid request parameters")
                else:
                    raise GooglePlacesError(f"API error: {status} - {error.get('message', 'Unknown error')}")
            
            if 'photos' in data:
                photos = data['photos']
                if photos:
                    # Select best photo using our algorithm
                    best_photo = self._select_best_photo(photos)
                    if best_photo:
                        photo_name = best_photo['name']
                        photo_url = self._get_photo_url(photo_name)
                        if photo_url:
                            self.logger.info(f"Selected photo with score {best_photo.get('_score', 0)} for place {place_id}")
                            return photo_url
            
            return None
            
        except Exception as e:
            self.logger.error(f"Get place photos failed for {place_id}: {e}")
            return None
    
    def get_place_photos_filtered(self, place_id: str, max_photos: int = 3, min_score: int = 30) -> List[str]:
        """Get multiple filtered photos for a place, prioritizing official business photos"""
        try:
            if not place_id or not place_id.strip():
                return []
            
            # Mock mode for testing
            if self.mock_mode:
                self.logger.info(f"MOCK: Getting filtered photos for place {place_id}")
                return ["https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=400"]
            
            # Get place details with photos
            headers = {
                "X-Goog-Api-Key": self.key,
                "X-Goog-FieldMask": "photos.name,photos.widthPx,photos.heightPx,photos.authorAttributions"
            }
            params = { "languageCode": "en" }
            response = requests.get(f"{BASE_URL}/places/{place_id.strip()}", params=params, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                error = data["error"]
                status = error.get("status", "UNKNOWN")
                self.stats[status] += 1
                
                if status == "RESOURCE_EXHAUSTED":
                    self.logger.warning("Rate limit exceeded, sleeping 2 seconds")
                    time.sleep(2.0)
                    raise GooglePlacesError("Rate limit exceeded")
                elif status == "PERMISSION_DENIED":
                    raise GooglePlacesError("API key invalid or request denied")
                elif status == "INVALID_ARGUMENT":
                    raise GooglePlacesError("Invalid request parameters")
                else:
                    raise GooglePlacesError(f"API error: {status} - {error.get('message', 'Unknown error')}")
            
            if 'photos' not in data or not data['photos']:
                return []
            
            photos = data['photos']
            
            # Score and filter photos
            scored_photos = []
            for photo in photos:
                score = 0
                photo_info = photo.get('authorAttributions', [{}])[0]
                display_name = photo_info.get('displayName', '').lower()
                
                # Check dimensions
                width = photo.get('widthPx', 0)
                height = photo.get('heightPx', 0)
                if width >= 1000 and height >= 1000:
                    score += 10
                elif width >= 800 and height >= 800:
                    score += 5
                
                # Check aspect ratio
                aspect_ratio = width / height if height > 0 else 1
                if 1.2 <= aspect_ratio <= 2.0:
                    score += 5
                
                # Check if official business photo
                official_keywords = ['google', 'business', 'owner', 'official', 'verified', 'place', 'establishment']
                is_official = any(keyword in display_name for keyword in official_keywords)
                
                if is_official:
                    score += 50
                else:
                    # Check for user photos and penalize
                    user_keywords = ['user', 'customer', 'visitor', 'guest', 'review', 'tripadvisor', 'yelp']
                    if any(keyword in display_name for keyword in user_keywords):
                        score -= 20
                
                # Check content keywords
                interior_keywords = ['interior', 'inside', 'dining', 'seating', 'restaurant', 'cafe', 'bar']
                food_keywords = ['food', 'dish', 'meal', 'drink', 'coffee', 'tea', 'cocktail']
                
                if any(keyword in display_name for keyword in interior_keywords):
                    score += 15
                if any(keyword in display_name for keyword in food_keywords):
                    score += 20
                
                # Avoid exterior photos
                if any(word in display_name for word in ['exterior', 'outside', 'building', 'facade']):
                    score -= 10
                
                photo['_score'] = score
                photo['_is_official'] = is_official
                scored_photos.append((score, photo))
            
            # Sort by score and filter by minimum score
            scored_photos.sort(key=lambda x: x[0], reverse=True)
            filtered_photos = [(score, photo) for score, photo in scored_photos if score >= min_score]
            
            # Get URLs for top photos
            photo_urls = []
            for score, photo in filtered_photos[:max_photos]:
                photo_name = photo['name']
                photo_url = self._get_photo_url(photo_name)
                if photo_url:
                    photo_urls.append(photo_url)
                    self.logger.debug(f"Added photo with score {score} (Official: {photo.get('_is_official', False)})")
            
            self.logger.info(f"Selected {len(photo_urls)} photos for place {place_id} (from {len(photos)} total)")
            return photo_urls
            
        except Exception as e:
            self.logger.error(f"Get filtered photos failed for {place_id}: {e}")
            return []
    
    def _select_best_photo(self, photos: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Select best photo with interior or food focus, prioritizing official business photos"""
        try:
            if not photos:
                return None
            
            # Keywords for interior and food photos
            interior_keywords = [
                'interior', 'inside', 'dining', 'seating', 'table', 'chair', 
                'restaurant', 'cafe', 'bar', 'kitchen', 'counter', 'decor',
                'atmosphere', 'ambiance', 'space', 'room', 'hall'
            ]
            
            food_keywords = [
                'food', 'dish', 'meal', 'plate', 'drink', 'coffee', 'tea',
                'cocktail', 'beer', 'wine', 'dessert', 'cake', 'pasta',
                'pizza', 'sushi', 'thai', 'cuisine', 'menu', 'serving'
            ]
            
            # Keywords indicating official business photos
            official_keywords = [
                'google', 'business', 'owner', 'official', 'verified', 
                'place', 'establishment', 'venue', 'restaurant', 'cafe', 'bar'
            ]
            
            # Keywords indicating user photos (to avoid)
            user_photo_keywords = [
                'user', 'customer', 'visitor', 'guest', 'review', 'tripadvisor',
                'yelp', 'foursquare', 'instagram', 'facebook', 'social'
            ]
            
            # Score photos by priority
            scored_photos = []
            
            for photo in photos:
                score = 0
                photo_info = photo.get('authorAttributions', [{}])[0]
                display_name = photo_info.get('displayName', '').lower()
                
                # Check dimensions (prefer larger photos)
                width = photo.get('widthPx', 0)
                height = photo.get('heightPx', 0)
                if width >= 1000 and height >= 1000:
                    score += 10
                elif width >= 800 and height >= 800:
                    score += 5
                
                # Check aspect ratio (prefer landscape for interiors)
                aspect_ratio = width / height if height > 0 else 1
                if 1.2 <= aspect_ratio <= 2.0:  # Good landscape ratio
                    score += 5
                elif aspect_ratio > 2.0:  # Too wide
                    score -= 2
                
                # PRIORITY: Check if it's an official business photo
                is_official = any(keyword in display_name for keyword in official_keywords)
                is_user_photo = any(keyword in display_name for keyword in user_photo_keywords)
                
                if is_official:
                    score += 50  # High priority for official photos
                    self.logger.debug(f"Official photo detected: {display_name}")
                elif is_user_photo:
                    score -= 20  # Penalty for user photos
                    self.logger.debug(f"User photo detected: {display_name}")
                
                # Check keywords in author name for content type
                for keyword in interior_keywords:
                    if keyword in display_name:
                        score += 15
                        break
                
                for keyword in food_keywords:
                    if keyword in display_name:
                        score += 20  # Food has priority
                        break
                
                # Avoid exterior building photos
                if any(word in display_name for word in ['exterior', 'outside', 'building', 'facade', 'street']):
                    score -= 10
                
                # Avoid low-quality indicators
                if any(word in display_name for word in ['blurry', 'dark', 'low', 'bad', 'poor']):
                    score -= 15
                
                # Store score in photo for logging
                photo['_score'] = score
                photo['_is_official'] = is_official
                photo['_is_user_photo'] = is_user_photo
                scored_photos.append((score, photo))
            
            # Sort by score descending
            scored_photos.sort(key=lambda x: x[0], reverse=True)
            
            # Log top 3 photos for debugging
            if scored_photos:
                self.logger.debug(f"Top 3 photos for debugging:")
                for i, (score, photo) in enumerate(scored_photos[:3]):
                    photo_info = photo.get('authorAttributions', [{}])[0]
                    display_name = photo_info.get('displayName', 'Unknown')
                    self.logger.debug(f"  {i+1}. Score: {score}, Official: {photo.get('_is_official', False)}, Author: {display_name}")
            
            # Return best photo
            if scored_photos:
                best_photo = scored_photos[0][1]
                self.logger.info(f"Selected photo with score {best_photo.get('_score', 0)} (Official: {best_photo.get('_is_official', False)})")
                return best_photo
            
            return photos[0] if photos else None
            
        except Exception as e:
            self.logger.error(f"Photo selection failed: {e}")
            return photos[0] if photos else None
    
    def _get_photo_url(self, photo_name: str) -> Optional[str]:
        """Get photo URL from photo name"""
        try:
            # Use new Places API for getting photo
            url = f"{BASE_URL}/{photo_name}/media"
            params = { 'maxWidthPx': 1600 }
            headers = { "X-Goog-Api-Key": self.key }
            response = requests.get(url, params=params, headers=headers, allow_redirects=False, timeout=self.timeout)
            
            if response.status_code == 302:  # Redirect
                return response.headers.get('Location', '')
            elif response.status_code == 200:
                # If image returned directly
                q = '&'.join([f"{k}={v}" for k, v in params.items()])
                return f"{url}?{q}"
            
            return None
            
        except Exception as e:
            self.logger.error(f"Get photo URL failed: {e}")
            return None

    def get_stats(self) -> Dict[str, int]:
        """Get API usage statistics"""
        return dict(self.stats)

    # -------- Legacy fallback (Places v2 JSON) -------
    def legacy_find_place(self, text: str) -> Optional[str]:
        try:
            url = "https://maps.googleapis.com/maps/api/place/findplacefromtext/json"
            params = {
                'input': text,
                'inputtype': 'textquery',
                'fields': 'place_id',
                'language': 'en',
                'region': 'th',
                'key': self.key,
            }
            r = requests.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            j = r.json()
            if j.get('status') == 'OK' and j.get('candidates'):
                return j['candidates'][0]['place_id']
        except Exception as e:
            self.logger.warning(f"legacy_find_place failed: {e}")
        return None

    def legacy_place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        try:
            url = "https://maps.googleapis.com/maps/api/place/details/json"
            params = {
                'place_id': place_id,
                'fields': 'place_id,formatted_address,geometry,price_level,types,website,international_phone_number,opening_hours,rating,user_ratings_total,photos',
                'language': 'en',
                'region': 'th',
                'key': self.key,
            }
            r = requests.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            j = r.json()
            if j.get('status') == 'OK' and j.get('result'):
                return j['result']
        except Exception as e:
            self.logger.warning(f"legacy_place_details failed: {e}")
        return None

    def legacy_photo_url(self, photo_reference: str) -> Optional[str]:
        try:
            url = "https://maps.googleapis.com/maps/api/place/photo"
            params = {
                'maxwidth': 1600,
                'photoreference': photo_reference,
                'key': self.key,
            }
            r = requests.get(url, params=params, allow_redirects=False, timeout=self.timeout)
            if r.status_code == 302:
                return r.headers.get('Location', '')
        except Exception as e:
            self.logger.warning(f"legacy_photo_url failed: {e}")
        return None


def opening_hours_to_json(opening_hours: Optional[Dict[str, Any]]) -> Optional[Dict[str, List[str]]]:
    """Convert Google Places opening hours to our JSON format"""
    if not opening_hours:
        return None
    
    # Handle both old format (periods in root) and new format (periods in regularOpeningHours)
    periods = opening_hours.get("periods")
    if not periods and opening_hours.get("regularOpeningHours"):
        periods = opening_hours["regularOpeningHours"].get("periods")
    
    if not periods:
        return None
    
    # Google: 0=Sun .. 6=Sat
    days_map = {0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat"}
    out = {d: [] for d in ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]}
    
    for period in periods:
        open_time = period.get("open")
        close_time = period.get("close")
        
        if not open_time or "hour" not in open_time:
            continue
            
        def format_time(time_obj):
            return f"{time_obj['hour']:02d}:{time_obj.get('minute', 0):02d}"
        
        if close_time and "hour" in close_time:
            # Normal hours (same day)
            d_open, d_close = days_map[open_time["day"]], days_map[close_time["day"]]
            start, end = format_time(open_time), format_time(close_time)
            
            if d_open == d_close:
                out[d_open].append(f"{start}-{end}")
            else:
                # Overnight hours (split across days)
                out[d_open].append(f"{start}-24:00")
                out[d_close].append(f"00:00-{end}")
        else:
            # 24h open
            out[days_map[open_time["day"]]].append("00:00-24:00")
    
    # Remove empty days
    return {k: v for k, v in out.items() if v} or None


def gmaps_url_from_id(place_id: str) -> str:
    """Generate Google Maps URL from place ID"""
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


def normalize_query(name: str, address: str = None) -> str:
    """Normalize search query - use only name + Bangkok for better Google Maps results"""
    if not name or not name.strip():
        return ""
    
    # Clean name and add Bangkok for disambiguation
    clean_name = name.strip()
    return f"{clean_name} Bangkok"
