# apps/farms/admin.py

from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.html import format_html
from django.db.models import Count
from .models import Farm, FarmBoundaryPoint


@admin.register(Farm)
class FarmAdmin(GISModelAdmin):
    """Admin interface for Farm model with map support"""
    
    # GIS-specific settings
    gis_widget_kwargs = {
        'attrs': {
            'default_zoom': 12,
            'default_lon': 36.8219,  # Nairobi longitude
            'default_lat': -1.2921,  # Nairobi latitude
        },
    }
    
    list_display = [
        'farm_id',
        'farmer_link',
        'county',
        'size_display',
        'verification_badge',
        'primary_badge',
        'satellite_scans_count',
        'created_at'
    ]
    
    list_filter = [
        'county',
        'sub_county',
        'satellite_verified',
        'is_primary',
        'created_at'
    ]
    
    search_fields = [
        'farm_id',
        'farmer__pulse_id',
        'farmer__full_name',
        'county',
        'sub_county',
        'ward'
    ]
    
    readonly_fields = [
        'farm_id',
        'size_hectares',
        'created_at',
        'updated_at',
        'map_preview',
        'farm_statistics'
    ]
    
    fieldsets = (
        ('Identification', {
            'fields': ('farm_id', 'farmer', 'is_primary')
        }),
        ('Location (Map)', {
            'fields': ('boundary', 'center_point', 'map_preview'),
            'classes': ('wide',),
            'description': 'Use the map tools to draw or edit the farm boundary'
        }),
        ('Size & Elevation', {
            'fields': ('size_acres', 'size_hectares', 'elevation')
        }),
        ('Address', {
            'fields': ('county', 'sub_county', 'ward')
        }),
        ('Verification', {
            'fields': ('satellite_verified', 'last_verified')
        }),
        ('Ownership', {
            'fields': ('ownership_document',)
        }),
        ('Statistics', {
            'fields': ('farm_statistics',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    def farmer_link(self, obj):
        """Link to farmer admin page"""
        from django.urls import reverse
        url = reverse('admin:farmers_farmer_change', args=[obj.farmer.id])
        return format_html(
            '<a href="{}">{} ({})</a>',
            url,
            obj.farmer.full_name,
            obj.farmer.pulse_id
        )
    farmer_link.short_description = 'Farmer'
    
    def size_display(self, obj):
        """Display farm size with both units"""
        return format_html(
            '<strong>{:.2f}</strong> acres<br/>'
            '<span style="color: #6b7280; font-size: 11px;">{:.2f} hectares</span>',
            obj.size_acres,
            obj.size_hectares
        )
    size_display.short_description = 'Size'
    
    def verification_badge(self, obj):
        """Display verification status"""
        if obj.satellite_verified:
            return format_html(
                '<span style="background-color: #10b981; color: white; padding: 3px 10px; '
                'border-radius: 12px; font-size: 11px; font-weight: bold;">✓ VERIFIED</span>'
            )
        return format_html(
            '<span style="background-color: #f59e0b; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">UNVERIFIED</span>'
        )
    verification_badge.short_description = 'Satellite'
    
    def primary_badge(self, obj):
        """Display primary farm badge"""
        if obj.is_primary:
            return format_html(
                '<span style="color: #3b82f6; font-weight: bold;">★ Primary</span>'
            )
        return format_html(
            '<span style="color: #9ca3af;">Secondary</span>'
        )
    primary_badge.short_description = 'Type'
    
    def satellite_scans_count(self, obj):
        """Display number of satellite scans"""
        count = obj.satellite_scans.count()
        if count > 0:
            return format_html(
                '<span style="background-color: #8b5cf6; color: white; padding: 2px 8px; '
                'border-radius: 10px; font-size: 11px;">{} scan(s)</span>',
                count
            )
        return format_html(
            '<span style="color: #9ca3af;">No scans</span>'
        )
    satellite_scans_count.short_description = 'Scans'
    
    def map_preview(self, obj):
        """Display map preview (read-only)"""
        if obj.boundary:
            # Get center point coordinates
            center = obj.center_point
            lat = center.y
            lon = center.x
            
            # Create Google Maps link
            maps_url = f"https://www.google.com/maps?q={lat},{lon}&z=15"
            
            html = f'<div style="background: #f3f4f6; padding: 15px; border-radius: 8px;">'
            html += f'<p><strong>Center Point:</strong> {lat:.6f}, {lon:.6f}</p>'
            html += f'<p><strong>Boundary Points:</strong> {len(obj.boundary.coords[0])}</p>'
            html += f'<a href="{maps_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">'
            html += '📍 View on Google Maps</a>'
            html += '</div>'
            
            return format_html(html)
        return 'No boundary data'
    map_preview.short_description = 'Map Info'
    
    def farm_statistics(self, obj):
        """Display farm statistics"""
        scans_count = obj.satellite_scans.count()
        
        # Get latest NDVI if available
        latest_scan = obj.satellite_scans.order_by('-acquisition_date').first()
        latest_ndvi = latest_scan.ndvi if latest_scan and latest_scan.ndvi else None
        
        html = '<div style="background: #f3f4f6; padding: 15px; border-radius: 8px;">'
        html += f'<p><strong>Total Satellite Scans:</strong> {scans_count}</p>'
        
        if latest_scan:
            html += f'<p><strong>Last Scan:</strong> {latest_scan.acquisition_date.strftime("%Y-%m-%d")}</p>'
            if latest_ndvi:
                html += f'<p><strong>Latest NDVI:</strong> {latest_ndvi:.3f}</p>'
                html += f'<p><strong>Crop Health:</strong> {latest_scan.crop_health_status}</p>'
        
        html += f'<p><strong>Elevation:</strong> {obj.elevation}m' if obj.elevation else 'Unknown'
        html += '</div>'
        
        return format_html(html)
    farm_statistics.short_description = 'Statistics'
    
    actions = [
        'mark_as_verified',
        'mark_as_primary',
        'trigger_satellite_scan',
        'export_to_csv'
    ]
    
    def mark_as_verified(self, request, queryset):
        """Mark farms as satellite verified"""
        from django.utils import timezone
        updated = queryset.update(
            satellite_verified=True,
            last_verified=timezone.now()
        )
        self.message_user(request, f'{updated} farm(s) marked as verified.')
    mark_as_verified.short_description = 'Mark as satellite verified'
    
    def mark_as_primary(self, request, queryset):
        """Mark selected farms as primary"""
        # First, unmark all farms for these farmers
        farmer_ids = queryset.values_list('farmer_id', flat=True)
        Farm.objects.filter(farmer_id__in=farmer_ids).update(is_primary=False)
        
        # Then mark selected farms as primary
        updated = queryset.update(is_primary=True)
        self.message_user(request, f'{updated} farm(s) marked as primary.')
    mark_as_primary.short_description = 'Mark as primary farm'
    
    def trigger_satellite_scan(self, request, queryset):
        """Trigger satellite scan for selected farms"""
        from apps.satellite.tasks import process_satellite_scan
        
        count = 0
        for farm in queryset:
            try:
                process_satellite_scan.delay(farm.id)
                count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f'Failed to queue scan for {farm.farm_id}: {str(e)}',
                    level='error'
                )
        
        self.message_user(request, f'{count} satellite scan(s) queued.')
    trigger_satellite_scan.short_description = 'Trigger satellite scan'
    
    def export_to_csv(self, request, queryset):
        """Export farms to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="farms_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Farm ID', 'Farmer Pulse ID', 'Farmer Name', 'County', 'Sub County',
            'Size (Acres)', 'Size (Hectares)', 'Satellite Verified', 'Is Primary',
            'Center Latitude', 'Center Longitude', 'Created Date'
        ])
        
        for farm in queryset.select_related('farmer'):
            writer.writerow([
                farm.farm_id,
                farm.farmer.pulse_id,
                farm.farmer.full_name,
                farm.county,
                farm.sub_county,
                float(farm.size_acres),
                float(farm.size_hectares),
                'Yes' if farm.satellite_verified else 'No',
                'Yes' if farm.is_primary else 'No',
                farm.center_point.y,
                farm.center_point.x,
                farm.created_at.strftime('%Y-%m-%d')
            ])
        
        return response
    export_to_csv.short_description = 'Export to CSV'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('farmer').prefetch_related('satellite_scans')


@admin.register(FarmBoundaryPoint)
class FarmBoundaryPointAdmin(admin.ModelAdmin):
    """Admin interface for individual boundary points"""
    
    list_display = [
        'farm_link',
        'sequence',
        'coordinates_display',
        'created_at'
    ]
    
    list_filter = [
        'created_at'
    ]
    
    search_fields = [
        'farm__farm_id',
        'farm__farmer__pulse_id'
    ]
    
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Farm', {
            'fields': ('farm',)
        }),
        ('Point Data', {
            'fields': ('point', 'sequence')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    ordering = ['farm', 'sequence']
    
    def farm_link(self, obj):
        """Link to farm admin page"""
        from django.urls import reverse
        url = reverse('admin:farms_farm_change', args=[obj.farm.id])
        return format_html(
            '<a href="{}">{}</a>',
            url,
            obj.farm.farm_id
        )
    farm_link.short_description = 'Farm'
    
    def coordinates_display(self, obj):
        """Display coordinates"""
        return format_html(
            '<span style="font-family: monospace;">{:.6f}, {:.6f}</span>',
            obj.point.y,
            obj.point.x
        )
    coordinates_display.short_description = 'Coordinates (Lat, Lon)'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('farm', 'farm__farmer')