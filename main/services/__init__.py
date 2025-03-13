# Import main service classes for easier access
from .tfl_service import TflApiService, get_nearest_stations, calculate_journey_time
from .optimization_service import MeetupOptimizationService

# Version
__version__ = '0.1.0'