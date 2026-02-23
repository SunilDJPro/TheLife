from django.contrib import admin
from .models import Skill, SkillResource, SkillSession


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'priority', 'created_at')
    list_filter = ('status', 'priority')


@admin.register(SkillResource)
class SkillResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'skill', 'resource_type', 'is_completed')
    list_filter = ('resource_type', 'is_completed')


@admin.register(SkillSession)
class SkillSessionAdmin(admin.ModelAdmin):
    list_display = ('resource', 'date', 'duration_minutes', 'rating')
    date_hierarchy = 'date'
