"""Work management views for TheLife."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .models import WorkProfile, Project, Deliverable, WorkLog
from .forms import WorkProfileForm, ProjectForm, DeliverableForm, WorkLogForm
from activities.sync import create_activity_from_work_log


@login_required
def work_dashboard(request):
    """Work management main page."""
    profile, _ = WorkProfile.objects.get_or_create(user=request.user)
    projects = Project.objects.filter(user=request.user)
    active_projects = projects.filter(status='active')
    recent_logs = WorkLog.objects.filter(user=request.user)[:10]

    # Stats
    today = timezone.localdate()
    today_hours = sum(l.hours_spent for l in WorkLog.objects.filter(user=request.user, date=today))

    context = {
        'profile': profile,
        'projects': projects,
        'active_projects': active_projects,
        'recent_logs': recent_logs,
        'today_hours': today_hours,
    }
    return render(request, 'work/dashboard.html', context)


@login_required
def work_profile_edit(request):
    """Edit work profile."""
    profile, _ = WorkProfile.objects.get_or_create(user=request.user)
    form = WorkProfileForm(request.POST or None, instance=profile)
    if request.method == 'POST' and form.is_valid():
        form.save()
        if request.htmx:
            return render(request, 'work/partials/profile_card.html', {'profile': profile})
        return redirect('work:dashboard')
    return render(request, 'work/profile_edit.html', {'form': form, 'profile': profile})


@login_required
def project_create(request):
    """Create a new project."""
    form = ProjectForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        project = form.save(commit=False)
        project.user = request.user
        project.save()
        if request.htmx:
            projects = Project.objects.filter(user=request.user)
            return render(request, 'work/partials/project_list.html', {'projects': projects})
        return redirect('work:project_detail', project_id=project.id)
    context = {'form': form, 'is_new': True}
    if request.htmx:
        return render(request, 'work/partials/project_form.html', context)
    return render(request, 'work/project_form.html', context)


@login_required
def project_detail(request, project_id):
    """View project details with deliverables and logs."""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    deliverables = project.deliverables.all()
    logs = project.work_logs.all()[:20]
    deliverable_form = DeliverableForm()

    context = {
        'project': project,
        'deliverables': deliverables,
        'logs': logs,
        'deliverable_form': deliverable_form,
    }
    return render(request, 'work/project_detail.html', context)


@login_required
def project_edit(request, project_id):
    """Edit a project."""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    form = ProjectForm(request.POST or None, instance=project)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('work:project_detail', project_id=project.id)
    return render(request, 'work/project_form.html', {'form': form, 'project': project})


@login_required
def deliverable_add(request, project_id):
    """Add a deliverable to a project."""
    project = get_object_or_404(Project, id=project_id, user=request.user)
    form = DeliverableForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        deliverable = form.save(commit=False)
        deliverable.project = project
        deliverable.save()
        if request.htmx:
            deliverables = project.deliverables.all()
            return render(request, 'work/partials/deliverable_list.html',
                         {'deliverables': deliverables, 'project': project})
    return redirect('work:project_detail', project_id=project.id)


@login_required
def deliverable_update_status(request, deliverable_id):
    """Quick status update for a deliverable."""
    deliverable = get_object_or_404(Deliverable,
                                     id=deliverable_id,
                                     project__user=request.user)
    new_status = request.POST.get('status')
    if new_status and new_status in dict(Deliverable.STATUS_CHOICES):
        deliverable.status = new_status
        if new_status == 'completed':
            deliverable.completed_date = timezone.localdate()
        deliverable.save()
    if request.htmx:
        deliverables = deliverable.project.deliverables.all()
        return render(request, 'work/partials/deliverable_list.html',
                     {'deliverables': deliverables, 'project': deliverable.project})
    return redirect('work:project_detail', project_id=deliverable.project.id)


@login_required
def work_log_create(request):
    """Create a work log entry."""
    form = WorkLogForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        log = form.save(commit=False)
        log.user = request.user
        log.save()
        create_activity_from_work_log(request.user, log)
        # Trigger analytical scoring + aggregates
        try:
            from scoring.engine import calculate_daily_score, aggregate_weekly_score, aggregate_monthly_score
            calculate_daily_score(request.user, log.date)
            year, week, _ = log.date.isocalendar()
            aggregate_weekly_score(request.user, year, week)
            aggregate_monthly_score(request.user, log.date.year, log.date.month)
        except Exception:
            pass
        if request.htmx:
            recent_logs = WorkLog.objects.filter(user=request.user)[:10]
            return render(request, 'work/partials/work_log_list.html', {'logs': recent_logs})
        return redirect('work:dashboard')

    context = {'form': form}
    if request.htmx:
        return render(request, 'work/partials/work_log_form.html', context)
    return render(request, 'work/work_log_form.html', context)


@login_required
def work_log_list(request):
    """List work logs with date filter."""
    date_str = request.GET.get('date')
    logs = WorkLog.objects.filter(user=request.user).select_related('project', 'deliverable')
    if date_str:
        logs = logs.filter(date=date_str)

    if request.htmx:
        return render(request, 'work/partials/work_log_list.html', {'logs': logs[:30]})
    return render(request, 'work/work_logs.html', {'logs': logs[:30]})


@login_required
def deliverables_for_project(request):
    """HTMX endpoint: return deliverables dropdown for a project."""
    project_id = request.GET.get('project')
    deliverables = Deliverable.objects.filter(project_id=project_id) if project_id else []

    if request.htmx:
        return render(request, 'work/partials/deliverable_options.html',
                     {'deliverables': deliverables})
    return render(request, 'work/partials/deliverable_options.html',
                 {'deliverables': deliverables})
