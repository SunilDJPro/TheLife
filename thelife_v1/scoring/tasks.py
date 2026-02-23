"""Celery tasks for scoring calculations."""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def calculate_all_daily_scores():
    """Calculate daily scores for all users (run at end of day)."""
    from accounts.models import User
    from .engine import calculate_daily_score

    today = timezone.localdate()
    users = User.objects.filter(is_active=True)

    for user in users:
        try:
            calculate_daily_score(user, today)
            logger.info(f"Calculated daily score for {user} on {today}")
        except Exception as e:
            logger.error(f"Error scoring {user}: {e}")


@shared_task
def run_all_llm_scrutinizers():
    """Run LLM scrutinizer for all users (run after daily scores)."""
    from accounts.models import User
    from .engine import run_llm_scrutinizer

    today = timezone.localdate()
    users = User.objects.filter(is_active=True)

    for user in users:
        try:
            run_llm_scrutinizer(user, today)
            logger.info(f"LLM scrutinizer completed for {user} on {today}")
        except Exception as e:
            logger.error(f"LLM scrutinizer error for {user}: {e}")


@shared_task
def aggregate_weekly_scores():
    """Aggregate weekly scores (run on Mondays)."""
    from accounts.models import User
    from .engine import aggregate_weekly_score

    today = timezone.localdate()
    # Get last week's number
    last_week = today - timedelta(weeks=1)
    year = last_week.isocalendar()[0]
    week = last_week.isocalendar()[1]

    users = User.objects.filter(is_active=True)
    for user in users:
        try:
            aggregate_weekly_score(user, year, week)
        except Exception as e:
            logger.error(f"Weekly aggregation error for {user}: {e}")


@shared_task
def aggregate_monthly_scores():
    """Aggregate monthly scores (run on 1st of each month)."""
    from accounts.models import User
    from .engine import aggregate_monthly_score

    today = timezone.localdate()
    # Get last month
    first_of_month = today.replace(day=1)
    last_month = first_of_month - timedelta(days=1)

    users = User.objects.filter(is_active=True)
    for user in users:
        try:
            aggregate_monthly_score(user, last_month.year, last_month.month)
        except Exception as e:
            logger.error(f"Monthly aggregation error for {user}: {e}")


@shared_task
def calculate_score_for_user(user_id, date_str):
    """Calculate score for a specific user and date."""
    from accounts.models import User
    from .engine import calculate_daily_score, run_llm_scrutinizer
    from datetime import datetime

    user = User.objects.get(id=user_id)
    date = datetime.strptime(date_str, '%Y-%m-%d').date()

    score = calculate_daily_score(user, date)
    run_llm_scrutinizer(user, date)

    return str(score.final_score)
