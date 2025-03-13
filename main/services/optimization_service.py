import logging
from itertools import product
from django.db.models import Avg, StdDev
import numpy as np
from .tfl_service import calculate_journey_time, get_nearest_stations

logger = logging.getLogger(__name__)

class MeetupOptimizationService:
    """
    Service for optimizing meetup locations based on travel times
    """
    
    def __init__(self, fairness_weight=0.5):
        """
        Initialize with fairness weighting factor
        
        Args:
            fairness_weight: Weight for the fairness component (0-1)
                             Higher values prioritize fairness over total time
        """
        self.fairness_weight = fairness_weight
    
    def _calculate_journey_score(self, journey_times):
        """
        Calculate the score for a set of journey times
        Lower is better
        
        Args:
            journey_times: List of journey times in minutes
            
        Returns:
            Score (lower is better)
        """
        if not journey_times:
            return float('inf')
            
        total_time = sum(journey_times)
        
        # Calculate standard deviation for fairness
        if len(journey_times) > 1:
            std_dev = np.std(journey_times)
        else:
            std_dev = 0
            
        # Weighted score (total time + fairness penalty)
        score = total_time + (self.fairness_weight * std_dev * len(journey_times))
        
        return score
        
    def find_optimal_meeting_point(self, participants_data, potential_venues, max_candidates=10):
        """
        Find the optimal meeting venue based on journey times
        
        Args:
            participants_data: List of dicts with start/end stations
                [{'start_lat': x, 'start_lon': y, 'end_lat': z, 'end_lon': w}, ...]
            potential_venues: List of venue dicts with coordinates
                [{'id': 1, 'name': 'Venue', 'lat': x, 'lon': y}, ...]
            max_candidates: Maximum number of venues to evaluate fully
            
        Returns:
            Best venue dict with score added
        """
        # If we have too many potential venues, pre-filter 
        # to avoid excessive API calls
        if len(potential_venues) > max_candidates:
            # Simplified pre-filtering based on geographical center
            avg_lat = sum(p['start_lat'] for p in participants_data) / len(participants_data)
            avg_lon = sum(p['start_lon'] for p in participants_data) / len(participants_data)
            
            # Sort venues by distance to center
            def calc_distance(venue):
                return ((venue['lat'] - avg_lat) ** 2 + (venue['lon'] - avg_lon) ** 2) ** 0.5
                
            potential_venues = sorted(potential_venues, key=calc_distance)[:max_candidates]
            
        # Calculate scores for each venue
        venue_scores = []
        
        for venue in potential_venues:
            try:
                # Calculate journey times for each participant
                all_journey_times = []
                
                for participant in participants_data:
                    # Calculate start → venue time
                    start_to_venue = calculate_journey_time(
                        participant['start_lat'], 
                        participant['start_lon'],
                        venue['lat'], 
                        venue['lon']
                    ) or 0
                    
                    # Calculate venue → end time
                    venue_to_end = calculate_journey_time(
                        venue['lat'],
                        venue['lon'],
                        participant['end_lat'],
                        participant['end_lon']
                    ) or 0
                    
                    # Total journey time
                    total_time = start_to_venue + venue_to_end
                    all_journey_times.append(total_time)
                
                # Calculate score for this venue
                score = self._calculate_journey_score(all_journey_times)
                
                venue_scores.append({
                    'venue': venue,
                    'score': score,
                    'journey_times': all_journey_times
                })
                
            except Exception as e:
                logger.error(f"Error calculating score for venue {venue['name']}: {e}")
        
        # Sort by score (lower is better)
        venue_scores.sort(key=lambda x: x['score'])
        
        if venue_scores:
            best_venue = venue_scores[0]['venue'].copy()
            best_venue['score'] = venue_scores[0]['score']
            best_venue['journey_times'] = venue_scores[0]['journey_times']
            return best_venue
        
        return None

    def get_potential_meeting_venues(self, participants_data, venue_type=None, limit=20):
        """
        Find potential meeting venues based on participant locations
        
        Args:
            participants_data: List of dicts with start/end stations
            venue_type: Optional type of venue (restaurant, cafe, etc.)
            limit: Maximum number of venues to return
            
        Returns:
            List of potential meeting venues
        """
        # Calculate the geographical center of all start/end points
        all_points = []
        for p in participants_data:
            all_points.append((p['start_lat'], p['start_lon']))
            all_points.append((p['end_lat'], p['end_lon']))
            
        center_lat = sum(p[0] for p in all_points) / len(all_points)
        center_lon = sum(p[1] for p in all_points) / len(all_points)
        
        # Find stations near this center
        central_stations = get_nearest_stations(center_lat, center_lon, radius=1500, limit=5)
        
        # For now, just return station coordinates as potential venues
        # In a real implementation, you would look up restaurants, cafes, etc. near these stations
        potential_venues = []
        
        for station in central_stations:
            potential_venues.append({
                'id': station.get('id', ''),
                'name': station.get('commonName', 'Unknown Station'),
                'lat': station.get('lat', 0),
                'lon': station.get('lon', 0),
                'type': 'station',
                'description': f"Near {station.get('commonName', 'station')}"
            })
            
        return potential_venues[:limit]