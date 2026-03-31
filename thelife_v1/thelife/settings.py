"""
TheLife - Django Settings
Make people live their lives and get the best out of it.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third party
    'django_htmx',
    'django_extensions',
    'widget_tweaks',
    'django_celery_beat',
    # TheLife apps
    'accounts.apps.AccountsConfig',
    'dashboard.apps.DashboardConfig',
    'activities.apps.ActivitiesConfig',
    'work.apps.WorkConfig',
    'skills.apps.SkillsConfig',
    'entertainment.apps.EntertainmentConfig',
    'scoring.apps.ScoringConfig',
    'compute_mastery.apps.ComputeMasteryConfig',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'accounts.middleware.TimezoneMiddleware',
]

ROOT_URLCONF = 'thelife.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'dashboard.context_processors.sidebar_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'thelife.wsgi.application'

# Database - PostgreSQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'thelife_db'),
        'USER': os.getenv('DB_USER', 'thelife_user'),
        'PASSWORD': os.getenv('DB_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'OPTIONS': {
            'connect_timeout': 5,
        },
    }
}

# Auth
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery (for background scoring, notifications)
CELERY_BROKER_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Ollama / LiteLLM
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
LLM_MODEL = os.getenv('LLM_MODEL', 'ollama/gemma3:12b')
COMPUTE_LLM_MODEL = os.getenv('COMPUTE_LLM_MODEL', 'ollama/qwen2.5-coder:14b')

# VAPID keys for push notifications
VAPID_PUBLIC_KEY = os.getenv('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.getenv('VAPID_PRIVATE_KEY', '')
VAPID_ADMIN_EMAIL = os.getenv('VAPID_ADMIN_EMAIL', 'admin@thelife.local')

# Encryption key for sensitive user data
FIELD_ENCRYPTION_KEY = os.getenv('FIELD_ENCRYPTION_KEY', '')

# Scoring configuration
SCORING_CONFIG = {
    'MAX_DAILY_SCORE': 100,
    'LLM_ADJUSTMENT_MAX_PERCENT': 30,  # ±30%
    'WORK_WEIGHT': 0.30,
    'SKILL_WEIGHT': 0.25,
    'FITNESS_WEIGHT': 0.15,
    'PERSONAL_WEIGHT': 0.15,
    'CONSISTENCY_WEIGHT': 0.15,
}

# Activity logging
ACTIVITY_LOG_INTERVAL_HOURS = 2  # Prompt every 2 hours
ACTIVITY_LOG_DURATION_MINUTES = 5  # Expected logging time
