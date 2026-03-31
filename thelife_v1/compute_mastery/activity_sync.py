"""
Sync Compute Mastery submissions to ActivityLog for daily scoring.
Follows the same pattern as activities/sync.py.
"""
from datetime import datetime, timedelta

from activities.models import ActivityLog, ActivityCategory, ActivityType


def create_activity_from_submission(solution, timing_data=None, perf_data=None,
                                    llm_verdict=None):
    """
    Create/update an ActivityLog from a judged solution submission.

    Logs concise metadata (problem title, result, version, runtime, LLM verdict)
    for the daily scoring LLM — not the full code.
    """
    user = solution.problem.user

    # Compute Mastery falls under "Skill Learning" → "Practice / Hands-on"
    category = ActivityCategory.objects.filter(name='Skill Learning').first()
    if not category:
        return None

    activity_type = ActivityType.objects.filter(
        category=category, name__icontains='Practice'
    ).first()

    # Build description with summary metadata
    status_text = 'Accepted' if solution.is_accepted else 'Failed'
    desc_parts = [
        f"Problem: {solution.problem.title} ({solution.problem.get_difficulty_display()})",
        f"Language: {solution.get_language_display()}",
        f"Version: v{solution.version} — {status_text}",
        f"Flags: {solution.compiler_flags} {solution.custom_flags}".strip(),
    ]

    if timing_data and timing_data.get('median_us'):
        median = timing_data['median_us']
        if median >= 1000:
            desc_parts.append(f"Runtime: {median / 1000:.2f} ms (median)")
        else:
            desc_parts.append(f"Runtime: {median:.1f} us (median)")

    if perf_data and perf_data.get('ipc'):
        desc_parts.append(f"IPC: {perf_data['ipc']}")

    if solution.notes:
        desc_parts.append(f"Notes: {solution.notes}")

    if llm_verdict:
        # Include first 200 chars of AI analysis for the scoring LLM
        desc_parts.append(f"AI Analysis: {llm_verdict[:200]}")

    # Time: use submission timestamp
    submit_time = solution.created_at
    # Estimate ~30 min of work per submission (reasonable default)
    start_dt = submit_time - timedelta(minutes=30)
    end_dt = submit_time

    # Check for existing activity tied to this solution
    existing = ActivityLog.objects.filter(
        user=user,
        date=submit_time.date(),
        metadata__contains={
            'source': 'compute_mastery',
            'source_id': str(solution.id),
        },
    ).first()

    activity_data = {
        'title': f"Compute Mastery: {solution.problem.title} v{solution.version}",
        'description': '\n'.join(desc_parts),
        'start_time': start_dt.time(),
        'end_time': end_dt.time(),
        'duration_minutes': 30,
        'productivity_rating': 4 if solution.is_accepted else 3,
    }

    if existing:
        for key, val in activity_data.items():
            setattr(existing, key, val)
        existing.save()
        return existing

    log = ActivityLog.objects.create(
        user=user,
        category=category,
        activity_type=activity_type,
        date=submit_time.date(),
        **activity_data,
        metadata={
            'source': 'compute_mastery',
            'source_id': str(solution.id),
            'problem_slug': solution.problem.slug,
            'problem_title': solution.problem.title,
            'difficulty': solution.problem.difficulty,
            'version': solution.version,
            'language': solution.language,
            'is_accepted': solution.is_accepted,
            'median_runtime_us': timing_data.get('median_us') if timing_data else None,
            'ipc': perf_data.get('ipc') if perf_data else None,
        },
    )
    return log
