# apps/climate/admin.py
from django.contrib import admin
from apps.climate.models import ClimateData, ClimateRiskAssessment


@admin.register(ClimateData)
class ClimateDataAdmin(admin.ModelAdmin):
    """Admin interface for Climate Data"""
    
    list_display = [
        'id',
        'farm',
        'date',
        'temperature_avg',
        'rainfall',
        'humidity',
        'is_forecast',
        'data_source',
        'created_at'
    ]
    
    list_filter = [
        'is_forecast',
        'data_source',
        'date',
        'created_at'
    ]
    
    search_fields = [
        'farm__name',
        'farm__farmer__first_name',
        'farm__farmer__last_name',
        'farm__farmer__pulse_id'
    ]
    
    readonly_fields = [
        'created_at'
    ]
    
    fieldsets = (
        ('Farm Information', {
            'fields': ('farm', 'date', 'data_source', 'is_forecast')
        }),
        ('Temperature Data', {
            'fields': ('temperature_max', 'temperature_min', 'temperature_avg')
        }),
        ('Rainfall Data', {
            'fields': ('rainfall', 'rainfall_probability')
        }),
        ('Other Metrics', {
            'fields': ('humidity', 'wind_speed', 'solar_radiation')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        })
    )
    
    date_hierarchy = 'date'
    
    ordering = ['-date', '-created_at']
    
    list_per_page = 50
    
    def get_queryset(self, request):
        """Optimize queryset"""
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('farm', 'farm__farmer')
        return queryset


@admin.register(ClimateRiskAssessment)
class ClimateRiskAssessmentAdmin(admin.ModelAdmin):
    """Admin interface for Climate Risk Assessments"""
    
    list_display = [
        'id',
        'farm',
        'assessment_date',
        'overall_climate_risk',
        'drought_risk',
        'flood_risk',
        'heat_stress_risk',
        'get_risk_level'
    ]
    
    list_filter = [
        'assessment_date',
        'created_at'
    ]
    
    search_fields = [
        'farm__name',
        'farm__farmer__first_name',
        'farm__farmer__last_name',
        'farm__farmer__pulse_id'
    ]
    
    readonly_fields = [
        'assessment_date',
        'created_at',
        'get_risk_level',
        'get_drought_level',
        'get_flood_level',
        'get_heat_level'
    ]
    
    fieldsets = (
        ('Assessment Information', {
            'fields': ('farm', 'assessment_date', 'analysis_start_date', 'analysis_end_date')
        }),
        ('Risk Scores', {
            'fields': (
                ('drought_risk', 'get_drought_level'),
                ('flood_risk', 'get_flood_level'),
                ('heat_stress_risk', 'get_heat_level'),
                ('overall_climate_risk', 'get_risk_level')
            )
        }),
        ('Rainfall Analysis', {
            'fields': (
                'historical_rainfall_avg',
                'current_season_rainfall',
                'rainfall_deviation_percentage'
            )
        }),
        ('Recommendations', {
            'fields': ('recommendations',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at',)
        })
    )
    
    date_hierarchy = 'assessment_date'
    
    ordering = ['-assessment_date']
    
    list_per_page = 25
    
    def get_queryset(self, request):
        """Optimize queryset"""
        queryset = super().get_queryset(request)
        queryset = queryset.select_related('farm', 'farm__farmer')
        return queryset
    
    def get_risk_level(self, obj):
        """Display overall risk level"""
        return self._get_level_display(obj.overall_climate_risk)
    get_risk_level.short_description = 'Overall Risk Level'
    
    def get_drought_level(self, obj):
        """Display drought risk level"""
        return self._get_level_display(obj.drought_risk)
    get_drought_level.short_description = 'Drought Level'
    
    def get_flood_level(self, obj):
        """Display flood risk level"""
        return self._get_level_display(obj.flood_risk)
    get_flood_level.short_description = 'Flood Level'
    
    def get_heat_level(self, obj):
        """Display heat stress level"""
        return self._get_level_display(obj.heat_stress_risk)
    get_heat_level.short_description = 'Heat Stress Level'
    
    def _get_level_display(self, risk_score):
        """Convert risk score to level with color"""
        if risk_score is None:
            return 'N/A'
        if risk_score >= 70:
            return f'🔴 CRITICAL ({risk_score:.1f})'
        elif risk_score >= 40:
            return f'🟠 HIGH ({risk_score:.1f})'
        elif risk_score >= 20:
            return f'🟡 MODERATE ({risk_score:.1f})'
        else:
            return f'🟢 LOW ({risk_score:.1f})'