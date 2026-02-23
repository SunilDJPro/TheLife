from django.contrib import admin
from .models import WorkProfile, Project, Deliverable, WorkLog


@admin.register(WorkProfile)
class WorkProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'current_role', 'organization')


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'status', 'priority', 'target_date')
    list_filter = ('status', 'priority')


@admin.register(Deliverable)
class DeliverableAdmin(admin.ModelAdmin):
    list_display = ('title', 'project', 'status', 'due_date')
    list_filter = ('status',)


@admin.register(WorkLog)
class WorkLogAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'project', 'date', 'hours_spent', 'status_tag')
    list_filter = ('date',)
    date_hierarchy = 'date'
