from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, UserGoal


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'display_name', 'is_active', 'created_at')
    list_filter = ('is_active', 'is_staff')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('TheLife Profile', {
            'fields': ('display_name', 'timezone', 'wake_time', 'sleep_time',
                      'log_interval_hours', 'max_active_skills', 'long_term_goals'),
        }),
        ('Multi-Tenancy', {
            'fields': ('tenant_id',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('tenant_id', 'created_at', 'updated_at')


@admin.register(UserGoal)
class UserGoalAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'target_date', 'is_active')
    list_filter = ('is_active',)
