"""
Utility to sync Work/Entertainment entries to ActivityLog.
The dashboard calendar only reads ActivityLog — so all other apps
must create a corresponding ActivityLog when they log something.
"""
from activities.models import ActivityLog, ActivityCategory, ActivityType


def create_activity_from_work_log(user, work_log):
    """Create/update an ActivityLog from a WorkLog entry."""
    category = ActivityCategory.objects.filter(name='Work').first()
    if not category:
        return None

    # Try to find a matching activity type
    activity_type = None
    if work_log.status_tag:
        activity_type = ActivityType.objects.filter(
            category=category, name__icontains=work_log.status_tag
        ).first()

    # Build description
    desc_parts = []
    if work_log.project:
        desc_parts.append(f"Project: {work_log.project.name}")
    if work_log.deliverable:
        desc_parts.append(f"Deliverable: {work_log.deliverable.title}")
    if work_log.description:
        desc_parts.append(work_log.description)

    # Calculate start/end time from hours_spent
    # Default to work profile hours if available
    start_time = user.wake_time  # fallback
    try:
        profile = user.work_profile
        start_time = profile.work_start_time
    except Exception:
        pass

    from datetime import datetime, timedelta
    start_dt = datetime.combine(work_log.date, start_time)
    hours = float(work_log.hours_spent)
    end_dt = start_dt + timedelta(hours=hours) if hours > 0 else start_dt + timedelta(hours=1)

    # Check for existing activity tied to this work log (via metadata)
    existing = ActivityLog.objects.filter(
        user=user,
        date=work_log.date,
        metadata__contains={'source': 'work_log', 'source_id': str(work_log.id)},
    ).first()

    if existing:
        existing.title = work_log.title
        existing.description = '\n'.join(desc_parts)
        existing.start_time = start_dt.time()
        existing.end_time = end_dt.time()
        existing.duration_minutes = int(hours * 60) if hours > 0 else 60
        existing.notes = work_log.blockers
        existing.save()
        return existing

    log = ActivityLog.objects.create(
        user=user,
        category=category,
        activity_type=activity_type,
        date=work_log.date,
        start_time=start_dt.time(),
        end_time=end_dt.time(),
        duration_minutes=int(hours * 60) if hours > 0 else 60,
        title=work_log.title,
        description='\n'.join(desc_parts),
        notes=work_log.blockers,
        productivity_rating=3,
        metadata={
            'source': 'work_log',
            'source_id': str(work_log.id),
            'project': work_log.project.name if work_log.project else '',
            'hours_spent': str(work_log.hours_spent),
            'status_tag': work_log.status_tag,
        },
    )
    return log


def create_activity_from_entertainment(user, ent_log):
    """Create/update an ActivityLog from an EntertainmentLog entry."""
    category = ActivityCategory.objects.filter(name='Entertainment').first()
    if not category:
        return None

    # Match type
    type_map = {
        'movie': 'Movie',
        'series': 'Series / Short Film',
        'gaming': 'Gaming',
    }
    type_name = type_map.get(ent_log.entertainment_type, '')
    activity_type = ActivityType.objects.filter(
        category=category, name=type_name
    ).first() if type_name else None

    # Build times
    from datetime import datetime, timedelta
    start_time = ent_log.start_time or datetime.strptime('18:00', '%H:%M').time()
    duration = ent_log.duration_minutes or 120
    start_dt = datetime.combine(ent_log.date, start_time)
    end_dt = start_dt + timedelta(minutes=duration)

    desc_parts = []
    if ent_log.venue:
        desc_parts.append(f"Venue: {ent_log.venue}")
    if ent_log.description:
        desc_parts.append(ent_log.description)
    if ent_log.rating:
        desc_parts.append(f"Rating: {ent_log.rating}/10")

    # Check existing
    existing = ActivityLog.objects.filter(
        user=user,
        date=ent_log.date,
        metadata__contains={'source': 'entertainment', 'source_id': str(ent_log.id)},
    ).first()

    if existing:
        existing.title = f"{ent_log.get_entertainment_type_display()}: {ent_log.title}"
        existing.description = '\n'.join(desc_parts)
        existing.start_time = start_time
        existing.end_time = end_dt.time()
        existing.duration_minutes = duration
        existing.save()
        return existing

    log = ActivityLog.objects.create(
        user=user,
        category=category,
        activity_type=activity_type,
        date=ent_log.date,
        start_time=start_time,
        end_time=end_dt.time(),
        duration_minutes=duration,
        title=f"{ent_log.get_entertainment_type_display()}: {ent_log.title}",
        description='\n'.join(desc_parts),
        productivity_rating=2,  # Entertainment default
        metadata={
            'source': 'entertainment',
            'source_id': str(ent_log.id),
            'entertainment_type': ent_log.entertainment_type,
            'venue': ent_log.venue or '',
            'rating': ent_log.rating,
            'is_scheduled': ent_log.is_scheduled,
        },
    )
    return log