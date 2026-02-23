"""
Custom User model for TheLife.
Multi-tenant ready with privacy-focused design.
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended user model with TheLife-specific fields."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True,
                                  help_text="Tenant identifier for future multi-tenancy")

    # Profile
    display_name = models.CharField(max_length=100, blank=True)
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    wake_time = models.TimeField(default='06:00', help_text="Typical wake-up time")
    sleep_time = models.TimeField(default='23:00', help_text="Typical bedtime")

    # Push notification subscription (JSON)
    push_subscription = models.JSONField(null=True, blank=True,
                                          help_text="Web push subscription info")

    # Long-term goals (used by LLM scrutinizer for alignment scoring)
    long_term_goals = models.TextField(blank=True, default='',
                                        help_text="User's long-term goals for LLM alignment scoring")

    # Preferences
    log_interval_hours = models.PositiveSmallIntegerField(
        default=2, help_text="Hours between log prompts")
    max_active_skills = models.PositiveSmallIntegerField(
        default=2, help_text="Maximum concurrent active skills")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_users'

    def __str__(self):
        return self.display_name or self.username


class UserGoal(models.Model):
    """Individual long-term goals for structured tracking."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='goals')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    target_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'thelife_user_goals'
        ordering = ['-created_at']

    def __str__(self):
        return self.title
