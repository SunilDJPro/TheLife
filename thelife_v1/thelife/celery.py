"""
Celery configuration for TheLife project.
Used for background tasks: scoring, LLM scrutinizer, notifications.
"""
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'thelife.settings')

app = Celery('thelife')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
