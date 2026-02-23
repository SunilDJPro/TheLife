"""Scoring and analytics views for TheLife."""
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.http import JsonResponse
from django.utils import timezone

from .models import DailyScore, WeeklyScore, MonthlyScore
from .engine import calculate_daily_score, run_llm_scrutinizer


@login_required
def scoring_dashboard(request):
    """Scoring analytics dashboard."""
    today = timezone.localdate()

    # Today's score
    today_score = DailyScore.objects.filter(user=request.user, date=today).first()

    # Last 7 days
    week_ago = today - timedelta(days=7)
    recent_scores = DailyScore.objects.filter(
        user=request.user, date__gte=week_ago, date__lte=today
    ).order_by('date')

    # This week's aggregate
    year, week, _ = today.isocalendar()
    weekly_score = WeeklyScore.objects.filter(
        user=request.user, year=year, week_number=week
    ).first()

    # This month's aggregate
    monthly_score = MonthlyScore.objects.filter(
        user=request.user, year=today.year, month=today.month
    ).first()

    # Score trend data for chart
    last_30 = DailyScore.objects.filter(
        user=request.user,
        date__gte=today - timedelta(days=30),
    ).order_by('date')

    chart_data = {
        'labels': [s.date.strftime('%m/%d') for s in last_30],
        'scores': [round(s.final_score, 1) for s in last_30],
        'base_scores': [round(s.base_score, 1) for s in last_30],
    }

    context = {
        'today_score': today_score,
        'recent_scores': recent_scores,
        'weekly_score': weekly_score,
        'monthly_score': monthly_score,
        'chart_data': chart_data,
    }
    return render(request, 'scoring/dashboard.html', context)


@login_required
def score_detail(request, date_str):
    """Detailed score breakdown for a specific date."""
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = timezone.localdate()

    score = DailyScore.objects.filter(user=request.user, date=date).first()

    context = {
        'score': score,
        'date': date,
    }
    if request.htmx:
        return render(request, 'scoring/partials/score_detail.html', context)
    return render(request, 'scoring/score_detail.html', context)


@login_required
def recalculate_score(request):
    """Manually trigger score recalculation for a date."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    date_str = request.POST.get('date', '')
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = timezone.localdate()

    score = calculate_daily_score(request.user, date)

    # Trigger LLM scrutinizer asynchronously
    from .tasks import calculate_score_for_user
    try:
        calculate_score_for_user.delay(str(request.user.id), date.strftime('%Y-%m-%d'))
    except Exception:
        # If Celery isn't running, do it synchronously
        run_llm_scrutinizer(request.user, date)
        score.refresh_from_db()

    if request.htmx:
        return render(request, 'scoring/partials/score_card.html', {'score': score})
    return JsonResponse({
        'base_score': score.base_score,
        'final_score': score.final_score,
        'llm_feedback': score.llm_feedback,
    })


@login_required
def score_history(request):
    """Score history with weekly and monthly views."""
    view_type = request.GET.get('view', 'daily')

    if view_type == 'weekly':
        scores = WeeklyScore.objects.filter(user=request.user)[:20]
        template = 'scoring/partials/weekly_history.html'
    elif view_type == 'monthly':
        scores = MonthlyScore.objects.filter(user=request.user)[:12]
        template = 'scoring/partials/monthly_history.html'
    else:
        scores = DailyScore.objects.filter(user=request.user)[:30]
        template = 'scoring/partials/daily_history.html'

    context = {'scores': scores, 'view_type': view_type}
    if request.htmx:
        return render(request, template, context)
    return render(request, 'scoring/history.html', context)


@login_required
def score_chart_data(request):
    """API endpoint for score chart data."""
    days = int(request.GET.get('days', 30))
    today = timezone.localdate()
    scores = DailyScore.objects.filter(
        user=request.user,
        date__gte=today - timedelta(days=days),
    ).order_by('date')

    return JsonResponse({
        'labels': [s.date.strftime('%Y-%m-%d') for s in scores],
        'final_scores': [round(s.final_score, 1) for s in scores],
        'base_scores': [round(s.base_score, 1) for s in scores],
        'work_scores': [round(s.work_score, 1) for s in scores],
        'skill_scores': [round(s.skill_score, 1) for s in scores],
        'fitness_scores': [round(s.fitness_score, 1) for s in scores],
    })
