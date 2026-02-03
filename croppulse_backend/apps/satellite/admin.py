# apps/satellite/admin.py

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Avg
from .models import SatelliteScan, NDVIHistory


@admin.register(SatelliteScan)
class SatelliteScanAdmin(admin.ModelAdmin):
    """Admin interface for SatelliteScan model"""
    
    list_display = [
        'scan_id',
        'farm_link',
        'satellite_type',
        'acquisition_date',
        'health_badge',
        'ndvi_display',
        'cloud_cover_badge',
        'size_verification_badge',
        'processing_date',
    ]
    
    list_filter = [
        'satellite_type',
        'crop_health_status',
        'processing_status',
        'sar_penetrated_clouds',
        'matches_declared_size',
        'acquisition_date',
        'processing_date',
    ]
    
    search_fields = [
        'scan_id',
        'farm__farm_id',
        'farm__farmer__pulse_id',
        'farm__farmer__full_name',
    ]
    
    readonly_fields = [
        'scan_id',
        'processing_date',
        'created_at',
        'image_preview',
        'detailed_metrics',
    ]
    
    fieldsets = (
        ('Scan Information', {
            'fields': ('scan_id', 'farm', 'satellite_type', 'acquisition_date', 'processing_date', 'processing_status', 'processing_error'),
        }),
        ('Imagery Data', {
            'fields': ('image_url', 'image_preview', 'cloud_cover_percentage', 'sar_penetrated_clouds', 'cloud_mask_url', 'clear_pixel_percentage'),
        }),
        ('Vegetation Indices', {
            'fields': ('ndvi', 'evi', 'savi', 'ndwi', 'msavi'),
            'classes': ('wide',),
        }),
        ('Soil & Crop Analysis', {
            'fields': ('soil_moisture', 'crop_stage', 'crop_health_status'),
        }),
        ('SAR Metrics', {
            'fields': ('vh_backscatter', 'vv_backscatter', 'vh_vv_ratio', 'orbit_direction'),
        }),
        ('Verification', {
            'fields': ('verified_farm_size', 'matches_declared_size', 'size_difference_percentage'),
        }),
        ('Quality & Metadata', {
            'fields': ('data_quality_score', 'resolution_meters'),
        }),
        ('Raw Data', {
            'fields': ('raw_satellite_data', 'detailed_metrics'),
            'classes': ('collapse',),
        }),
    )
    
    date_hierarchy = 'acquisition_date'
    ordering = ['-acquisition_date']
    
    def farm_link(self, obj):
        """Link to farm admin page"""
        from django.urls import reverse
        url = reverse('admin:farms_farm_change', args=[obj.farm.id])
        return format_html('<a href="{}">{}</a>', url, obj.farm.farm_id)
    farm_link.short_description = 'Farm'
    
    def health_badge(self, obj):
        """Display crop health with colored badge"""
        colors = {
            'Healthy': '#10b981',
            'Stressed': '#f59e0b',
            'Poor': '#ef4444',
            'Unknown': '#6b7280',
        }
        color = colors.get(obj.crop_health_status, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; '
            'border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.crop_health_status,
        )
    health_badge.short_description = 'Crop Health'
    
    def ndvi_display(self, obj):
        """Display NDVI with color coding"""
        if obj.ndvi is None:
            return format_html('<span style="color: #9ca3af;">N/A</span>')
        
        # Color based on NDVI value
        if obj.ndvi >= 0.75:
            color = '#10b981'  # Green
        elif obj.ndvi >= 0.60:
            color = '#84cc16'  # Light green
        elif obj.ndvi >= 0.40:
            color = '#f59e0b'  # Orange
        else:
            color = '#ef4444'  # Red
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color, obj.ndvi,
        )
    ndvi_display.short_description = 'NDVI'
    
    def cloud_cover_badge(self, obj):
        """Display cloud cover percentage"""
        if obj.cloud_cover_percentage < 20:
            color = '#10b981'
            icon = '☀️'
        elif obj.cloud_cover_percentage < 50:
            color = '#f59e0b'
            icon = '⛅'
        else:
            color = '#6b7280'
            icon = '☁️'
        
        sar_text = ' (SAR)' if obj.sar_penetrated_clouds else ''
        
        return format_html(
            '<span style="color: {};">{} {:.1f}%{}</span>',
            color, icon, obj.cloud_cover_percentage, sar_text,
        )
    cloud_cover_badge.short_description = 'Cloud Cover'
    
    def size_verification_badge(self, obj):
        """Display size verification status"""
        if obj.matches_declared_size:
            return format_html(
                '<span style="color: #10b981;">✓ Verified</span>'
            )
        return format_html(
            '<span style="color: #ef4444;">✗ Mismatch</span>'
        )
    size_verification_badge.short_description = 'Size Match'
    
    def image_preview(self, obj):
        """Display satellite image preview"""
        if obj.image_url:
            return format_html(
                '<img src="{}" style="max-width: 400px; border-radius: 8px;" />',
                obj.image_url,
            )
        return 'No image available'
    image_preview.short_description = 'Satellite Image'
    
    def detailed_metrics(self, obj):
        """
        Display detailed metrics in a formatted box.
        
        All dynamic values are passed as arguments to format_html so that Django's
        auto-escaping protects against XSS — no f-string / .format() interpolation
        of user-controlled data into the HTML template.
        """
        # Build up a list of (label, value) rows; skip None values
        rows = []
        if obj.ndvi is not None:
            rows.append(('NDVI', f'{obj.ndvi:.3f}'))
        if obj.evi is not None:
            rows.append(('EVI', f'{obj.evi:.3f}'))
        if obj.savi is not None:
            rows.append(('SAVI', f'{obj.savi:.3f}'))
        if obj.ndwi is not None:
            rows.append(('NDWI', f'{obj.ndwi:.3f}'))
        if obj.msavi is not None:
            rows.append(('MSAVI', f'{obj.msavi:.3f}'))
        if obj.soil_moisture is not None:
            rows.append(('Soil Moisture', f'{obj.soil_moisture:.1f}%'))
        if obj.vh_backscatter is not None:
            rows.append(('VH Backscatter', f'{obj.vh_backscatter:.2f} dB'))
        if obj.vv_backscatter is not None:
            rows.append(('VV Backscatter', f'{obj.vv_backscatter:.2f} dB'))
        if obj.data_quality_score is not None:
            rows.append(('Data Quality Score', str(obj.data_quality_score)))
        rows.append(('Verified Size', f'{obj.verified_farm_size} acres'))
        rows.append(('Crop Stage', obj.crop_stage or 'Unknown'))
        rows.append(('Processing Status', obj.processing_status))
        
        # Build each <p> safely
        row_html_parts = []
        for label, value in rows:
            row_html_parts.append(
                format_html('<p><strong>{}</strong>: {}</p>', label, value)
            )
        
        # Join the pre-escaped parts — mark_safe is not needed because
        # format_html already returns a SafeString; concatenation preserves safety.
        inner_html = ''.join(row_html_parts)
        
        return format_html(
            '<div style="font-family: monospace; background: #f3f4f6; padding: 15px; border-radius: 8px;">{}</div>',
            inner_html,
        )
    detailed_metrics.short_description = 'Metrics Summary'
    
    actions = ['trigger_rescan', 'mark_as_verified', 'export_to_csv']
    
    def trigger_rescan(self, request, queryset):
        """Trigger rescan for selected farms"""
        from .tasks import process_satellite_scan
        
        count = 0
        for scan in queryset:
            process_satellite_scan.delay(scan.farm.id)
            count += 1
        
        self.message_user(request, f'{count} scan(s) queued for reprocessing.')
    trigger_rescan.short_description = 'Trigger rescan for selected farms'
    
    def mark_as_verified(self, request, queryset):
        """Mark selected scans as size-verified"""
        updated = queryset.update(matches_declared_size=True)
        self.message_user(request, f'{updated} scan(s) marked as verified.')
    mark_as_verified.short_description = 'Mark as size verified'
    
    def export_to_csv(self, request, queryset):
        """Export selected scans to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="satellite_scans.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Scan ID', 'Farm ID', 'Satellite Type', 'Acquisition Date',
            'NDVI', 'EVI', 'SAVI', 'NDWI', 'MSAVI',
            'Cloud Cover', 'Clear Pixel %',
            'VH Backscatter', 'VV Backscatter', 'VH/VV Ratio',
            'Soil Moisture', 'Crop Health', 'Crop Stage',
            'Verified Size', 'Matches Size', 'Size Diff %',
            'Data Quality Score', 'Processing Status',
        ])
        
        for scan in queryset:
            writer.writerow([
                scan.scan_id,
                scan.farm.farm_id,
                scan.satellite_type,
                scan.acquisition_date,
                scan.ndvi,
                scan.evi,
                scan.savi,
                scan.ndwi,
                scan.msavi,
                scan.cloud_cover_percentage,
                scan.clear_pixel_percentage,
                scan.vh_backscatter,
                scan.vv_backscatter,
                scan.vh_vv_ratio,
                scan.soil_moisture,
                scan.crop_health_status,
                scan.crop_stage,
                scan.verified_farm_size,
                scan.matches_declared_size,
                scan.size_difference_percentage,
                scan.data_quality_score,
                scan.processing_status,
            ])
        
        return response
    export_to_csv.short_description = 'Export to CSV'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('farm', 'farm__farmer')


@admin.register(NDVIHistory)
class NDVIHistoryAdmin(admin.ModelAdmin):
    """Admin interface for NDVI History"""
    
    list_display = [
        'farm_link',
        'date',
        'ndvi_display',
        'trend_indicator',
        'soil_moisture_display',
        'created_at',
    ]
    
    list_filter = [
        'date',
        'created_at',
    ]
    
    search_fields = [
        'farm__farm_id',
        'farm__farmer__pulse_id',
        'farm__farmer__full_name',
    ]
    
    readonly_fields = ['created_at']
    
    date_hierarchy = 'date'
    ordering = ['-date']
    
    def farm_link(self, obj):
        """Link to farm admin page"""
        from django.urls import reverse
        url = reverse('admin:farms_farm_change', args=[obj.farm.id])
        return format_html('<a href="{}">{}</a>', url, obj.farm.farm_id)
    farm_link.short_description = 'Farm'
    
    def ndvi_display(self, obj):
        """Display NDVI with color coding"""
        if obj.ndvi_value >= 0.75:
            color = '#10b981'
        elif obj.ndvi_value >= 0.60:
            color = '#84cc16'
        elif obj.ndvi_value >= 0.40:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{:.3f}</span>',
            color, obj.ndvi_value,
        )
    ndvi_display.short_description = 'NDVI Value'
    
    def trend_indicator(self, obj):
        """Show trend compared to previous reading"""
        previous = NDVIHistory.objects.filter(
            farm=obj.farm,
            date__lt=obj.date,
        ).order_by('-date').first()
        
        if not previous:
            return format_html('<span style="color: #9ca3af;">—</span>')
        
        diff = obj.ndvi_value - previous.ndvi_value
        
        if diff > 0.05:
            return format_html('<span style="color: #10b981;">↑ {:.3f}</span>', diff)
        elif diff < -0.05:
            return format_html('<span style="color: #ef4444;">↓ {:.3f}</span>', diff)
        else:
            return format_html('<span style="color: #f59e0b;">→ {:.3f}</span>', diff)
    trend_indicator.short_description = 'Trend'
    
    def soil_moisture_display(self, obj):
        """Display soil moisture if available"""
        if obj.soil_moisture is None:
            return format_html('<span style="color: #9ca3af;">—</span>')
        
        if obj.soil_moisture >= 60:
            color = '#10b981'
        elif obj.soil_moisture >= 40:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, obj.soil_moisture,
        )
    soil_moisture_display.short_description = 'Soil Moisture'
    
    def get_queryset(self, request):
        """Optimize queryset"""
        qs = super().get_queryset(request)
        return qs.select_related('farm', 'farm__farmer', 'satellite_scan')