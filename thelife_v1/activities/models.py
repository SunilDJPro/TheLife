"""
Activity logging models for TheLife.
Covers all daily activity categories with structured + free-form logging.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone


class ActivityCategory(models.Model):
    """
    Master list of activity categories.
    Seeded via migration, extensible by admin.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    icon = models.CharField(max_length=50, default='circle',
                            help_text="Lucide icon name")
    color = models.CharField(max_length=7, default='#00BCD4',
                             help_text="Hex color for UI")
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'thelife_activity_categories'
        ordering = ['sort_order', 'name']
        verbose_name_plural = 'Activity Categories'

    def __str__(self):
        return self.name


class ActivityType(models.Model):
    """
    Subtypes within each category.
    e.g., Category: Fitness → Types: Gym, Running, Yoga, Swimming
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.ForeignKey(ActivityCategory, on_delete=models.CASCADE,
                                  related_name='types')
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'thelife_activity_types'
        ordering = ['category__sort_order', 'name']
        unique_together = ['category', 'name']

    def __str__(self):
        return f"{self.category.name} → {self.name}"


class ActivityLog(models.Model):
    """
    Core activity log entry — one per time block.
    Every 1-2 hours, the user logs what they did.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='activity_logs')
    category = models.ForeignKey(ActivityCategory, on_delete=models.PROTECT,
                                  related_name='logs')
    activity_type = models.ForeignKey(ActivityType, on_delete=models.SET_NULL,
                                       null=True, blank=True, related_name='logs')

    # Time block
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField(
        help_text="Auto-calculated or manually entered duration in minutes")

    # Core fields
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default='')
    notes = models.TextField(blank=True, default='',
                              help_text="Additional notes, reflections")

    # Structured metadata (JSON) — stores category-specific fields
    # e.g., for Fitness: {"intensity": "high", "calories": 300}
    # e.g., for Meals: {"meal_type": "lunch", "home_cooked": true}
    metadata = models.JSONField(default=dict, blank=True)

    # Self-assessment
    PRODUCTIVITY_CHOICES = [
        (1, 'Very Low'), (2, 'Low'), (3, 'Medium'), (4, 'High'), (5, 'Very High'),
    ]
    productivity_rating = models.PositiveSmallIntegerField(
        choices=PRODUCTIVITY_CHOICES, default=3)

    # Scoring
    base_score = models.FloatField(default=0, help_text="Formula-based score for this log")
    llm_adjustment = models.FloatField(default=0, help_text="LLM adjustment (-30 to +30)")
    llm_feedback = models.TextField(blank=True, default='',
                                     help_text="LLM scrutinizer feedback")

    # Status
    is_recurring = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_activity_logs'
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['user', 'category', 'date']),
        ]

    def __str__(self):
        return f"{self.title} ({self.date} {self.start_time})"

    @property
    def final_score(self):
        return max(0, min(100, self.base_score + self.llm_adjustment))

    def save(self, *args, **kwargs):
        # Auto-calculate duration
        if self.start_time and self.end_time:
            from datetime import datetime, timedelta
            start = datetime.combine(self.date, self.start_time)
            end = datetime.combine(self.date, self.end_time)
            if end < start:
                end += timedelta(days=1)
            self.duration_minutes = int((end - start).total_seconds() / 60)
        super().save(*args, **kwargs)


class RecurringTask(models.Model):
    """Recurring tasks/activities that auto-populate the calendar."""
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekdays', 'Weekdays (Mon-Fri)'),
        ('weekends', 'Weekends (Sat-Sun)'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-weekly'),
        ('monthly', 'Monthly'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='recurring_tasks')
    category = models.ForeignKey(ActivityCategory, on_delete=models.PROTECT)
    activity_type = models.ForeignKey(ActivityType, on_delete=models.SET_NULL,
                                       null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    day_of_week = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="0=Monday, 6=Sunday (for weekly)")
    day_of_month = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="1-31 (for monthly)")
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'thelife_recurring_tasks'
        ordering = ['start_time']

    def __str__(self):
        return f"{self.title} ({self.get_frequency_display()})"
