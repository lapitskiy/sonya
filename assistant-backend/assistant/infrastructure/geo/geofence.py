"""Geofence service (infrastructure)."""

import math


class GeofenceService:
    """Service for geofence calculations."""
    
    def is_inside(
        self,
        lat: float,
        lon: float,
        center_lat: float,
        center_lon: float,
        radius_m: int,
    ) -> bool:
        """Check if point is inside geofence."""
        distance = self._haversine_distance(lat, lon, center_lat, center_lon)
        return distance <= radius_m
    
    @staticmethod
    def _haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in meters using Haversine formula."""
        R = 6_371_000  # Earth radius in meters
        
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lon2 - lon1)
        
        a = (
            math.sin(delta_phi / 2) ** 2 +
            math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c
