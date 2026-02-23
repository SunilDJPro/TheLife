"""TheLife URL Configuration."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('', include('dashboard.urls', namespace='dashboard')),
    path('activities/', include('activities.urls', namespace='activities')),
    path('work/', include('work.urls', namespace='work')),
    path('skills/', include('skills.urls', namespace='skills')),
    path('entertainment/', include('entertainment.urls', namespace='entertainment')),
    path('scoring/', include('scoring.urls', namespace='scoring')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
