# apps/farms/services/area_calculator.py

from django.contrib.gis.geos import Polygon, Point
from django.contrib.gis.measure import Area, Distance
from decimal import Decimal


class AreaCalculator:
    """
    Service for calculating farm areas and conversions
    """
    
    # Conversion constants
    SQ_METERS_TO_ACRES = 0.000247105
    SQ_METERS_TO_HECTARES = 0.0001
    ACRES_TO_HECTARES = 0.404686
    HECTARES_TO_ACRES = 2.47105
    
    @classmethod
    def calculate_polygon_area(cls, polygon):
        """
        Calculate area of a polygon in different units
        
        Args:
            polygon: Django GIS Polygon object (with geography=True)
            
        Returns:
            dict: Area in different units
        """
        # Get area in square meters (PostGIS with geography=True returns meters)
        area_sq_meters = polygon.area
        
        # Convert to different units
        area_acres = area_sq_meters * cls.SQ_METERS_TO_ACRES
        area_hectares = area_sq_meters * cls.SQ_METERS_TO_HECTARES
        
        return {
            'square_meters': round(area_sq_meters, 2),
            'acres': round(area_acres, 2),
            'hectares': round(area_hectares, 2)
        }
    
    @classmethod
    def calculate_from_coordinates(cls, coordinates):
        """
        Calculate area from list of coordinates
        
        Args:
            coordinates: List of (lng, lat) tuples or dicts with 'lat' and 'lng'
            
        Returns:
            dict: Area in different units
        """
        # Convert to (lng, lat) tuples if needed
        if isinstance(coordinates[0], dict):
            coords = [(c['lng'], c['lat']) for c in coordinates]
        else:
            coords = coordinates
        
        # Ensure polygon is closed
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        
        # Create polygon
        polygon = Polygon(coords, srid=4326)
        
        return cls.calculate_polygon_area(polygon)
    
    @classmethod
    def acres_to_hectares(cls, acres):
        """Convert acres to hectares"""
        return round(float(acres) * cls.ACRES_TO_HECTARES, 2)
    
    @classmethod
    def hectares_to_acres(cls, hectares):
        """Convert hectares to acres"""
        return round(float(hectares) * cls.HECTARES_TO_ACRES, 2)
    
    @classmethod
    def square_meters_to_acres(cls, sq_meters):
        """Convert square meters to acres"""
        return round(sq_meters * cls.SQ_METERS_TO_ACRES, 2)
    
    @classmethod
    def square_meters_to_hectares(cls, sq_meters):
        """Convert square meters to hectares"""
        return round(sq_meters * cls.SQ_METERS_TO_HECTARES, 2)
    
    @classmethod
    def calculate_perimeter(cls, polygon):
        """
        Calculate polygon perimeter in meters
        
        Args:
            polygon: Django GIS Polygon object
            
        Returns:
            float: Perimeter in meters
        """
        return round(polygon.length, 2)
    
    @classmethod
    def validate_farm_size(cls, area_acres, min_acres=0.1, max_acres=1000):
        """
        Validate if farm size is reasonable
        
        Args:
            area_acres: Farm size in acres
            min_acres: Minimum acceptable size (default 0.1 acres)
            max_acres: Maximum acceptable size (default 1000 acres)
            
        Returns:
            tuple: (is_valid, message)
        """
        if area_acres < min_acres:
            return False, f"Farm size too small (minimum {min_acres} acres)"
        
        if area_acres > max_acres:
            return False, f"Farm size too large (maximum {max_acres} acres)"
        
        return True, "Valid size"
    
    @classmethod
    def calculate_shape_complexity(cls, polygon):
        """
        Calculate shape complexity (ratio of perimeter to area)
        Higher values indicate more irregular shapes
        
        Args:
            polygon: Django GIS Polygon object
            
        Returns:
            float: Complexity score
        """
        area = polygon.area
        perimeter = polygon.length
        
        if area == 0:
            return 0
        
        # Complexity = Perimeter / sqrt(Area)
        # Normalized so circle = 1.0
        import math
        complexity = perimeter / (2 * math.sqrt(math.pi * area))
        
        return round(complexity, 2)
    
    @classmethod
    def detect_anomalies(cls, polygon):
        """
        Detect potential anomalies in farm boundary
        
        Args:
            polygon: Django GIS Polygon object
            
        Returns:
            dict: Anomaly detection results
        """
        anomalies = []
        
        # Check if polygon is valid
        if not polygon.valid:
            anomalies.append({
                'type': 'invalid_polygon',
                'severity': 'high',
                'message': 'Polygon geometry is invalid'
            })
        
        # Check for self-intersection
        if not polygon.simple:
            anomalies.append({
                'type': 'self_intersection',
                'severity': 'high',
                'message': 'Boundary has self-intersecting lines'
            })
        
        # Check number of vertices
        num_vertices = len(polygon.coords[0])
        if num_vertices < 4:
            anomalies.append({
                'type': 'too_few_points',
                'severity': 'high',
                'message': f'Only {num_vertices} points (minimum 4 required)'
            })
        elif num_vertices > 1000:
            anomalies.append({
                'type': 'too_many_points',
                'severity': 'low',
                'message': f'{num_vertices} points (may be overly complex)'
            })
        
        # Check shape complexity
        complexity = cls.calculate_shape_complexity(polygon)
        if complexity > 5.0:
            anomalies.append({
                'type': 'irregular_shape',
                'severity': 'medium',
                'message': f'Highly irregular shape (complexity: {complexity})'
            })
        
        # Check area
        area_acres = polygon.area * cls.SQ_METERS_TO_ACRES
        is_valid, message = cls.validate_farm_size(area_acres)
        if not is_valid:
            anomalies.append({
                'type': 'size_anomaly',
                'severity': 'high',
                'message': message
            })
        
        return {
            'has_anomalies': len(anomalies) > 0,
            'anomaly_count': len(anomalies),
            'anomalies': anomalies
        }
    
    @classmethod
    def calculate_centroid(cls, polygon):
        """
        Calculate polygon centroid (center point)
        
        Args:
            polygon: Django GIS Polygon object
            
        Returns:
            Point: Center point
        """
        return polygon.centroid
    
    @classmethod
    def calculate_bounding_box(cls, polygon):
        """
        Calculate bounding box of polygon
        
        Args:
            polygon: Django GIS Polygon object
            
        Returns:
            dict: Bounding box coordinates
        """
        extent = polygon.extent  # (min_lng, min_lat, max_lng, max_lat)
        
        return {
            'min_longitude': extent[0],
            'min_latitude': extent[1],
            'max_longitude': extent[2],
            'max_latitude': extent[3],
            'width_meters': polygon.envelope.length / 2,
            'height_meters': polygon.envelope.length / 2
        }