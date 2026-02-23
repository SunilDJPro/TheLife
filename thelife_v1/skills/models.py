"""
Skill management models for TheLife.
Enforces max 2 active skills at a time (hard block).
Tracks books (pages) and courses (sections/timeline).
"""
import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError


class Skill(models.Model):
    """A skill the user wants to learn or is learning."""
    STATUS_CHOICES = [
        ('queued', 'Queued'),
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('completed', 'Completed'),
        ('dropped', 'Dropped'),
    ]
    PRIORITY_CHOICES = [
        (1, 'Low'), (2, 'Medium'), (3, 'High'), (4, 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='skills')
    name = models.CharField(max_length=200, help_text="e.g., Computer Architecture, Machine Learning")
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='queued')
    priority = models.PositiveSmallIntegerField(choices=PRIORITY_CHOICES, default=2)
    target_completion_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_skills'
        ordering = ['-priority', 'created_at']

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    def clean(self):
        """Enforce hard block: max 2 active skills."""
        if self.status == 'active':
            active_count = Skill.objects.filter(
                user=self.user, status='active'
            ).exclude(pk=self.pk).count()
            max_active = self.user.max_active_skills
            if active_count >= max_active:
                raise ValidationError(
                    f"You can only have {max_active} active skills at a time. "
                    f"Complete or pause an existing skill before activating a new one."
                )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    @property
    def progress_percent(self):
        """Calculate overall progress across all resources."""
        resources = self.resources.all()
        if not resources:
            return 0
        total = sum(r.progress_percent for r in resources)
        return round(total / len(resources))


class SkillResource(models.Model):
    """A learning resource for a skill (book, course, etc.)."""
    RESOURCE_TYPES = [
        ('book', 'Book'),
        ('course_coursera', 'Online Course (Coursera)'),
        ('course_udemy', 'Online Course (Udemy)'),
        ('course_youtube', 'Online Course (YouTube)'),
        ('tutorial', 'Tutorial / Blog'),
        ('practice', 'Practice / Hands-on'),
        ('podcast', 'Podcast / Audio'),
        ('paper', 'Research Paper'),
        ('other', 'Other'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE, related_name='resources')
    resource_type = models.CharField(max_length=30, choices=RESOURCE_TYPES)
    title = models.CharField(max_length=300)
    url = models.URLField(blank=True, help_text="Link to course/resource")
    author = models.CharField(max_length=200, blank=True)

    # Book-specific
    total_pages = models.PositiveIntegerField(null=True, blank=True)
    current_page = models.PositiveIntegerField(default=0)

    # Course-specific
    total_sections = models.PositiveIntegerField(null=True, blank=True)
    completed_sections = models.PositiveIntegerField(default=0)
    total_duration_hours = models.DecimalField(max_digits=6, decimal_places=2,
                                                null=True, blank=True)

    is_completed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thelife_skill_resources'
        ordering = ['created_at']

    def __str__(self):
        return f"{self.title} ({self.get_resource_type_display()})"

    @property
    def progress_percent(self):
        if self.resource_type == 'book' and self.total_pages:
            return round((self.current_page / self.total_pages) * 100)
        elif self.total_sections:
            return round((self.completed_sections / self.total_sections) * 100)
        return 100 if self.is_completed else 0


class SkillSession(models.Model):
    """A study/practice session for a skill resource."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resource = models.ForeignKey(SkillResource, on_delete=models.CASCADE,
                                  related_name='sessions')
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()

    # Book progress
    start_page = models.PositiveIntegerField(null=True, blank=True)
    end_page = models.PositiveIntegerField(null=True, blank=True)

    # Course progress
    sections_covered = models.CharField(max_length=500, blank=True,
                                         help_text="Sections/chapters covered in this session")
    sections_count = models.PositiveIntegerField(default=0)

    # Timeline reference for video courses
    video_timestamp_start = models.CharField(max_length=20, blank=True,
                                              help_text="e.g., 1:23:45")
    video_timestamp_end = models.CharField(max_length=20, blank=True)

    notes = models.TextField(blank=True, help_text="Session notes, key learnings")
    rating = models.PositiveSmallIntegerField(
        default=3, choices=[(1, 'Poor'), (2, 'Below Avg'), (3, 'Average'),
                            (4, 'Good'), (5, 'Excellent')],
        help_text="Self-assessed session quality")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'thelife_skill_sessions'
        ordering = ['-date', '-start_time']

    def __str__(self):
        return f"{self.resource.title} session on {self.date}"

    @property
    def pages_read(self):
        if self.start_page and self.end_page:
            return self.end_page - self.start_page
        return 0

    @property
    def pages_per_hour(self):
        if self.pages_read and self.duration_minutes:
            return round(self.pages_read / (self.duration_minutes / 60), 1)
        return 0

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

        # Update resource progress
        if self.end_page and self.resource.resource_type == 'book':
            self.resource.current_page = max(self.resource.current_page, self.end_page)
            self.resource.save(update_fields=['current_page', 'updated_at'])
        if self.sections_count:
            self.resource.completed_sections = min(
                self.resource.completed_sections + self.sections_count,
                self.resource.total_sections or 999
            )
            self.resource.save(update_fields=['completed_sections', 'updated_at'])
