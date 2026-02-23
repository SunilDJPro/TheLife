"""
Work management models for TheLife.
Journal/log style with project tracking (mirrors OpzViz manually).
"""
import uuid
from django.db import models
from django.conf import settings


class WorkProfile(models.Model):
    """User's work profile — current role, org, etc."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                 related_name='work_profile')
    current_role = models.CharField(max_length=200, blank=True)
    organization = models.CharField(max_length=200, blank=True)
    department = models.CharField(max_length=200, blank=True)
    work_start_time = models.TimeField(default='09:00')
    work_end_time = models.TimeField(default='18:00')
    responsibilities = models.TextField(blank=True,
                                         help_text="Key responsibilities in current role")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_work_profiles'

    def __str__(self):
        return f"{self.user} — {self.current_role}"


class Project(models.Model):
    """Work projects (mirrors OpzViz project entries)."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_hold', 'On Hold'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    PRIORITY_CHOICES = [
        ('low', 'Low'), ('medium', 'Medium'),
        ('high', 'High'), ('critical', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='projects')
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='medium')
    start_date = models.DateField(null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    tags = models.CharField(max_length=500, blank=True, help_text="Comma-separated tags")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_projects'
        ordering = ['-updated_at']

    def __str__(self):
        return self.name

    @property
    def tag_list(self):
        return [t.strip() for t in self.tags.split(',') if t.strip()]


class Deliverable(models.Model):
    """Deliverables within a project."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('review', 'In Review'),
        ('completed', 'Completed'),
        ('blocked', 'Blocked'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE,
                                 related_name='deliverables')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_deliverables'
        ordering = ['due_date', '-created_at']

    def __str__(self):
        return f"{self.project.name} → {self.title}"


class WorkLog(models.Model):
    """
    Daily work journal entries.
    Log style — chronological entries with status tags.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='work_logs')
    project = models.ForeignKey(Project, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='work_logs')
    deliverable = models.ForeignKey(Deliverable, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='work_logs')
    date = models.DateField(db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    hours_spent = models.DecimalField(max_digits=4, decimal_places=2, default=0)
    status_tag = models.CharField(max_length=50, blank=True,
                                   help_text="e.g., completed, in-progress, blocked, reviewed")
    blockers = models.TextField(blank=True, help_text="Any blockers or issues faced")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'thelife_work_logs'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]

    def __str__(self):
        return f"{self.date}: {self.title}"
