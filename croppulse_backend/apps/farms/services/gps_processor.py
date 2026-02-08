# apps/farms/services/gps_processor.py

from django.contrib.gis.geos import Polygon, Point
from django.contrib.gis.measure import Distance
from geopy.distance import geodesic
import json
import logging

logger = logging.getLogger(__name__)


class GPSBoundaryProcessor:
    """Process GPS traces from mobile devices into farm boundaries"""
    
    def process_gps_trace(self, gps_points):
        """
        Convert GPS trace points into a valid farm boundary polygon
        
        Args:
            gps_points: List of [lat, lng, timestamp, accuracy] points
            
        Returns:
            dict: Processed boundary with validation metrics
        """
        try:
            if len(gps_points) < 4:
                raise ValueError("At least 4 GPS points required to create a boundary")
            
            # Extract coordinates and convert to [lng, lat] for PostGIS
            coordinates = []
            for point in gps_points:
                lat, lng = point['lat'], point['lng']
                coordinates.append([lng, lat])
            
            # Ensure polygon is closed
            if coordinates[0] != coordinates[-1]:
                coordinates.append(coordinates[0])
            
            # Create polygon
            polygon = Polygon(coordinates)
            
            # Validate and smooth the boundary
            quality_metrics = self.validate_boundary_quality(polygon, gps_points)
            smoothed_polygon = self.smooth_boundary(polygon)
            
            # Calculate area
            area_hectares = self._calculate_area_hectares(smoothed_polygon)
            area_acres = area_hectares * 2.47105  # Convert to acres
            
            return {
                'boundary': smoothed_polygon,
                'area_hectares': round(area_hectares, 2),
                'area_acres': round(area_acres, 2),
                'quality_score': quality_metrics['overall_score'],
                'quality_metrics': quality_metrics,
                'point_count': len(gps_points),
                'is_valid': polygon.valid and quality_metrics['overall_score'] > 60
            }
            
        except Exception as e:
            logger.error(f"Error processing GPS trace: {str(e)}")
            raise
    
    def validate_boundary_quality(self, boundary_polygon, gps_points):
        """
        Validate the quality of GPS-traced boundary
        
        Returns:
            dict: Quality metrics and recommendations
        """
        try:
            metrics = {
                'accuracy_score': 0,
                'completeness_score': 0,
                'consistency_score': 0,
                'overall_score': 0,
                'issues': [],
                'recommendations': []
            }
            
            # Check GPS accuracy
            accuracies = [point.get('accuracy', 10) for point in gps_points]
            avg_accuracy = sum(accuracies) / len(accuracies)
            
            if avg_accuracy <= 3:
                metrics['accuracy_score'] = 100
            elif avg_accuracy <= 5:
                metrics['accuracy_score'] = 80
            elif avg_accuracy <= 10:
                metrics['accuracy_score'] = 60
            else:
                metrics['accuracy_score'] = 30
                metrics['issues'].append('Poor GPS accuracy')
                metrics['recommendations'].append('Walk boundary again with better GPS signal')
            
            # Check boundary completeness (closure)
            first_point = [gps_points[0]['lat'], gps_points[0]['lng']]
            last_point = [gps_points[-1]['lat'], gps_points[-1]['lng']]
            closure_distance = geodesic(first_point, last_point).meters
            
            if closure_distance <= 5:
                metrics['completeness_score'] = 100
            elif closure_distance <= 10:
                metrics['completeness_score'] = 80
            elif closure_distance <= 20:
                metrics['completeness_score'] = 60
            else:
                metrics['completeness_score'] = 30
                metrics['issues'].append('Boundary not properly closed')
                metrics['recommendations'].append('Ensure you return to starting point')
            
            # Check point consistency (no major gaps)
            point_distances = []
            for i in range(1, len(gps_points)):
                prev_point = [gps_points[i-1]['lat'], gps_points[i-1]['lng']]
                curr_point = [gps_points[i]['lat'], gps_points[i]['lng']]
                distance = geodesic(prev_point, curr_point).meters
                point_distances.append(distance)
            
            avg_distance = sum(point_distances) / len(point_distances)
            max_gap = max(point_distances)
            
            if max_gap <= avg_distance * 3:
                metrics['consistency_score'] = 100
            elif max_gap <= avg_distance * 5:
                metrics['consistency_score'] = 80
            else:
                metrics['consistency_score'] = 60
                metrics['issues'].append('Large gaps in GPS trace')
                metrics['recommendations'].append('Walk more slowly and consistently')
            
            # Calculate overall score
            metrics['overall_score'] = round(
                (metrics['accuracy_score'] + metrics['completeness_score'] + metrics['consistency_score']) / 3
            )
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error validating boundary quality: {str(e)}")
            return {'overall_score': 0, 'issues': ['Validation failed'], 'recommendations': []}
    
    def smooth_boundary(self, raw_polygon, tolerance=5):
        """
        Smooth GPS boundary to remove noise and gaps
        
        Args:
            raw_polygon: Raw GPS polygon
            tolerance: Smoothing tolerance in meters
            
        Returns:
            Polygon: Smoothed boundary polygon
        """
        try:
            # Use PostGIS simplify to smooth the boundary
            # Convert tolerance from meters to degrees (approximate)
            tolerance_degrees = tolerance / 111000  # Rough conversion
            
            smoothed = raw_polygon.simplify(tolerance_degrees, preserve_topology=True)
            
            # Ensure the polygon is still valid
            if not smoothed.valid:
                logger.warning("Smoothed polygon is invalid, returning original")
                return raw_polygon
            
            return smoothed
            
        except Exception as e:
            logger.error(f"Error smoothing boundary: {str(e)}")
            return raw_polygon
    
    def _calculate_area_hectares(self, polygon):
        """Calculate polygon area in hectares"""
        try:
            # Get area in square meters (PostGIS geography)
            area_sq_meters = polygon.area
            # Convert to hectares
            area_hectares = area_sq_meters / 10000
            return area_hectares
        except Exception as e:
            logger.error(f"Error calculating area: {str(e)}")
            return 0
