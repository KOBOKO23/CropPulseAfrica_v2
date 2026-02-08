"""
Scoring App Django Admin
"""

from django.contrib import admin
from django.utils.html import format_html
from apps.scoring.models import (
    PulseScore, ScoreHistory, ScoreRecalculationLog,
    ScoreOverride, FraudAlert
)


@admin.register(PulseScore)
class PulseScoreAdmin(admin.ModelAdmin):
    list_display = [
        'farmer_name', 'score', 'grade', 'confidence_level',
        'is_current', 'is_frozen', 'valid_until', 'created_at'
    ]
    list_filter = ['is_current', 'is_frozen', 'created_at']
    search_fields = ['farmer__full_name', 'farmer__pulse_id']
    readonly_fields = [
        'score', 'confidence_level', 'grade', 'risk_category',
        'is_valid', 'days_until_expiry', 'created_at', 'updated_at'
    ]
    
    def farmer_name(self, obj):
        return obj.farmer.full_name
    farmer_name.short_description = 'Farmer'


@admin.register(ScoreHistory)
class ScoreHistoryAdmin(admin.ModelAdmin):
    list_display = ['farmer_name', 'date', 'score', 'change_badge']
    list_filter = ['date']
    search_fields = ['farmer__full_name']
    
    # Make all fields read-only
    readonly_fields = [f.name for f in ScoreHistory._meta.get_fields()]

    def farmer_name(self, obj):
        return obj.farmer.full_name
    
    def change_badge(self, obj):
        if obj.change_from_previous > 0:
            color = 'green'
            arrow = '↑'
        elif obj.change_from_previous < 0:
            color = 'red'
            arrow = '↓'
        else:
            color = 'gray'
            arrow = '→'
        return format_html(
            '<span style="color: {};">{} {}</span>',
            color, arrow, abs(obj.change_from_previous)
        )
    change_badge.short_description = 'Change'


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    list_display = [
        'farmer_name', 'alert_type', 'severity_badge',
        'status_badge', 'blocks_lending', 'created_at'
    ]
    list_filter = ['severity', 'status', 'blocks_lending', 'created_at']
    search_fields = ['farmer__full_name', 'description']
    
    def farmer_name(self, obj):
        return obj.farmer.full_name
    
    def severity_badge(self, obj):
        colors = {
            'critical': 'red',
            'high': 'darkorange',
            'medium': 'orange',
            'low': 'yellow'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.severity, 'gray'),
            obj.get_severity_display()
        )
    
    def status_badge(self, obj):
        colors = {
            'pending': 'orange',
            'investigating': 'blue',
            'confirmed': 'red',
            'false_positive': 'green',
            'resolved': 'darkgreen'
        }
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 8px; border-radius: 3px;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.get_status_display()
        )