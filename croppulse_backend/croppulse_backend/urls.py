
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    # Authentication
    path('api/v1/auth/', include('apps.accounts.urls')),
]