
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from django.conf import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    # Authentication
    path('api/v1/auth/', include('apps.accounts.urls')),
    path('api/v1/satellite/', include('apps.satellite.urls')),
    path('api/v1/farmers/', include('apps.farmers.urls')),
    path('api/v1/farms/', include('apps.farms.urls')),
    path('api/v1/climate/', include('apps.climate.urls')),
    # path('api/v1/admin/', include('apps.admin_portal.urls')),  # Temporarily disabled
    path('api/v1/compliance/', include('apps.compliance.urls')),
]


# serve media files during development

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)