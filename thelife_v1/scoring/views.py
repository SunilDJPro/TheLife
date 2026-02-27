"""Scoring and analytics views for TheLife."""
import json
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import DailyScore, WeeklyScore, MonthlyScore
from .engine import calculate_daily_score, run_llm_scrutinizer, aggregate_weekly_score, aggregate_monthly_score


@login_required
def scoring_dashboard(request):
    """Scoring analytics dashboard."""
    today = timezone.localdate()

    today_score = DailyScore.objects.filter(user=request.user, date=today).first()

    # Auto-aggregate weekly/monthly from existing daily scores
    year, week, _ = today.isocalendar()
    try:
        aggregate_weekly_score(request.user, year, week)
        aggregate_monthly_score(request.user, today.year, today.month)
    except Exception:
        pass

    week_ago = today - timedelta(days=7)
    recent_scores = DailyScore.objects.filter(
        user=request.user, date__gte=week_ago, date__lte=today
    ).order_by('-date')

    weekly_score = WeeklyScore.objects.filter(
        user=request.user, year=year, week_number=week
    ).first()

    monthly_score = MonthlyScore.objects.filter(
        user=request.user, year=today.year, month=today.month
    ).first()

    last_30 = DailyScore.objects.filter(
        user=request.user,
        date__gte=today - timedelta(days=30),
    ).order_by('date')

    chart_data = json.dumps({
        'labels': [s.date.strftime('%m/%d') for s in last_30],
        'scores': [round(s.final_score, 1) for s in last_30],
        'base_scores': [round(s.base_score, 1) for s in last_30],
    })

    # Dates needing LLM scoring
    pending_llm = DailyScore.objects.filter(
        user=request.user,
        llm_processed=False,
        total_activities__gt=0,
        date__lt=today,
    ).order_by('-date')[:7]

    context = {
        'today_score': today_score,
        'recent_scores': recent_scores,
        'weekly_score': weekly_score,
        'monthly_score': monthly_score,
        'chart_data': chart_data,
        'pending_llm': pending_llm,
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
    context = {'score': score, 'date': date}
    if request.htmx:
        return render(request, 'scoring/partials/score_detail.html', context)
    return render(request, 'scoring/score_detail.html', context)


@login_required
@require_POST
def recalculate_score(request):
    """Manually trigger analytical score recalculation."""
    date_str = request.POST.get('date', '')
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = timezone.localdate()

    score = calculate_daily_score(request.user, date)
    year, week, _ = date.isocalendar()
    aggregate_weekly_score(request.user, year, week)
    aggregate_monthly_score(request.user, date.year, date.month)

    if request.htmx:
        return render(request, 'scoring/partials/score_card.html', {'score': score})
    return redirect('scoring:dashboard')


@login_required
@require_POST
def run_llm_scoring(request):
    """Manually trigger LLM scrutinizer for a specific date. Returns JSON."""
    date_str = request.POST.get('date', '')
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid date'}, status=400)

    score = DailyScore.objects.filter(user=request.user, date=date).first()
    if not score:
        score = calculate_daily_score(request.user, date)

    if score.total_activities == 0:
        return JsonResponse({
            'status': 'skipped',
            'message': f'No activities logged on {date}. Nothing to analyze.',
        })

    if score.llm_processed:
        return JsonResponse({
            'status': 'already_done',
            'message': 'AI scoring already completed for this date.',
            'adjustment': score.llm_adjustment,
            'feedback': score.llm_feedback,
            'final_score': score.final_score,
        })

    result = run_llm_scrutinizer(request.user, date)

    if result.llm_processed:
        return JsonResponse({
            'status': 'success',
            'message': 'AI scrutinizer completed.',
            'adjustment': result.llm_adjustment,
            'feedback': result.llm_feedback,
            'final_score': result.final_score,
            'base_score': result.base_score,
        })
    else:
        return JsonResponse({
            'status': 'error',
            'message': result.llm_feedback or 'LLM processing failed. Is Ollama running?',
        })


@login_required
@require_POST
def run_llm_batch(request):
    """Run LLM scrutinizer for all unscored past days (batch)."""
    today = timezone.localdate()
    pending = DailyScore.objects.filter(
        user=request.user,
        llm_processed=False,
        total_activities__gt=0,
        date__lt=today,
    ).order_by('date')[:7]

    results = []
    for score in pending:
        result = run_llm_scrutinizer(request.user, score.date)
        results.append({
            'date': score.date.strftime('%Y-%m-%d'),
            'status': 'success' if result.llm_processed else 'error',
            'adjustment': result.llm_adjustment if result.llm_processed else 0,
            'feedback': result.llm_feedback[:100] if result.llm_feedback else '',
        })

    return JsonResponse({
        'status': 'completed',
        'processed': len(results),
        'results': results,
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
