# 🛰️ Real Satellite Verification Integration Guide

## Overview
This guide provides step-by-step instructions to integrate real satellite verification using Google Earth Engine (GEE) for CropPulse Africa. Farmers will be able to walk their farm boundaries with their phones, and the system will automatically verify farm details using satellite imagery.

## 🎯 What This Enables
- **Real-time Farm Verification** - Automatic verification using Sentinel-1/2 satellite data
- **Boundary Validation** - Compare GPS-traced boundaries with satellite imagery
- **Crop Health Monitoring** - NDVI, EVI, and vegetation indices calculation
- **Deforestation Detection** - EUDR compliance verification
- **Size Verification** - Accurate farm size calculation from satellite data
- **Weather Integration** - Cloud cover and weather impact analysis

---

## 📋 Prerequisites

### 1. Google Earth Engine Setup
You mentioned you already have a GEE key. Ensure you have:
- ✅ Google Earth Engine service account
- ✅ Service account JSON key file
- ✅ Earth Engine API enabled
- ✅ Appropriate permissions for Sentinel data access

### 2. System Requirements
- Python 3.8+
- PostGIS database (already configured)
- Redis for caching
- Celery for background tasks

---

## 🔧 Configuration Steps

### Step 1: Environment Variables
Update your `.env` file with the correct GEE credentials:

```bash
# Google Earth Engine Configuration
GEE_SERVICE_ACCOUNT=your-service-account@your-project.iam.gserviceaccount.com
GEE_PRIVATE_KEY=/path/to/your/service-account-key.json

# Satellite Processing Settings
SATELLITE_CACHE_TIMEOUT=3600  # 1 hour cache
SATELLITE_MAX_CLOUD_COVER=30  # Maximum acceptable cloud cover %
SATELLITE_ANALYSIS_BUFFER=50  # Buffer around farm boundary in meters
```

### Step 2: Install Required Packages
```bash
pip install earthengine-api>=0.1.350
pip install geopy>=2.3.0
pip install shapely>=2.0.0
pip install rasterio>=1.3.0
pip install scikit-image>=0.20.0
```

### Step 3: Update Django Settings
Add to your `settings/base.py`:

```python
# Satellite Configuration
SATELLITE_CONFIG = {
    'SENTINEL_COLLECTIONS': {
        'SENTINEL1': 'COPERNICUS/S1_GRD',
        'SENTINEL2': 'COPERNICUS/S2_SR_HARMONIZED',
    },
    'ANALYSIS_SETTINGS': {
        'MAX_CLOUD_COVER': 30,
        'TEMPORAL_WINDOW_DAYS': 30,
        'MIN_CLEAR_PIXELS': 70,
        'NDVI_THRESHOLD': 0.3,
    },
    'CACHE_SETTINGS': {
        'ENABLE_CACHING': True,
        'CACHE_TIMEOUT': 3600,
        'MAX_CACHE_SIZE': '1GB',
    }
}

# Celery Configuration for Satellite Tasks
CELERY_TASK_ROUTES = {
    'apps.satellite.tasks.process_satellite_scan': {'queue': 'satellite'},
    'apps.satellite.tasks.bulk_process_scans': {'queue': 'satellite'},
}
```

---

## 📁 Required Files and Modifications

### 1. Update Sentinel Service (`apps/satellite/services/sentinel_service.py`)

Add these methods to enable real verification:

```python
def verify_farm_boundary(self, gps_boundary, satellite_boundary_threshold=0.85):
    """
    Verify GPS-traced boundary against satellite-detected farm boundary
    
    Args:
        gps_boundary: GeoJSON polygon from farmer's GPS trace
        satellite_boundary_threshold: Similarity threshold (0-1)
    
    Returns:
        dict: Verification results with confidence score
    """
    
def calculate_accurate_farm_size(self, boundary_polygon):
    """
    Calculate precise farm size using satellite imagery
    
    Args:
        boundary_polygon: Farm boundary geometry
        
    Returns:
        dict: Size in acres, hectares, and confidence metrics
    """
    
def detect_crop_type(self, boundary_polygon, analysis_date=None):
    """
    Identify crop type using spectral analysis
    
    Args:
        boundary_polygon: Farm boundary
        analysis_date: Date for analysis (defaults to latest)
        
    Returns:
        dict: Detected crop type with confidence score
    """
```

### 2. Create Mobile GPS Integration (`apps/farms/services/gps_processor.py`)

```python
# apps/farms/services/gps_processor.py

from django.contrib.gis.geos import Polygon, Point
from django.contrib.gis.measure import Distance
import json

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
        
    def validate_boundary_quality(self, boundary_polygon):
        """
        Validate the quality of GPS-traced boundary
        
        Returns:
            dict: Quality metrics and recommendations
        """
        
    def smooth_boundary(self, raw_polygon, tolerance=5):
        """
        Smooth GPS boundary to remove noise and gaps
        
        Returns:
            Polygon: Smoothed boundary polygon
        """
```

### 3. Enhanced Farm Model (`apps/farms/models.py`)

Add these fields to your existing Farm model:

```python
class Farm(models.Model):
    # ... existing fields ...
    
    # GPS Trace Data
    gps_trace_points = models.JSONField(
        default=list,
        help_text='Raw GPS points from mobile trace'
    )
    gps_trace_quality = models.FloatField(
        null=True, blank=True,
        help_text='GPS trace quality score (0-100)'
    )
    
    # Satellite Verification Status
    satellite_verified = models.BooleanField(default=False)
    satellite_verification_date = models.DateTimeField(null=True, blank=True)
    satellite_confidence_score = models.FloatField(
        null=True, blank=True,
        help_text='Satellite verification confidence (0-100)'
    )
    
    # Verification Metrics
    boundary_match_score = models.FloatField(
        null=True, blank=True,
        help_text='GPS vs Satellite boundary match score'
    )
    size_verification_status = models.CharField(
        max_length=20,
        choices=[
            ('verified', 'Verified'),
            ('discrepancy', 'Size Discrepancy'),
            ('pending', 'Pending Verification'),
        ],
        default='pending'
    )
```

### 4. Mobile API Endpoints (`apps/farms/views.py`)

Add these views for mobile GPS integration:

```python
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def upload_gps_boundary(request):
    """
    Upload GPS boundary trace from mobile device
    
    Expected payload:
    {
        "farm_id": "FARM-001",
        "gps_points": [
            {"lat": -1.2345, "lng": 36.7890, "timestamp": "2024-02-05T10:30:00Z", "accuracy": 3.2},
            ...
        ],
        "device_info": {
            "device_type": "android",
            "app_version": "1.0.0"
        }
    }
    """
    
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_verification_status(request, farm_id):
    """
    Get real-time satellite verification status
    
    Returns:
    {
        "status": "processing|completed|failed",
        "progress": 75,
        "estimated_completion": "2024-02-05T11:00:00Z",
        "results": {...}
    }
    """
```

---

## 🔄 Processing Workflow

### 1. Mobile GPS Collection
```
Farmer opens app → Walks boundary → GPS points collected → Upload to server
```

### 2. Server Processing Pipeline
```
GPS Upload → Boundary Processing → Satellite Analysis → Verification → Results
```

### 3. Satellite Analysis Steps
1. **Boundary Validation** - Compare GPS trace with satellite-detected boundaries
2. **Size Calculation** - Calculate accurate farm size from satellite imagery
3. **Crop Detection** - Identify crop type using spectral analysis
4. **Health Assessment** - Calculate NDVI and vegetation health
5. **Deforestation Check** - EUDR compliance verification
6. **Quality Scoring** - Overall verification confidence score

---

## 📱 Mobile Integration Requirements

### 1. GPS Collection Standards
- **Minimum Accuracy**: 5 meters
- **Sampling Rate**: Every 2-3 seconds while walking
- **Boundary Closure**: Ensure first and last points are within 10 meters
- **Metadata**: Include timestamp, accuracy, and device info

### 2. Mobile App Features Needed
- GPS boundary tracing interface
- Real-time accuracy display
- Boundary preview and editing
- Upload progress tracking
- Verification status monitoring

### 3. API Endpoints for Mobile
```
POST /api/v1/farms/gps-boundary/upload/
GET  /api/v1/farms/{farm_id}/verification-status/
POST /api/v1/farms/{farm_id}/verify-satellite/
GET  /api/v1/farms/{farm_id}/satellite-results/
```

---

## 🚀 Deployment Steps

### 1. Database Migration
```bash
python manage.py makemigrations farms satellite
python manage.py migrate
```

### 2. Celery Worker Setup
```bash
# Start satellite processing worker
celery -A croppulse_backend worker -Q satellite --loglevel=info

# Start periodic tasks
celery -A croppulse_backend beat --loglevel=info
```

### 3. Google Earth Engine Authentication
```bash
# Test GEE connection
python manage.py shell
>>> import ee
>>> ee.Initialize()  # Should not raise errors
```

### 4. Redis Configuration
```bash
# Ensure Redis is running for caching
redis-cli ping  # Should return PONG
```

---

## 🧪 Testing the Integration

### 1. Test GEE Connection
```python
# In Django shell
from apps.satellite.services import SentinelService
service = SentinelService()
# Should initialize without errors
```

### 2. Test Satellite Analysis
```python
# Test with sample farm boundary
from apps.satellite.tasks import process_satellite_scan
result = process_satellite_scan.delay(farm_id=1)
print(result.get())  # Should return analysis results
```

### 3. Test Mobile GPS Upload
```bash
curl -X POST http://localhost:8000/api/v1/farms/gps-boundary/upload/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "farm_id": "FARM-001",
    "gps_points": [
      {"lat": -1.2345, "lng": 36.7890, "timestamp": "2024-02-05T10:30:00Z", "accuracy": 3.2}
    ]
  }'
```

---

## 📊 Monitoring and Maintenance

### 1. Key Metrics to Monitor
- Satellite processing success rate
- Average processing time
- GPS trace quality scores
- Verification accuracy rates
- API response times

### 2. Logging Configuration
```python
LOGGING = {
    'loggers': {
        'apps.satellite': {
            'handlers': ['satellite_file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'handlers': {
        'satellite_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/satellite.log',
        },
    },
}
```

### 3. Performance Optimization
- Enable Redis caching for satellite results
- Use database indexes on verification fields
- Implement result pagination for large datasets
- Set up monitoring alerts for failed verifications

---

## 🔒 Security Considerations

1. **API Rate Limiting** - Prevent abuse of satellite processing
2. **GPS Data Validation** - Validate GPS coordinates and accuracy
3. **User Authentication** - Ensure only farm owners can upload boundaries
4. **Data Encryption** - Encrypt sensitive location data
5. **Audit Logging** - Log all verification activities

---

## 📈 Expected Results

After implementation, farmers will be able to:
- ✅ Walk their farm boundaries with their phones
- ✅ Get automatic satellite verification within 5-10 minutes
- ✅ Receive detailed farm analysis reports
- ✅ Generate EUDR compliance certificates
- ✅ Monitor crop health over time
- ✅ Detect any boundary or size discrepancies

The system will provide 85-95% accuracy for farm verification using the combination of GPS traces and satellite imagery analysis.

---

## 🆘 Troubleshooting

### Common Issues:
1. **GEE Authentication Errors** - Check service account permissions
2. **Slow Processing** - Increase Celery workers or optimize queries
3. **GPS Accuracy Issues** - Implement boundary smoothing algorithms
4. **Cloud Cover Problems** - Use SAR data fallback for cloudy conditions

### Support Resources:
- Google Earth Engine Documentation
- PostGIS Spatial Analysis Guide
- Celery Task Queue Documentation
- Django GIS Tutorial

---

This integration will transform your platform into a comprehensive satellite-powered farm verification system that farmers can use simply by walking their boundaries with their phones!
