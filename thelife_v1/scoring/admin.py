from django.contrib import admin
from .models import DailyScore, WeeklyScore, MonthlyScore


@admin.register(DailyScore)
class DailyScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'base_score', 'llm_adjustment', 'final_score',
                    'total_logged_hours', 'logging_coverage', 'llm_processed')
    list_filter = ('llm_processed', 'date')
    date_hierarchy = 'date'
    readonly_fields = ('work_score', 'skill_score', 'fitness_score',
                       'personal_score', 'consistency_score')


@admin.register(WeeklyScore)
class WeeklyScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'week_number', 'avg_score', 'days_logged')


@admin.register(MonthlyScore)
class MonthlyScoreAdmin(admin.ModelAdmin):
    list_display = ('user', 'year', 'month', 'avg_score', 'days_logged')
