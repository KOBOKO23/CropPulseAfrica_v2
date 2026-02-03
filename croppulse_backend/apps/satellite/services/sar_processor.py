# apps/satellite/services/sar_processor.py

import logging
import numpy as np

logger = logging.getLogger(__name__)


class SARProcessor:
    """Service for processing Sentinel-1 SAR data"""
    
    def __init__(self):
        """Initialize SAR processor"""
        pass
    
    def process_sar_backscatter(self, vh_value, vv_value):
        """
        Process SAR backscatter values
        
        Args:
            vh_value: VH polarization backscatter in dB
            vv_value: VV polarization backscatter in dB
        
        Returns:
            dict: Processed SAR metrics
        """
        if vh_value is None or vv_value is None:
            return {
                'valid': False,
                'message': 'Missing backscatter data'
            }
        
        # Calculate VH/VV ratio
        if vv_value != 0:
            vh_vv_ratio = vh_value / vv_value
        else:
            vh_vv_ratio = 0
        
        # Estimate soil moisture from VH
        soil_moisture = self.estimate_soil_moisture_from_vh(vh_value)
        
        # Estimate crop type likelihood
        crop_likelihood = self.estimate_crop_type(vh_value, vv_value, vh_vv_ratio)
        
        # Detect surface roughness
        surface_roughness = self.detect_surface_roughness(vh_value, vv_value)
        
        return {
            'valid': True,
            'vh_backscatter': vh_value,
            'vv_backscatter': vv_value,
            'vh_vv_ratio': round(vh_vv_ratio, 3),
            'soil_moisture_estimate': soil_moisture,
            'crop_likelihood': crop_likelihood,
            'surface_roughness': surface_roughness
        }
    
    def estimate_soil_moisture_from_vh(self, vh_value):
        """
        Estimate soil moisture from VH backscatter
        
        Args:
            vh_value: VH backscatter in dB
        
        Returns:
            float: Estimated soil moisture percentage (0-100)
        """
        if vh_value is None:
            return None
        
        # Empirical relationship for soil moisture estimation
        # Lower VH values (-25 to -20 dB) indicate drier soil
        # Higher VH values (-15 to -5 dB) indicate wetter soil
        
        min_vh = -25  # Very dry
        max_vh = -5   # Very wet
        
        # Clamp values
        vh_clamped = max(min_vh, min(vh_value, max_vh))
        
        # Linear interpolation to 0-100% scale
        moisture = ((vh_clamped - min_vh) / (max_vh - min_vh)) * 100
        
        return round(moisture, 1)
    
    def estimate_crop_type(self, vh_value, vv_value, vh_vv_ratio):
        """
        Estimate likely crop type based on backscatter characteristics
        
        Args:
            vh_value: VH backscatter
            vv_value: VV backscatter
            vh_vv_ratio: VH/VV ratio
        
        Returns:
            dict: Crop type likelihoods
        """
        likelihoods = {}
        
        # Rice (high VH/VV ratio due to double-bounce)
        if vh_vv_ratio > 0.7:
            likelihoods['rice'] = 'high'
        elif vh_vv_ratio > 0.5:
            likelihoods['rice'] = 'medium'
        else:
            likelihoods['rice'] = 'low'
        
        # Maize (moderate VH, high structure)
        if -18 <= vh_value <= -12:
            likelihoods['maize'] = 'high'
        elif -20 <= vh_value <= -10:
            likelihoods['maize'] = 'medium'
        else:
            likelihoods['maize'] = 'low'
        
        # Bare soil (low VH and VV)
        if vh_value < -22 and vv_value < -18:
            likelihoods['bare_soil'] = 'high'
        else:
            likelihoods['bare_soil'] = 'low'
        
        # Dense vegetation (high VH due to volume scattering)
        if vh_value > -12:
            likelihoods['dense_vegetation'] = 'high'
        elif vh_value > -15:
            likelihoods['dense_vegetation'] = 'medium'
        else:
            likelihoods['dense_vegetation'] = 'low'
        
        return likelihoods
    
    def detect_surface_roughness(self, vh_value, vv_value):
        """
        Detect surface roughness from backscatter
        
        Args:
            vh_value: VH backscatter
            vv_value: VV backscatter
        
        Returns:
            str: Roughness category
        """
        # Higher VV indicates rougher surface
        if vv_value > -10:
            return 'very_rough'
        elif vv_value > -14:
            return 'rough'
        elif vv_value > -18:
            return 'moderate'
        else:
            return 'smooth'
    
    def detect_flooding(self, vh_value, vv_value):
        """
        Detect potential flooding based on SAR characteristics
        
        Args:
            vh_value: VH backscatter
            vv_value: VV backscatter
        
        Returns:
            dict: Flooding detection results
        """
        # Water bodies have very low backscatter
        # VV < -20 dB and VH < -25 dB suggests water
        
        if vv_value < -20 and vh_value < -25:
            likelihood = 'high'
            confidence = 0.85
        elif vv_value < -18 and vh_value < -23:
            likelihood = 'medium'
            confidence = 0.65
        else:
            likelihood = 'low'
            confidence = 0.30
        
        return {
            'flooding_likelihood': likelihood,
            'confidence': confidence,
            'recommendation': self._get_flooding_recommendation(likelihood)
        }
    
    def _get_flooding_recommendation(self, likelihood):
        """Get recommendation based on flooding likelihood"""
        if likelihood == 'high':
            return 'Possible flooding detected - verify field conditions immediately'
        elif likelihood == 'medium':
            return 'Potential water accumulation - monitor field drainage'
        else:
            return 'No flooding detected'
    
    def calculate_biomass_estimate(self, vh_value, vv_value):
        """
        Estimate crop biomass from SAR data
        
        Args:
            vh_value: VH backscatter
            vv_value: VV backscatter
        
        Returns:
            dict: Biomass estimation
        """
        # Simplified biomass estimation
        # Higher backscatter generally indicates more biomass
        
        # Combine VH and VV for biomass proxy
        biomass_proxy = (vh_value + vv_value) / 2
        
        if biomass_proxy > -12:
            category = 'high'
            description = 'High crop biomass detected'
        elif biomass_proxy > -15:
            category = 'medium'
            description = 'Moderate crop biomass'
        elif biomass_proxy > -18:
            category = 'low'
            description = 'Low crop biomass'
        else:
            category = 'very_low'
            description = 'Very low or no crop biomass'
        
        return {
            'category': category,
            'description': description,
            'biomass_proxy': round(biomass_proxy, 2),
            'confidence': 'medium'  # SAR biomass estimation is approximate
        }
    
    def apply_speckle_filter(self, backscatter_values, window_size=5):
        """
        Apply speckle filtering to SAR data
        
        Args:
            backscatter_values: Array of backscatter values
            window_size: Filter window size (default 5x5)
        
        Returns:
            array: Filtered backscatter values
        """
        # Simple moving average filter for speckle reduction
        if len(backscatter_values) < window_size:
            return backscatter_values
        
        filtered = []
        half_window = window_size // 2
        
        for i in range(len(backscatter_values)):
            start = max(0, i - half_window)
            end = min(len(backscatter_values), i + half_window + 1)
            window_values = backscatter_values[start:end]
            filtered.append(sum(window_values) / len(window_values))
        
        return filtered
    
    def generate_sar_quality_score(self, vh_value, vv_value, orbit_direction=None):
        """
        Generate quality score for SAR data
        
        Args:
            vh_value: VH backscatter
            vv_value: VV backscatter
            orbit_direction: Ascending or Descending
        
        Returns:
            dict: Quality assessment
        """
        score = 100
        issues = []
        
        # Check for valid backscatter ranges
        if vh_value < -30 or vh_value > 0:
            score -= 20
            issues.append('VH backscatter out of typical range')
        
        if vv_value < -30 or vv_value > 0:
            score -= 20
            issues.append('VV backscatter out of typical range')
        
        # Check for saturation
        if vh_value > -3 or vv_value > -3:
            score -= 15
            issues.append('Possible saturation detected')
        
        # Check for very low signal (noise floor)
        if vh_value < -28 or vv_value < -28:
            score -= 10
            issues.append('Very low signal - possible noise')
        
        # Orbit direction preference (descending often better for agriculture)
        if orbit_direction and orbit_direction.lower() != 'descending':
            score -= 5
            issues.append('Ascending orbit - descending preferred for agriculture')
        
        return {
            'quality_score': max(0, score),
            'quality_level': self._get_quality_level(max(0, score)),
            'issues': issues,
            'usable': score >= 50
        }
    
    def _get_quality_level(self, score):
        """Get quality level from score"""
        if score >= 85:
            return 'excellent'
        elif score >= 70:
            return 'good'
        elif score >= 50:
            return 'acceptable'
        else:
            return 'poor'