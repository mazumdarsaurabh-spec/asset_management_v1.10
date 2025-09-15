# inventory_management/urls.py

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

# Import your dashboard view with its correct name
from inventory.views import dashboard_view # <--- CHANGED from 'dashboard' to 'dashboard_view'

urlpatterns = [
    path('admin/', admin.site.urls),

    # Map the root URL (http://127.0.0.1:8000/) to your dashboard_view.
    path('', dashboard_view, name='dashboard'), # <--- USED 'dashboard_view' here

    # Add a trailing slash here so all URLs in inventory.urls are correctly prefixed.
    path('inventory/', include('inventory.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)