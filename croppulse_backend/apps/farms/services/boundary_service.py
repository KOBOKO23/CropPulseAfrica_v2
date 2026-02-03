# apps/farms/services/boundary_service.py

from django.contrib.gis.geos import Polygon, Point, LineString
from django.contrib.gis.measure import D
from django.db import transaction
from apps.farms.models import Farm, FarmBoundaryPoint
from .area_calculator import AreaCalculator


class BoundaryService:
    """
    Service for farm boundary operations and validation
    """
    
    @classmethod
    def validate_boundary_points(cls, points):
        """
        Validate boundary points before creating farm
        
        Args:
            points: List of dicts with 'lat' and 'lng'
            
        Returns:
            tuple: (is_valid, errors, warnings)
        """
        errors = []
        warnings = []
        
        # Check minimum points
        if len(points) < 3:
            errors.append("At least 3 points required to form a boundary")
            return False, errors, warnings
        
        # Check maximum points (performance)
        if len(points) > 1000:
            warnings.append(f"Boundary has {len(points)} points (very complex)")
        
        # Validate each point
        for i, point in enumerate(points):
            # Check required fields
            if 'lat' not in point or 'lng' not in point:
                errors.append(f"Point {i}: Missing 'lat' or 'lng' field")
                continue
            
            try:
                lat = float(point['lat'])
                lng = float(point['lng'])
            except (ValueError, TypeError):
                errors.append(f"Point {i}: Invalid coordinate values")
                continue
            
            # Validate coordinate ranges
            if not (-90 <= lat <= 90):
                errors.append(f"Point {i}: Latitude must be between -90 and 90")
            
            if not (-180 <= lng <= 180):
                errors.append(f"Point {i}: Longitude must be between -180 and 180")
            
            # Kenya-specific validation (optional)
            if not (-5 <= lat <= 5 and 33 <= lng <= 42):
                warnings.append(f"Point {i}: Coordinates appear to be outside Kenya")
        
        # Check for duplicate consecutive points
        for i in range(len(points) - 1):
            try:
                p1_lat, p1_lng = float(points[i]['lat']), float(points[i]['lng'])
                p2_lat, p2_lng = float(points[i+1]['lat']), float(points[i+1]['lng'])
                
                if p1_lat == p2_lat and p1_lng == p2_lng:
                    warnings.append(f"Points {i} and {i+1} are duplicates")
            except:
                pass
        
        # Try to create polygon for validation
        if len(errors) == 0:
            try:
                coords = [(float(p['lng']), float(p['lat'])) for p in points]
                
                # Close polygon if not closed
                if coords[0] != coords[-1]:
                    coords.append(coords[0])
                
                polygon = Polygon(coords, srid=4326)
                
                # Validate polygon
                if not polygon.valid:
                    errors.append("Polygon geometry is invalid (self-intersecting or malformed)")
                
                if not polygon.simple:
                    errors.append("Boundary lines cross each other (self-intersection)")
                
                # Check area
                area_result = AreaCalculator.calculate_polygon_area(polygon)
                is_valid_size, size_message = AreaCalculator.validate_farm_size(
                    area_result['acres']
                )
                
                if not is_valid_size:
                    errors.append(f"Farm size issue: {size_message}")
                
            except Exception as e:
                errors.append(f"Failed to create polygon: {str(e)}")
        
        is_valid = len(errors) == 0
        return is_valid, errors, warnings
    
    @classmethod
    @transaction.atomic
    def create_farm_boundary(cls, farm, boundary_points_data):
        """
        Create farm boundary from points
        
        Args:
            farm: Farm instance
            boundary_points_data: List of dicts with point data
            
        Returns:
            list: Created FarmBoundaryPoint instances
        """
        created_points = []
        
        for i, point_data in enumerate(boundary_points_data):
            lng = float(point_data['lng'])
            lat = float(point_data['lat'])
            
            point = Point(lng, lat, srid=4326)
            
            boundary_point = FarmBoundaryPoint.objects.create(
                farm=farm,
                point=point,
                sequence=i,
                altitude=point_data.get('altitude'),
                accuracy=point_data.get('accuracy'),
                recorded_at=point_data.get('recorded_at')
            )
            
            created_points.append(boundary_point)
        
        return created_points
    
    @classmethod
    def create_polygon_from_points(cls, points):
        """
        Create Polygon from boundary points
        
        Args:
            points: List of dicts with 'lat' and 'lng'
            
        Returns:
            Polygon: Django GIS Polygon
        """
        coords = [(float(p['lng']), float(p['lat'])) for p in points]
        
        # Close the polygon
        if coords[0] != coords[-1]:
            coords.append(coords[0])
        
        return Polygon(coords, srid=4326)
    
    @classmethod
    def simplify_boundary(cls, polygon, tolerance=0.0001):
        """
        Simplify polygon boundary to reduce complexity
        
        Args:
            polygon: Django GIS Polygon
            tolerance: Simplification tolerance in degrees
            
        Returns:
            Polygon: Simplified polygon
        """
        return polygon.simplify(tolerance, preserve_topology=True)
    
    @classmethod
    def check_boundary_overlap(cls, farm, exclude_farms=None):
        """
        Check if farm boundary overlaps with other farms
        
        Args:
            farm: Farm instance
            exclude_farms: List of farm IDs to exclude from check
            
        Returns:
            dict: Overlap detection results
        """
        # Get nearby farms
        nearby_farms = Farm.objects.filter(
            center_point__distance_lte=(farm.center_point, D(km=5)),
            is_active=True
        ).exclude(id=farm.id)
        
        if exclude_farms:
            nearby_farms = nearby_farms.exclude(id__in=exclude_farms)
        
        overlaps = []
        
        for other_farm in nearby_farms:
            # Check if boundaries overlap
            if farm.boundary.overlaps(other_farm.boundary):
                overlap_area = farm.boundary.intersection(other_farm.boundary).area
                overlap_percentage = (overlap_area / farm.boundary.area) * 100
                
                overlaps.append({
                    'farm_id': other_farm.farm_id,
                    'farmer_name': other_farm.farmer.full_name,
                    'overlap_area_sq_meters': round(overlap_area, 2),
                    'overlap_percentage': round(overlap_percentage, 2)
                })
        
        return {
            'has_overlaps': len(overlaps) > 0,
            'overlap_count': len(overlaps),
            'overlaps': overlaps
        }
    
    @classmethod
    def calculate_boundary_accuracy(cls, boundary_points):
        """
        Calculate estimated boundary accuracy from GPS points
        
        Args:
            boundary_points: QuerySet or list of FarmBoundaryPoint instances
            
        Returns:
            dict: Accuracy metrics
        """
        points_with_accuracy = [
            p for p in boundary_points
            if p.accuracy is not None
        ]
        
        if not points_with_accuracy:
            return {
                'has_accuracy_data': False,
                'average_accuracy': None,
                'max_accuracy': None,
                'min_accuracy': None
            }
        
        accuracies = [p.accuracy for p in points_with_accuracy]
        
        return {
            'has_accuracy_data': True,
            'average_accuracy': round(sum(accuracies) / len(accuracies), 2),
            'max_accuracy': round(max(accuracies), 2),
            'min_accuracy': round(min(accuracies), 2),
            'points_with_data': len(points_with_accuracy),
            'total_points': len(boundary_points)
        }
    
    @classmethod
    def convert_to_geojson(cls, farm):
        """
        Convert farm boundary to GeoJSON format
        
        Args:
            farm: Farm instance
            
        Returns:
            dict: GeoJSON Feature
        """
        coords = farm.boundary.coords[0]
        
        return {
            'type': 'Feature',
            'geometry': {
                'type': 'Polygon',
                'coordinates': [[
                    [point[0], point[1]] for point in coords
                ]]
            },
            'properties': {
                'farm_id': farm.farm_id,
                'farmer_name': farm.farmer.full_name,
                'size_acres': float(farm.size_acres),
                'size_hectares': float(farm.size_hectares),
                'county': farm.county,
                'satellite_verified': farm.satellite_verified
            }
        }
    
    @classmethod
    def convert_from_geojson(cls, geojson_feature):
        """
        Extract polygon from GeoJSON Feature
        
        Args:
            geojson_feature: GeoJSON Feature dict
            
        Returns:
            Polygon: Django GIS Polygon
        """
        geometry = geojson_feature['geometry']
        
        if geometry['type'] != 'Polygon':
            raise ValueError("GeoJSON must be a Polygon")
        
        coords = geometry['coordinates'][0]
        
        # Convert to (lng, lat) tuples
        polygon_coords = [(point[0], point[1]) for point in coords]
        
        return Polygon(polygon_coords, srid=4326)
    
    @classmethod
    def buffer_boundary(cls, polygon, distance_meters):
        """
        Create a buffer around the boundary
        
        Args:
            polygon: Django GIS Polygon
            distance_meters: Buffer distance in meters
            
        Returns:
            Polygon: Buffered polygon
        """
        # Convert meters to degrees (approximate)
        # 1 degree ≈ 111,000 meters at equator
        distance_degrees = distance_meters / 111000
        
        return polygon.buffer(distance_degrees)
    
    @classmethod
    def get_boundary_vertices(cls, farm):
        """
        Get all vertices of farm boundary
        
        Args:
            farm: Farm instance
            
        Returns:
            list: List of coordinate dicts
        """
        coords = farm.boundary.coords[0]
        
        return [
            {
                'latitude': point[1],
                'longitude': point[0],
                'sequence': i
            }
            for i, point in enumerate(coords)
        ]
    
    @classmethod
    def calculate_distance_between_farms(cls, farm1, farm2):
        """
        Calculate distance between two farms (center to center)
        
        Args:
            farm1: First Farm instance
            farm2: Second Farm instance
            
        Returns:
            dict: Distance metrics
        """
        distance_meters = farm1.center_point.distance(farm2.center_point)
        distance_km = distance_meters / 1000
        
        return {
            'distance_meters': round(distance_meters, 2),
            'distance_km': round(distance_km, 2),
            'distance_miles': round(distance_km * 0.621371, 2)
        }
    
    @classmethod
    def validate_kenya_location(cls, point):
        """
        Validate if point is within Kenya boundaries
        
        Args:
            point: Django GIS Point
            
        Returns:
            bool: True if within Kenya
        """
        # Kenya approximate bounds
        # Latitude: -4.678° to 5.506°
        # Longitude: 33.893° to 41.899°
        
        lat = point.y
        lng = point.x
        
        return (-4.678 <= lat <= 5.506) and (33.893 <= lng <= 41.899)