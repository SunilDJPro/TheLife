"""
Scoring models for TheLife.
Daily scores out of 100 with LLM adjustment of ±30%.
Cumulative weekly, monthly, yearly aggregations.
"""
import uuid
from django.db import models
from django.conf import settings


class DailyScore(models.Model):
    """Daily score for a user — the core accountability metric."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='daily_scores')
    date = models.DateField(db_index=True)

    # Component scores (each out of 100, weighted to final)
    work_score = models.FloatField(default=0, help_text="Work efficiency score")
    skill_score = models.FloatField(default=0, help_text="Skill learning score")
    fitness_score = models.FloatField(default=0, help_text="Fitness/health score")
    personal_score = models.FloatField(default=0, help_text="Personal time management score")
    consistency_score = models.FloatField(default=0, help_text="Logging consistency score")

    # Final scores
    base_score = models.FloatField(default=0, help_text="Weighted formula score out of 100")
    llm_adjustment = models.FloatField(default=0, help_text="LLM adjustment (-30 to +30)")
    final_score = models.FloatField(default=0, help_text="Final score after LLM adjustment")

    # LLM feedback
    llm_feedback = models.TextField(blank=True, default='',
                                     help_text="LLM scrutinizer feedback for the day")
    llm_processed = models.BooleanField(default=False)

    # Stats
    total_logged_hours = models.FloatField(default=0)
    total_activities = models.PositiveIntegerField(default=0)
    logging_coverage = models.FloatField(default=0,
                                          help_text="% of waking hours logged")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_daily_scores'
        unique_together = ['user', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} — {self.date}: {self.final_score:.1f}/100"


class WeeklyScore(models.Model):
    """Aggregated weekly score."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='weekly_scores')
    year = models.PositiveIntegerField()
    week_number = models.PositiveSmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()

    avg_score = models.FloatField(default=0)
    best_day_score = models.FloatField(default=0)
    worst_day_score = models.FloatField(default=0)
    total_logged_hours = models.FloatField(default=0)
    days_logged = models.PositiveSmallIntegerField(default=0)

    # Category breakdowns
    avg_work_score = models.FloatField(default=0)
    avg_skill_score = models.FloatField(default=0)
    avg_fitness_score = models.FloatField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_weekly_scores'
        unique_together = ['user', 'year', 'week_number']
        ordering = ['-year', '-week_number']

    def __str__(self):
        return f"{self.user} — W{self.week_number}/{self.year}: {self.avg_score:.1f}"


class MonthlyScore(models.Model):
    """Aggregated monthly score."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='monthly_scores')
    year = models.PositiveIntegerField()
    month = models.PositiveSmallIntegerField()

    avg_score = models.FloatField(default=0)
    best_day_score = models.FloatField(default=0)
    worst_day_score = models.FloatField(default=0)
    total_logged_hours = models.FloatField(default=0)
    days_logged = models.PositiveSmallIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_monthly_scores'
        unique_together = ['user', 'year', 'month']
        ordering = ['-year', '-month']

    def __str__(self):
        return f"{self.user} — {self.month}/{self.year}: {self.avg_score:.1f}"
