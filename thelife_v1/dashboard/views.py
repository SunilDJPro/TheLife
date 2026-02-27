"""Dashboard views for TheLife — main home page with calendar."""
import calendar
from datetime import datetime, timedelta, date as date_cls
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone
from django.conf import settings

from activities.models import ActivityLog, ActivityCategory
from activities.forms import QuickLogForm
from scoring.models import DailyScore
from skills.models import Skill


def _backfill_unscored_days(user):
    """
    On first load of the day, score any past days that have activity logs
    but no DailyScore. Covers server-off gaps.
    Only looks back 7 days to stay fast.
    """
    today = timezone.localdate()
    for i in range(1, 8):
        day = today - timedelta(days=i)
        has_logs = ActivityLog.objects.filter(user=user, date=day).exists()
        has_score = DailyScore.objects.filter(user=user, date=day).exists()
        if has_logs and not has_score:
            try:
                from scoring.engine import calculate_daily_score
                calculate_daily_score(user, day)
            except Exception:
                pass


@login_required
def home(request):
    """Main dashboard with calendar view and catch-up prompts."""
    today = timezone.localdate()
    now = timezone.localtime()

    # Backfill unscored past days (runs once, fast check)
    _backfill_unscored_days(request.user)

    # View mode: day, week, month
    view_mode = request.GET.get('view', 'day')
    date_str = request.GET.get('date')

    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today
    else:
        selected_date = today

    # Today's logs
    today_logs = ActivityLog.objects.filter(
        user=request.user, date=today
    ).select_related('category', 'activity_type').order_by('start_time')

    # Unfilled blocks for catch-up prompt
    unfilled_blocks = _get_unfilled_blocks_for_dashboard(request.user, today, today_logs)

    # Today's score — compute if activities exist but no score yet
    today_score = DailyScore.objects.filter(user=request.user, date=today).first()
    if not today_score and today_logs.exists():
        try:
            from scoring.engine import calculate_daily_score, aggregate_weekly_score, aggregate_monthly_score
            today_score = calculate_daily_score(request.user, today)
            year, week, _ = today.isocalendar()
            aggregate_weekly_score(request.user, year, week)
            aggregate_monthly_score(request.user, today.year, today.month)
        except Exception:
            pass

    # Active skills
    active_skills = Skill.objects.filter(user=request.user, status='active')

    # Calendar data
    if view_mode == 'month':
        cal_data = _get_month_calendar(request.user, selected_date)
    elif view_mode == 'week':
        cal_data = _get_week_calendar(request.user, selected_date)
    else:
        cal_data = _get_day_calendar(request.user, selected_date)

    # Navigation dates
    if view_mode == 'month':
        prev_date = (selected_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        next_month = selected_date.replace(day=28) + timedelta(days=4)
        next_date = next_month.replace(day=1)
    elif view_mode == 'week':
        prev_date = selected_date - timedelta(weeks=1)
        next_date = selected_date + timedelta(weeks=1)
    else:
        prev_date = selected_date - timedelta(days=1)
        next_date = selected_date + timedelta(days=1)

    context = {
        'today': today,
        'now': now,
        'selected_date': selected_date,
        'view_mode': view_mode,
        'today_logs': today_logs,
        'unfilled_blocks': unfilled_blocks,
        'today_score': today_score,
        'active_skills': active_skills,
        'cal_data': cal_data,
        'prev_date': prev_date.strftime('%Y-%m-%d'),
        'next_date': next_date.strftime('%Y-%m-%d'),
        'quick_form': QuickLogForm(),
        'show_catchup': len(unfilled_blocks) > 0,
        'categories': ActivityCategory.objects.filter(is_active=True),
    }

    if request.htmx:
        if request.GET.get('partial') == 'calendar':
            return render(request, 'dashboard/partials/calendar.html', context)
        return render(request, 'dashboard/partials/main_content.html', context)

    return render(request, 'dashboard/home.html', context)


def _get_unfilled_blocks_for_dashboard(user, date, existing_logs):
    """Get unfilled time blocks for dashboard catch-up prompt."""
    now = timezone.localtime()
    wake = datetime.combine(date, user.wake_time)
    sleep = datetime.combine(date, user.sleep_time)
    interval = user.log_interval_hours

    blocks = []
    current = wake
    while current < sleep:
        block_end = current + timedelta(hours=interval)
        if block_end > sleep:
            block_end = sleep
        # Only past blocks
        if block_end <= datetime.combine(date, now.time()):
            has_log = False
            for log in existing_logs:
                if log.start_time < block_end.time() and log.end_time > current.time():
                    has_log = True
                    break
            if not has_log:
                blocks.append({
                    'start_time': current.time(),
                    'end_time': block_end.time(),
                    'start_str': current.strftime('%H:%M'),
                    'end_str': block_end.strftime('%H:%M'),
                })
        current = block_end

    return blocks


def _get_day_calendar(user, date):
    """Get hourly slots for day view."""
    logs = ActivityLog.objects.filter(
        user=user, date=date
    ).select_related('category', 'activity_type').order_by('start_time')

    # Build hour-by-hour grid
    hours = []
    for hour in range(24):
        slot_logs = [l for l in logs if l.start_time.hour <= hour < (
            l.end_time.hour if l.end_time > l.start_time else 24)]
        hours.append({
            'hour': hour,
            'label': f"{hour:02d}:00",
            'logs': slot_logs,
            'has_logs': len(slot_logs) > 0,
        })

    score = DailyScore.objects.filter(user=user, date=date).first()

    return {
        'type': 'day',
        'date': date,
        'hours': hours,
        'logs': logs,
        'score': score,
    }


def _get_week_calendar(user, date):
    """Get week view data."""
    # Find Monday of the week
    monday = date - timedelta(days=date.weekday())
    days = []

    for i in range(7):
        day = monday + timedelta(days=i)
        logs = ActivityLog.objects.filter(
            user=user, date=day
        ).select_related('category').order_by('start_time')
        score = DailyScore.objects.filter(user=user, date=day).first()

        days.append({
            'date': day,
            'day_name': day.strftime('%a'),
            'day_number': day.day,
            'logs': logs,
            'log_count': logs.count(),
            'score': score,
            'is_today': day == timezone.localdate(),
        })

    return {
        'type': 'week',
        'start_date': monday,
        'end_date': monday + timedelta(days=6),
        'days': days,
    }


def _get_month_calendar(user, date):
    """Get month view data with score indicators."""
    year = date.year
    month = date.month
    cal = calendar.monthcalendar(year, month)

    # Get all scores for the month
    scores = {s.date: s for s in DailyScore.objects.filter(
        user=user, date__year=year, date__month=month)}

    # Get log counts per day
    from django.db.models import Count
    log_counts = dict(
        ActivityLog.objects.filter(
            user=user, date__year=year, date__month=month
        ).values('date').annotate(count=Count('id')).values_list('date', 'count')
    )

    weeks = []
    for week in cal:
        days = []
        for day_num in week:
            if day_num == 0:
                days.append({'day': 0, 'empty': True})
            else:
                day = date_cls(year, month, day_num)
                score = scores.get(day)
                days.append({
                    'day': day_num,
                    'date': day,
                    'empty': False,
                    'score': score,
                    'score_value': score.final_score if score else None,
                    'log_count': log_counts.get(day, 0),
                    'is_today': day == timezone.localdate(),
                    'is_future': day > timezone.localdate(),
                })
        weeks.append(days)

    return {
        'type': 'month',
        'year': year,
        'month': month,
        'month_name': calendar.month_name[month],
        'weeks': weeks,
        'weekdays': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    }
