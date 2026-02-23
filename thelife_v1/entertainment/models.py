"""Entertainment logging models for TheLife."""
import uuid
from django.db import models
from django.conf import settings


class EntertainmentLog(models.Model):
    """Simple entertainment log — movies, gaming, series."""
    TYPE_CHOICES = [
        ('movie', 'Movie'),
        ('series', 'Series / Short Film'),
        ('gaming', 'Gaming'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                              related_name='entertainment_logs')
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True)
    entertainment_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    venue = models.CharField(max_length=200, blank=True,
                              help_text="e.g., HT-Screen 1 Dolby Atmos, Lab, Home")
    date = models.DateField(db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    rating = models.PositiveSmallIntegerField(
        null=True, blank=True,
        choices=[(i, str(i)) for i in range(1, 11)],
        help_text="Personal rating 1-10")
    is_scheduled = models.BooleanField(default=False,
                                        help_text="Pre-scheduled vs logged after")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'thelife_entertainment_logs'
        ordering = ['-date', '-created_at']
        indexes = [
            models.Index(fields=['user', 'date']),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_entertainment_type_display()})"
