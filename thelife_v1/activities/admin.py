from django.contrib import admin
from .models import ActivityCategory, ActivityType, ActivityLog, RecurringTask


@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon', 'color', 'sort_order', 'is_active')
    list_editable = ('sort_order', 'is_active')
    ordering = ('sort_order',)


@admin.register(ActivityType)
class ActivityTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_active')
    list_filter = ('category', 'is_active')
    list_editable = ('is_active',)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'date', 'start_time', 'end_time',
                    'productivity_rating', 'base_score')
    list_filter = ('category', 'date', 'productivity_rating')
    search_fields = ('title', 'description')
    date_hierarchy = 'date'


@admin.register(RecurringTask)
class RecurringTaskAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'category', 'frequency', 'start_time', 'is_active')
    list_filter = ('frequency', 'is_active')
