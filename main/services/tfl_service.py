import os
import requests
import json
import logging
from django.conf import settings
from django.core.cache import cache
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

class TflApiService:
    """
    Service for interacting with the Transport for London API.
    Handles authentication, requests, and data parsing.
    """
    
    BASE_URL = 'https://api.tfl.gov.uk'
    CACHE_TIMEOUT = 60 * 60 * 24  # 24 hours (in seconds)
    
    def __init__(self):
        self.app_id = settings.TFL_APP_ID
        self.api_key = settings.TFL_API_KEY
        
    def _get_auth_params(self):
        """Returns authentication parameters for TfL API"""
        return {
            'app_id': self.app_id,
            'app_key': self.api_key
        }
        
    def _make_request(self, endpoint, params=None, cache_key=None, cache_timeout=None):
        """
        Makes a request to the TfL API with optional caching
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            cache_key: Optional cache key
            cache_timeout: Optional cache timeout in seconds
            
        Returns:
            Response data as dict or None if error
        """
        # Try to get from cache first
        if cache_key:
            cached_data = cache.get(cache_key)
            if cached_data:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_data
                
        # Build full URL
        url = f"{self.BASE_URL}/{endpoint}"
        
        # Add auth params
        all_params = self._get_auth_params()
        if params:
            all_params.update(params)
            
        try:
            response = requests.get(url, params=all_params)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            data = response.json()
            
            # Cache successful response
            if cache_key:
                timeout = cache_timeout or self.CACHE_TIMEOUT
                cache.set(cache_key, data, timeout)
                
            return data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"TfL API request failed: {e}")
            return None
    
    def search_stations(self, query, modes=None):
        """
        Searches for stations by name or location
        
        Args:
            query: Station name or part of name
            modes: Optional list of transport modes (tube, bus, etc.)
            
        Returns:
            List of station dictionaries or empty list if none found
        """
        params = {'query': query}
        if modes:
            params['modes'] = ','.join(modes)
            
        cache_key = f"tfl_station_search_{query}_{modes}"
        
        endpoint = 'StopPoint/Search'
        response = self._make_request(endpoint, params, cache_key)
        
        if response and 'matches' in response:
            return response['matches']
        return []
    
    def get_station_by_id(self, station_id):
        """
        Gets detailed information about a station by ID
        
        Args:
            station_id: TfL station ID
            
        Returns:
            Station dict or None if not found
        """
        cache_key = f"tfl_station_{station_id}"
        endpoint = f'StopPoint/{station_id}'
        
        return self._make_request(endpoint, cache_key=cache_key)
    
    def plan_journey(self, from_lat, from_lon, to_lat, to_lon, time=None, date=None, time_is_arrival=False):
        """
        Plans a journey between two coordinates
        
        Args:
            from_lat: Starting latitude
            from_lon: Starting longitude
            to_lat: Destination latitude
            to_lon: Destination longitude
            time: Optional journey time (HH:MM)
            date: Optional journey date (YYYYMMDD)
            time_is_arrival: If True, time is arrival time, else departure
            
        Returns:
            Journey planning data or None if error
        """
        # Build the journey parameters
        params = {
            'from': f"{from_lat},{from_lon}",
            'to': f"{to_lat},{to_lon}",
        }
        
        if time:
            params['time'] = time
        if date:
            params['date'] = date
        if time_is_arrival:
            params['timeIs'] = 'Arriving'
            
        # Don't cache journey requests as they're time-sensitive
        endpoint = 'Journey/JourneyResults'
        
        return self._make_request(endpoint, params)
        
    def get_station_nearby(self, lat, lon, radius=1000, modes=None):
        """
        Finds stations near a given coordinate
        
        Args:
            lat: Latitude
            lon: Longitude
            radius: Search radius in meters (default 1000)
            modes: Optional list of transport modes
            
        Returns:
            List of nearby stations or empty list
        """
        params = {
            'lat': lat,
            'lon': lon,
            'radius': radius,
            'stopTypes': 'NaptanMetroStation,NaptanRailStation,NaptanPublicBusCoachTram'
        }
        
        if modes:
            params['modes'] = ','.join(modes)
            
        # Generate a cache key based on the parameters
        cache_key = f"tfl_nearby_{lat}_{lon}_{radius}_{modes}"
        
        endpoint = 'StopPoint'
        response = self._make_request(endpoint, params, cache_key)
        
        if response and 'stopPoints' in response:
            return response['stopPoints']
        return []
    
    def get_line_status(self, line_ids=None):
        """
        Gets the status of specified lines or all lines
        
        Args:
            line_ids: Optional list of line IDs (e.g., ['bakerloo', 'central'])
            
        Returns:
            List of line statuses
        """
        endpoint = 'Line/Status'
        if line_ids:
            endpoint = f'Line/{",".join(line_ids)}/Status'
            
        cache_key = f"tfl_line_status_{line_ids or 'all'}"
        # Shorter cache for line status as it changes frequently
        cache_timeout = 60 * 5  # 5 minutes
        
        return self._make_request(endpoint, cache_key=cache_key, cache_timeout=cache_timeout)


# Helper functions for common TfL API operations
def get_nearest_stations(lat, lon, radius=1000, limit=5):
    """
    Gets the nearest stations to a location
    
    Args:
        lat: Latitude
        lon: Longitude
        radius: Search radius in meters
        limit: Maximum number of stations to return
        
    Returns:
        List of nearest stations (dicts)
    """
    tfl_service = TflApiService()
    stations = tfl_service.get_station_nearby(lat, lon, radius)
    
    # Sort by distance and limit results
    sorted_stations = sorted(stations, key=lambda s: s.get('distance', float('inf')))
    return sorted_stations[:limit]

def calculate_journey_time(from_lat, from_lon, to_lat, to_lon):
    """
    Calculates journey time between two points
    
    Args:
        from_lat: Starting latitude
        from_lon: Starting longitude
        to_lat: Destination latitude
        to_lon: Destination longitude
        
    Returns:
        Journey time in minutes or None if error
    """
    tfl_service = TflApiService()
    journey_data = tfl_service.plan_journey(from_lat, from_lon, to_lat, to_lon)
    
    if journey_data and 'journeys' in journey_data and journey_data['journeys']:
        # Get the fastest journey option
        fastest_journey = min(journey_data['journeys'], key=lambda j: j.get('duration', float('inf')))
        return fastest_journey.get('duration')
    
    return None