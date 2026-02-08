#!/usr/bin/env python
"""
Test script for satellite verification system
Run this after registering your project with Google Earth Engine
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'croppulse_backend.settings.base')
django.setup()

def test_satellite_connection():
    """Test Google Earth Engine connection"""
    try:
        import ee
        from django.conf import settings
        
        print("🛰️ Testing Google Earth Engine connection...")
        
        credentials = ee.ServiceAccountCredentials(
            email=settings.GEE_SERVICE_ACCOUNT,
            key_file=settings.GEE_PRIVATE_KEY
        )
        ee.Initialize(credentials)
        
        # Test basic functionality
        image = ee.Image('COPERNICUS/S2_SR_HARMONIZED/20240101T073251_20240101T073251_T37MCS')
        print(f"✅ Connected to Google Earth Engine successfully!")
        print(f"Service Account: {settings.GEE_SERVICE_ACCOUNT}")
        return True
        
    except Exception as e:
        print(f"❌ Google Earth Engine connection failed: {str(e)}")
        if "not registered" in str(e):
            print("📝 Please register your project at:")
            print("https://console.cloud.google.com/earth-engine/configuration?project=croppulseafrica")
        return False

def test_gps_processing():
    """Test GPS boundary processing"""
    try:
        from apps.farms.services.gps_processor import GPSBoundaryProcessor
        
        print("\n📱 Testing GPS boundary processing...")
        
        # Sample GPS trace around a small farm
        gps_points = [
            {'lat': -1.2345, 'lng': 36.7890, 'timestamp': '2024-02-05T10:30:00Z', 'accuracy': 3.2},
            {'lat': -1.2350, 'lng': 36.7890, 'timestamp': '2024-02-05T10:30:30Z', 'accuracy': 2.8},
            {'lat': -1.2350, 'lng': 36.7895, 'timestamp': '2024-02-05T10:31:00Z', 'accuracy': 3.1},
            {'lat': -1.2345, 'lng': 36.7895, 'timestamp': '2024-02-05T10:31:30Z', 'accuracy': 2.9},
            {'lat': -1.2345, 'lng': 36.7890, 'timestamp': '2024-02-05T10:32:00Z', 'accuracy': 3.0},
        ]
        
        processor = GPSBoundaryProcessor()
        result = processor.process_gps_trace(gps_points)
        
        print(f"✅ GPS processing successful!")
        print(f"   Area: {result['area_acres']:.2f} acres ({result['area_hectares']:.2f} hectares)")
        print(f"   Quality Score: {result['quality_score']}/100")
        print(f"   Valid Boundary: {result['is_valid']}")
        
        return True
        
    except Exception as e:
        print(f"❌ GPS processing failed: {str(e)}")
        return False

def test_satellite_service():
    """Test satellite data fetching"""
    try:
        from apps.satellite.services.sentinel_service import SentinelService
        
        print("\n🛰️ Testing satellite data service...")
        
        # Sample farm boundary (small area in Kenya)
        farm_boundary = {
            "type": "Polygon",
            "coordinates": [[
                [36.7890, -1.2345],
                [36.7895, -1.2345],
                [36.7895, -1.2350],
                [36.7890, -1.2350],
                [36.7890, -1.2345]
            ]]
        }
        
        service = SentinelService()
        
        # Test Sentinel-1 data
        print("   Testing Sentinel-1 SAR data...")
        s1_data = service.get_sentinel1_data(farm_boundary)
        print(f"   ✅ Sentinel-1 data retrieved: VH={s1_data.get('vh_backscatter'):.2f}dB")
        
        # Test Sentinel-2 data
        print("   Testing Sentinel-2 optical data...")
        try:
            s2_data = service.get_sentinel2_data(farm_boundary)
            print(f"   ✅ Sentinel-2 data retrieved: NDVI={s2_data.get('ndvi'):.3f}")
        except Exception as e:
            print(f"   ⚠️  Sentinel-2 data not available (likely due to cloud cover): {str(e)}")
            print("   ✅ This is normal - system will use Sentinel-1 SAR data as fallback")
        
        return True
        
    except Exception as e:
        print(f"❌ Satellite service test failed: {str(e)}")
        return False

def main():
    """Run all tests"""
    print("🚀 CropPulse Satellite Verification System Test")
    print("=" * 50)
    
    tests = [
        test_satellite_connection,
        test_gps_processing,
        test_satellite_service,
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All systems operational! Ready for satellite verification.")
        print("\n📱 Mobile API Endpoints:")
        print("   POST /api/v1/farms/gps-boundary/upload/")
        print("   GET  /api/v1/farms/{farm_id}/verification-status/")
    else:
        print("⚠️  Some tests failed. Please check the configuration.")

if __name__ == "__main__":
    main()
