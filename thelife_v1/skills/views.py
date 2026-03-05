"""Skill management views for TheLife."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError

from .models import Skill, SkillResource, SkillSession
from .forms import SkillForm, SkillResourceForm, SkillSessionForm
from activities.sync import create_activity_from_skill_session


@login_required
def skill_list(request):
    """List all skills organized by status."""
    skills = Skill.objects.filter(user=request.user).prefetch_related('resources')
    active_skills = skills.filter(status='active')
    queued_skills = skills.filter(status='queued')
    completed_skills = skills.filter(status='completed')
    paused_skills = skills.filter(status='paused')

    can_activate = active_skills.count() < request.user.max_active_skills

    context = {
        'active_skills': active_skills,
        'queued_skills': queued_skills,
        'completed_skills': completed_skills,
        'paused_skills': paused_skills,
        'can_activate': can_activate,
        'max_active': request.user.max_active_skills,
    }
    return render(request, 'skills/skill_list.html', context)


@login_required
def skill_create(request):
    """Create a new skill."""
    form = SkillForm(request.POST or None)
    if request.method == 'POST':
        form.instance.user = request.user
        if form.is_valid():
            skill = form.save(commit=False)
            skill.user = request.user
            try:
                skill.save()
                return redirect('skills:skill_detail', skill_id=skill.id)
            except ValidationError as e:
                form.add_error(None, e.message)

    context = {'form': form, 'is_new': True}
    if request.htmx:
        return render(request, 'skills/partials/skill_form.html', context)
    return render(request, 'skills/skill_form.html', context)


@login_required
def skill_detail(request, skill_id):
    """View skill details with resources and sessions."""
    skill = get_object_or_404(Skill, id=skill_id, user=request.user)
    resources = skill.resources.all()
    resource_form = SkillResourceForm()

    # Get recent sessions across all resources
    recent_sessions = SkillSession.objects.filter(
        resource__skill=skill
    ).select_related('resource')[:20]

    # Reading speed stats for book resources
    book_sessions = SkillSession.objects.filter(
        resource__skill=skill,
        resource__resource_type='book',
        start_page__isnull=False,
        end_page__isnull=False,
    )
    avg_pages_per_hour = 0
    if book_sessions.exists():
        total_pages = sum(s.pages_read for s in book_sessions)
        total_minutes = sum(s.duration_minutes for s in book_sessions)
        if total_minutes > 0:
            avg_pages_per_hour = round(total_pages / (total_minutes / 60), 1)

    context = {
        'skill': skill,
        'resources': resources,
        'resource_form': resource_form,
        'recent_sessions': recent_sessions,
        'avg_pages_per_hour': avg_pages_per_hour,
    }
    return render(request, 'skills/skill_detail.html', context)


@login_required
def skill_edit(request, skill_id):
    """Edit a skill."""
    skill = get_object_or_404(Skill, id=skill_id, user=request.user)
    form = SkillForm(request.POST or None, instance=skill)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            return redirect('skills:skill_detail', skill_id=skill.id)
        except ValidationError as e:
            form.add_error(None, e.message)
    return render(request, 'skills/skill_form.html', {'form': form, 'skill': skill})


@login_required
def skill_activate(request, skill_id):
    """Activate a queued/paused skill (with hard block check)."""
    skill = get_object_or_404(Skill, id=skill_id, user=request.user)
    try:
        skill.status = 'active'
        skill.save()
        messages.success(request, f'"{skill.name}" is now active!')
    except ValidationError as e:
        messages.error(request, str(e.message))
    return redirect('skills:skill_list')


@login_required
def resource_add(request, skill_id):
    """Add a resource to a skill."""
    skill = get_object_or_404(Skill, id=skill_id, user=request.user)
    form = SkillResourceForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        resource = form.save(commit=False)
        resource.skill = skill
        resource.save()
        if request.htmx:
            resources = skill.resources.all()
            return render(request, 'skills/partials/resource_list.html',
                         {'resources': resources, 'skill': skill})
        return redirect('skills:skill_detail', skill_id=skill.id)
    return redirect('skills:skill_detail', skill_id=skill.id)


@login_required
def session_log(request, resource_id):
    """Log a study session for a resource."""
    resource = get_object_or_404(SkillResource, id=resource_id,
                                  skill__user=request.user)
    form = SkillSessionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        session = form.save(commit=False)
        session.resource = resource
        session.save()
        # Sync to ActivityLog + trigger scoring
        create_activity_from_skill_session(request.user, session)
        try:
            from scoring.engine import calculate_daily_score, aggregate_weekly_score, aggregate_monthly_score
            calculate_daily_score(request.user, session.date)
            year, week, _ = session.date.isocalendar()
            aggregate_weekly_score(request.user, year, week)
            aggregate_monthly_score(request.user, session.date.year, session.date.month)
        except Exception:
            pass
        if request.htmx:
            sessions = SkillSession.objects.filter(
                resource__skill=resource.skill
            ).select_related('resource')[:20]
            return render(request, 'skills/partials/session_list.html',
                         {'sessions': sessions})
        return redirect('skills:skill_detail', skill_id=resource.skill.id)

    # Pre-fill with resource-specific fields
    is_book = resource.resource_type == 'book'
    has_video = resource.resource_type.startswith('course_')

    context = {
        'form': form,
        'resource': resource,
        'is_book': is_book,
        'has_video': has_video,
    }
    if request.htmx:
        return render(request, 'skills/partials/session_form.html', context)
    return render(request, 'skills/session_form.html', context)
