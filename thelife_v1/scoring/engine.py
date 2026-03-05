"""
Scoring engine for TheLife.
- Formula-based daily score out of 100.
- LLM scrutinizer adjusts by ±30%.
- Aggregates to weekly/monthly.
"""
import json
import logging
from datetime import datetime, timedelta
from django.conf import settings
from django.utils import timezone
from django.db.models import Sum, Count, Avg

from activities.models import ActivityLog, ActivityCategory
from skills.models import SkillSession
from work.models import WorkLog
from .models import DailyScore, WeeklyScore, MonthlyScore

logger = logging.getLogger(__name__)

SCORING_CONFIG = settings.SCORING_CONFIG


def calculate_daily_score(user, date):
    """
    Calculate the formula-based daily score for a user.
    Returns a DailyScore instance (saved).
    """
    score, created = DailyScore.objects.get_or_create(
        user=user, date=date,
    )

    logs = ActivityLog.objects.filter(user=user, date=date)
    if not logs.exists():
        score.final_score = 0
        score.save()
        return score

    # --- Component Calculations ---

    # 1. WORK SCORE (30% weight)
    work_logs = logs.filter(category__name='Work')
    work_score = _calculate_work_score(user, date, work_logs)

    # 2. SKILL LEARNING SCORE (25% weight)
    skill_sessions = SkillSession.objects.filter(
        resource__skill__user=user, date=date
    )
    skill_score = _calculate_skill_score(skill_sessions)

    # 3. FITNESS SCORE (15% weight)
    fitness_logs = logs.filter(category__name='Fitness')
    fitness_score = _calculate_fitness_score(fitness_logs)

    # 4. PERSONAL TIME MANAGEMENT (15% weight)
    personal_score = _calculate_personal_score(user, date, logs)

    # 5. CONSISTENCY SCORE (15% weight)
    consistency_score = _calculate_consistency_score(user, date, logs)

    # --- Weighted Final ---
    base_score = (
        work_score * SCORING_CONFIG['WORK_WEIGHT'] +
        skill_score * SCORING_CONFIG['SKILL_WEIGHT'] +
        fitness_score * SCORING_CONFIG['FITNESS_WEIGHT'] +
        personal_score * SCORING_CONFIG['PERSONAL_WEIGHT'] +
        consistency_score * SCORING_CONFIG['CONSISTENCY_WEIGHT']
    )
    base_score = min(100, max(0, base_score))

    # Stats
    total_minutes = logs.aggregate(total=Sum('duration_minutes'))['total'] or 0
    total_hours = total_minutes / 60

    # Logging coverage (% of waking hours logged)
    wake = datetime.combine(date, user.wake_time)
    sleep = datetime.combine(date, user.sleep_time)
    waking_hours = (sleep - wake).total_seconds() / 3600
    coverage = min(100, (total_hours / waking_hours) * 100) if waking_hours > 0 else 0

    # Save
    score.work_score = work_score
    score.skill_score = skill_score
    score.fitness_score = fitness_score
    score.personal_score = personal_score
    score.consistency_score = consistency_score
    score.base_score = base_score
    score.final_score = base_score  # LLM adjusts this later
    score.total_logged_hours = round(total_hours, 2)
    score.total_activities = logs.count()
    score.logging_coverage = round(coverage, 1)
    score.save()

    return score


def _calculate_work_score(user, date, work_logs):
    """Score based on hours worked, productivity ratings, and work log entries."""
    if not work_logs.exists():
        # Check if it's a weekend — no penalty
        if date.weekday() >= 5:
            return 50  # Neutral for weekends
        return 0

    total_minutes = work_logs.aggregate(total=Sum('duration_minutes'))['total'] or 0
    hours = total_minutes / 60
    avg_productivity = work_logs.aggregate(avg=Avg('productivity_rating'))['avg'] or 3

    # Also factor in detailed work logs
    detailed_logs = WorkLog.objects.filter(user=user, date=date)
    detailed_hours = float(detailed_logs.aggregate(total=Sum('hours_spent'))['total'] or 0)

    # Base: 8 hours = 100, scale linearly
    hour_score = min(100, (max(hours, detailed_hours) / 8) * 100)

    # Productivity multiplier (1-5 → 0.4-1.2)
    productivity_multiplier = 0.2 + (avg_productivity / 5) * 1.0

    return min(100, hour_score * productivity_multiplier)


def _calculate_skill_score(sessions):
    """Score based on study sessions, time spent, and quality."""
    if not sessions.exists():
        return 0

    total_minutes = sessions.aggregate(total=Sum('duration_minutes'))['total'] or 0
    avg_rating = sessions.aggregate(avg=Avg('rating'))['avg'] or 3

    # 2 hours of quality study = 100
    time_score = min(100, (total_minutes / 120) * 100)
    quality_multiplier = 0.4 + (avg_rating / 5) * 0.8

    # Bonus for pages read (reading efficiency)
    pages_total = sum(s.pages_read for s in sessions if s.pages_read)
    page_bonus = min(20, pages_total * 0.5)

    return min(100, time_score * quality_multiplier + page_bonus)


def _calculate_fitness_score(fitness_logs):
    """Score based on fitness activity duration and variety."""
    if not fitness_logs.exists():
        return 0

    total_minutes = fitness_logs.aggregate(total=Sum('duration_minutes'))['total'] or 0
    activity_variety = fitness_logs.values('activity_type').distinct().count()

    # 60 minutes = 80, variety bonus
    time_score = min(80, (total_minutes / 60) * 80)
    variety_bonus = min(20, activity_variety * 10)

    return min(100, time_score + variety_bonus)


def _calculate_personal_score(user, date, all_logs):
    """Score for personal time management — social, self-care, meals, household."""
    personal_categories = ['Social', 'Self-Care & Rest', 'Meals & Nutrition',
                           'Household', 'Spirituality', 'Creative']
    personal_logs = all_logs.filter(category__name__in=personal_categories)

    if not personal_logs.exists():
        return 20  # Minimal baseline

    category_count = personal_logs.values('category').distinct().count()
    total_minutes = personal_logs.aggregate(total=Sum('duration_minutes'))['total'] or 0

    # Balance bonus: having 3+ different personal activities
    balance_score = min(50, category_count * 15)

    # Time score: 2-4 hours of personal time is ideal
    hours = total_minutes / 60
    if hours < 1:
        time_score = hours * 30
    elif hours <= 4:
        time_score = 50
    else:
        time_score = max(20, 50 - (hours - 4) * 10)  # Diminishing returns

    return min(100, balance_score + time_score)


def _calculate_consistency_score(user, date, logs):
    """Score for logging consistency — how well the user covered their day."""
    wake = datetime.combine(date, user.wake_time)
    sleep = datetime.combine(date, user.sleep_time)
    interval = user.log_interval_hours

    # Expected blocks
    expected_blocks = 0
    current = wake
    now = timezone.localtime()

    while current < sleep:
        block_end = current + timedelta(hours=interval)
        # Only count past blocks (for today)
        if date < now.date() or block_end <= datetime.combine(date, now.time()):
            expected_blocks += 1
        current = block_end

    if expected_blocks == 0:
        return 100  # Day hasn't started

    actual_blocks = logs.count()
    coverage = min(1.0, actual_blocks / expected_blocks)

    return coverage * 100


def run_llm_scrutinizer(user, date):
    """
    Use LLM to review the day's activities and adjust score by ±30%.
    Uses LiteLLM with Ollama (gemma3:12b).
    """
    try:
        import litellm

        score = DailyScore.objects.get(user=user, date=date)
        if score.llm_processed:
            return score

        logs = ActivityLog.objects.filter(user=user, date=date).select_related(
            'category', 'activity_type')

        if not logs.exists():
            return score

        # Build context
        goals = user.long_term_goals or "No goals specified."
        log_entries = []
        for log in logs:
            entry = (f"[{log.start_time.strftime('%H:%M')}-{log.end_time.strftime('%H:%M')}] "
                     f"{log.category.name}: {log.title}")
            if log.description:
                entry += f" — {log.description}"
            if log.notes:
                entry += f" (Notes: {log.notes})"
            entry += f" [Self-rated: {log.get_productivity_rating_display()}]"
            log_entries.append(entry)

        prompt = f"""You are a strict but fair life coach reviewing someone's daily activity log.

USER'S LONG-TERM GOALS:
{goals}

TODAY'S ACTIVITY LOG ({date.strftime('%A, %B %d, %Y')}):
{chr(10).join(log_entries)}

CURRENT BASE SCORE: {score.base_score:.1f}/100

Your task:
1. Review each activity against the user's long-term goals.
2. Assess whether the day's activities are well-aligned with their goals.
3. Provide a score adjustment between -30 and +30 points.
4. Be stern but constructive — the goal is accountability, not demoralization.

RESPOND WITH ONLY THIS JSON — no markdown fences, no explanation before or after:
{{"adjustment": 0, "feedback": "your feedback here", "highlights": "what they did well", "improvements": "what to improve"}}"""

        response = litellm.completion(
            model=settings.LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_base=settings.OLLAMA_BASE_URL,
            temperature=0.3,
            max_tokens=500,
            response_format={"type": "json_object"},
        )

        result_text = response.choices[0].message.content.strip()

        # Robust JSON extraction — LLMs often wrap in markdown fences or add preamble
        import re
        result = None

        # Strategy 1: Strip markdown code fences
        cleaned = re.sub(r'```(?:json)?\s*', '', result_text).strip()
        cleaned = re.sub(r'```\s*$', '', cleaned).strip()

        # Strategy 2: Find outermost JSON object with brace matching
        def extract_json_object(text):
            start = text.find('{')
            if start == -1:
                return None
            depth = 0
            for i in range(start, len(text)):
                if text[i] == '{':
                    depth += 1
                elif text[i] == '}':
                    depth -= 1
                    if depth == 0:
                        return text[start:i + 1]
            return None

        # Try cleaned text first, then raw
        for attempt in [cleaned, result_text]:
            if result:
                break
            json_str = extract_json_object(attempt)
            if json_str:
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError:
                    # Try fixing common issues: trailing commas, single quotes
                    fixed = re.sub(r',\s*}', '}', json_str)
                    fixed = re.sub(r',\s*]', ']', fixed)
                    try:
                        result = json.loads(fixed)
                    except json.JSONDecodeError:
                        continue

        # Strategy 3: If all parsing fails, extract what we can from plain text
        if not result:
            logger.warning(f"LLM JSON parse failed for {user} on {date}. Raw: {result_text[:300]}")
            # Try to salvage a numeric adjustment from the text
            adj_match = re.search(r'"?adjustment"?\s*[:=]\s*(-?\d+(?:\.\d+)?)', result_text)
            adjustment = float(adj_match.group(1)) if adj_match else 0
            adjustment = max(-30, min(30, adjustment))

            score.llm_adjustment = adjustment
            score.llm_feedback = f"AI reviewed (partial parse):\n{result_text[:300]}"
            score.final_score = max(0, min(100, score.base_score + adjustment))
            score.llm_processed = True
            score.save()
            return score

        adjustment = max(-30, min(30, float(result.get('adjustment', 0))))
        feedback_parts = []
        if result.get('feedback'):
            feedback_parts.append(result['feedback'])
        if result.get('highlights'):
            feedback_parts.append(f"✓ {result['highlights']}")
        if result.get('improvements'):
            feedback_parts.append(f"✗ {result['improvements']}")

        score.llm_adjustment = adjustment
        score.llm_feedback = '\n'.join(feedback_parts)
        score.final_score = max(0, min(100, score.base_score + adjustment))
        score.llm_processed = True
        score.save()

        logger.info(f"LLM scored {user} for {date}: adjustment={adjustment}, "
                    f"final={score.final_score}")

    except Exception as e:
        logger.error(f"LLM scrutinizer error for {user} on {date}: {e}")
        # Keep base score if LLM fails
        score.llm_feedback = f"LLM unavailable: {str(e)[:200]}"
        score.save()

    return score


def aggregate_weekly_score(user, year, week_number):
    """Aggregate daily scores into a weekly score."""
    from datetime import date as date_cls
    # Get the Monday of the given week
    jan1 = date_cls(year, 1, 1)
    start = jan1 + timedelta(weeks=week_number - 1, days=-jan1.weekday())
    end = start + timedelta(days=6)

    daily_scores = DailyScore.objects.filter(
        user=user, date__gte=start, date__lte=end
    )

    if not daily_scores.exists():
        return None

    weekly, _ = WeeklyScore.objects.update_or_create(
        user=user, year=year, week_number=week_number,
        defaults={
            'start_date': start,
            'end_date': end,
            'avg_score': daily_scores.aggregate(avg=Avg('final_score'))['avg'] or 0,
            'best_day_score': max(s.final_score for s in daily_scores),
            'worst_day_score': min(s.final_score for s in daily_scores),
            'total_logged_hours': daily_scores.aggregate(
                total=Sum('total_logged_hours'))['total'] or 0,
            'days_logged': daily_scores.count(),
            'avg_work_score': daily_scores.aggregate(avg=Avg('work_score'))['avg'] or 0,
            'avg_skill_score': daily_scores.aggregate(avg=Avg('skill_score'))['avg'] or 0,
            'avg_fitness_score': daily_scores.aggregate(avg=Avg('fitness_score'))['avg'] or 0,
        },
    )
    return weekly


def aggregate_monthly_score(user, year, month):
    """Aggregate daily scores into a monthly score."""
    daily_scores = DailyScore.objects.filter(
        user=user, date__year=year, date__month=month
    )

    if not daily_scores.exists():
        return None

    monthly, _ = MonthlyScore.objects.update_or_create(
        user=user, year=year, month=month,
        defaults={
            'avg_score': daily_scores.aggregate(avg=Avg('final_score'))['avg'] or 0,
            'best_day_score': max(s.final_score for s in daily_scores),
            'worst_day_score': min(s.final_score for s in daily_scores),
            'total_logged_hours': daily_scores.aggregate(
                total=Sum('total_logged_hours'))['total'] or 0,
            'days_logged': daily_scores.count(),
        },
    )
    return monthly
