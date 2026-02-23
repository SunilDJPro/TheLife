from django.contrib import admin
from .models import EntertainmentLog


@admin.register(EntertainmentLog)
class EntertainmentLogAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'entertainment_type', 'venue', 'date', 'rating')
    list_filter = ('entertainment_type', 'date')
    date_hierarchy = 'date'
