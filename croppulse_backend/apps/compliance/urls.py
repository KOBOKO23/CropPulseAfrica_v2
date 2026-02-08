# compliance/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ExportPassportViewSet,
    DeforestationCheckViewSet,
    ComplianceDocumentViewSet,
    AuditLogViewSet
)

app_name = 'compliance'

router = DefaultRouter()
router.register(r'passports', ExportPassportViewSet, basename='passport')
router.register(r'deforestation-checks', DeforestationCheckViewSet, basename='deforestation-check')
router.register(r'documents', ComplianceDocumentViewSet, basename='document')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')

urlpatterns = [
    path('', include(router.urls)),
]