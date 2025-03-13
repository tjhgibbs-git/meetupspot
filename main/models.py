from django.db import models
from django.contrib.auth.models import User

class Station(models.Model):
    """
    Stores information about transport stations/stops
    """
    name = models.CharField(max_length=255)
    station_code = models.CharField(max_length=20, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    transport_modes = models.CharField(max_length=255)  # e.g., "tube,bus,rail"
    amenities = models.TextField(null=True, blank=True)  # JSON field
    
    def __str__(self):
        return self.name

class StationConnection(models.Model):
    """
    Caches travel information between stations
    """
    origin_station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='origin_connections')
    destination_station = models.ForeignKey(Station, on_delete=models.CASCADE, related_name='destination_connections')
    travel_time_minutes = models.IntegerField()
    route_data = models.TextField()  # JSON field for route details
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('origin_station', 'destination_station')
        
    def __str__(self):
        return f"{self.origin_station.name} to {self.destination_station.name}"

class MeetingVenue(models.Model):
    """
    Potential meeting locations (restaurants, cafes, etc.)
    """
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    venue_type = models.CharField(max_length=100)  # e.g., restaurant, cafe, pub
    amenities = models.TextField(null=True, blank=True)  # JSON field
    nearest_station = models.ForeignKey(Station, on_delete=models.SET_NULL, null=True, related_name='nearby_venues')
    
    def __str__(self):
        return self.name

class Participant(models.Model):
    """
    Stores information about participants
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='participant_profiles')
    nickname = models.CharField(max_length=100, null=True, blank=True)
    
    def __str__(self):
        return self.user.username if not self.nickname else self.nickname

class Meetup(models.Model):
    """
    Stores information about meetups
    """
    title = models.CharField(max_length=255)
    date = models.DateField()
    time = models.TimeField()
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_meetups')
    participants = models.ManyToManyField(Participant, through='MeetupParticipant')
    optimal_meeting_venue = models.ForeignKey(
        MeetingVenue, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='meetups'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.title

class MeetupParticipant(models.Model):
    """
    Junction table for meetup participants with their nearest stations
    """
    meetup = models.ForeignKey(Meetup, on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    
    # Instead of storing exact locations, we store only nearest stations
    starting_station = models.ForeignKey(
        Station, 
        on_delete=models.CASCADE, 
        related_name='meetup_starts'
    )
    ending_station = models.ForeignKey(
        Station, 
        on_delete=models.CASCADE, 
        related_name='meetup_ends'
    )
    
    # Approximate distances (in minutes) to nearest stations
    walking_time_to_start = models.IntegerField(default=5)
    walking_time_from_end = models.IntegerField(default=5)
    
    class Meta:
        unique_together = ('meetup', 'participant')

class TemporaryLocation(models.Model):
    """
    Temporarily stores location data during meetup planning
    Auto-deleted after calculation is complete
    """
    session_id = models.CharField(max_length=100)
    participant_identifier = models.CharField(max_length=100)
    location_type = models.CharField(max_length=10)  # 'START' or 'END'
    latitude = models.FloatField()
    longitude = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        index_together = ['session_id', 'participant_identifier']