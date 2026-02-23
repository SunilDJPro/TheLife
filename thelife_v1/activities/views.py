"""
Activity logging views for TheLife.
Handles hourly logs, catch-up prompts, and activity search.
"""
import json
from datetime import datetime, timedelta, time
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q

from .models import ActivityLog, ActivityCategory, ActivityType, RecurringTask
from .forms import ActivityLogForm, QuickLogForm, RecurringTaskForm


@login_required
def activity_log_list(request):
    """List all activity logs for a given date."""
    date_str = request.GET.get('date')
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()

    logs = ActivityLog.objects.filter(
        user=request.user, date=selected_date
    ).select_related('category', 'activity_type')

    # Find unfilled time blocks for catch-up
    unfilled_blocks = _get_unfilled_blocks(request.user, selected_date, logs)

    context = {
        'logs': logs,
        'selected_date': selected_date,
        'unfilled_blocks': unfilled_blocks,
        'quick_form': QuickLogForm(),
    }

    if request.htmx:
        return render(request, 'activities/partials/log_list.html', context)
    return render(request, 'activities/log_list.html', context)


@login_required
def activity_log_create(request):
    """Create a new activity log entry."""
    form = ActivityLogForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        log = form.save(commit=False)
        log.user = request.user
        # Handle metadata from dynamic form
        metadata = {}
        for key in request.POST:
            if key.startswith('meta_'):
                metadata[key[5:]] = request.POST[key]
        if metadata:
            log.metadata = metadata
        log.save()

        if request.htmx:
            logs = ActivityLog.objects.filter(
                user=request.user, date=log.date
            ).select_related('category', 'activity_type')
            return render(request, 'activities/partials/log_list.html', {
                'logs': logs,
                'selected_date': log.date,
                'unfilled_blocks': _get_unfilled_blocks(request.user, log.date, logs),
                'quick_form': QuickLogForm(),
                'just_saved': True,
            })
        return redirect('activities:log_list')

    # Pre-fill date and time from query params (for catch-up blocks)
    if request.GET.get('date'):
        form.initial['date'] = request.GET['date']
    if request.GET.get('start_time'):
        form.initial['start_time'] = request.GET['start_time']
    if request.GET.get('end_time'):
        form.initial['end_time'] = request.GET['end_time']

    context = {'form': form, 'is_new': True}
    if request.htmx:
        return render(request, 'activities/partials/log_form.html', context)
    return render(request, 'activities/log_form.html', context)


@login_required
def activity_log_edit(request, log_id):
    """Edit an existing activity log."""
    log = get_object_or_404(ActivityLog, id=log_id, user=request.user)
    form = ActivityLogForm(request.POST or None, instance=log)

    if request.method == 'POST' and form.is_valid():
        log = form.save(commit=False)
        metadata = {}
        for key in request.POST:
            if key.startswith('meta_'):
                metadata[key[5:]] = request.POST[key]
        if metadata:
            log.metadata = metadata
        log.save()

        if request.htmx:
            logs = ActivityLog.objects.filter(
                user=request.user, date=log.date
            ).select_related('category', 'activity_type')
            return render(request, 'activities/partials/log_list.html', {
                'logs': logs,
                'selected_date': log.date,
                'unfilled_blocks': _get_unfilled_blocks(request.user, log.date, logs),
                'quick_form': QuickLogForm(),
            })
        return redirect('activities:log_list')

    context = {'form': form, 'log': log, 'is_new': False}
    if request.htmx:
        return render(request, 'activities/partials/log_form.html', context)
    return render(request, 'activities/log_form.html', context)


@login_required
def activity_log_delete(request, log_id):
    """Delete an activity log."""
    log = get_object_or_404(ActivityLog, id=log_id, user=request.user)
    date = log.date
    log.delete()

    if request.htmx:
        logs = ActivityLog.objects.filter(
            user=request.user, date=date
        ).select_related('category', 'activity_type')
        return render(request, 'activities/partials/log_list.html', {
            'logs': logs,
            'selected_date': date,
            'unfilled_blocks': _get_unfilled_blocks(request.user, date, logs),
            'quick_form': QuickLogForm(),
        })
    return redirect('activities:log_list')


@login_required
def quick_log_save(request):
    """Save a quick log entry (from catch-up prompt)."""
    if request.method != 'POST':
        return redirect('activities:log_list')

    form = QuickLogForm(request.POST)
    date_str = request.POST.get('date', '')
    try:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        date = timezone.localdate()

    if form.is_valid():
        ActivityLog.objects.create(
            user=request.user,
            category=form.cleaned_data['category'],
            date=date,
            start_time=form.cleaned_data['start_time'],
            end_time=form.cleaned_data['end_time'],
            title=form.cleaned_data['title'],
            productivity_rating=form.cleaned_data['productivity_rating'],
        )

    if request.htmx:
        logs = ActivityLog.objects.filter(
            user=request.user, date=date
        ).select_related('category', 'activity_type')
        return render(request, 'activities/partials/log_list.html', {
            'logs': logs,
            'selected_date': date,
            'unfilled_blocks': _get_unfilled_blocks(request.user, date, logs),
            'quick_form': QuickLogForm(),
            'just_saved': True,
        })
    return redirect('activities:log_list')


@login_required
def get_activity_types(request):
    """HTMX endpoint: return activity types for a category (for dropdown)."""
    category_id = request.GET.get('category')
    types = ActivityType.objects.filter(
        category_id=category_id, is_active=True
    ) if category_id else ActivityType.objects.none()

    options = '<option value="">-- Select Type --</option>'
    for t in types:
        options += f'<option value="{t.id}">{t.name}</option>'
    return JsonResponse({'html': options}, safe=False) if not request.htmx else \
        render(request, 'activities/partials/type_options.html', {'types': types})


@login_required
def search_activities(request):
    """Search activity categories and types (for quick search during logging)."""
    q = request.GET.get('q', '').strip()
    if len(q) < 1:
        return JsonResponse({'results': []})

    categories = ActivityCategory.objects.filter(
        Q(name__icontains=q) & Q(is_active=True)
    )[:5]

    types = ActivityType.objects.filter(
        Q(name__icontains=q) & Q(is_active=True)
    ).select_related('category')[:10]

    results = []
    for cat in categories:
        results.append({
            'id': str(cat.id), 'type': 'category',
            'label': cat.name, 'icon': cat.icon, 'color': cat.color,
        })
    for t in types:
        results.append({
            'id': str(t.id), 'type': 'activity_type',
            'category_id': str(t.category_id),
            'label': f"{t.category.name} → {t.name}",
            'icon': t.category.icon, 'color': t.category.color,
        })

    return JsonResponse({'results': results})


@login_required
def get_metadata_form(request):
    """HTMX endpoint: return category-specific metadata fields."""
    category_id = request.GET.get('category')
    if not category_id:
        return render(request, 'activities/partials/metadata_empty.html')

    try:
        category = ActivityCategory.objects.get(id=category_id)
    except ActivityCategory.DoesNotExist:
        return render(request, 'activities/partials/metadata_empty.html')

    template_map = {
        'Fitness': 'activities/partials/metadata_fitness.html',
        'Meals & Nutrition': 'activities/partials/metadata_meals.html',
        'Commute & Travel': 'activities/partials/metadata_commute.html',
    }

    template = template_map.get(category.name, 'activities/partials/metadata_empty.html')
    return render(request, template)


@login_required
def recurring_task_list(request):
    """List and manage recurring tasks."""
    tasks = RecurringTask.objects.filter(user=request.user).select_related('category')
    form = RecurringTaskForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        task = form.save(commit=False)
        task.user = request.user
        task.save()
        if request.htmx:
            tasks = RecurringTask.objects.filter(user=request.user).select_related('category')
            return render(request, 'activities/partials/recurring_list.html', {'tasks': tasks})
        return redirect('activities:recurring_tasks')

    context = {'tasks': tasks, 'form': form}
    if request.htmx:
        return render(request, 'activities/partials/recurring_list.html', context)
    return render(request, 'activities/recurring_tasks.html', context)


@login_required
def recurring_task_delete(request, task_id):
    """Delete a recurring task."""
    RecurringTask.objects.filter(id=task_id, user=request.user).delete()
    if request.htmx:
        tasks = RecurringTask.objects.filter(user=request.user).select_related('category')
        return render(request, 'activities/partials/recurring_list.html', {'tasks': tasks})
    return redirect('activities:recurring_tasks')


def _get_unfilled_blocks(user, date, existing_logs):
    """
    Calculate unfilled time blocks between wake and sleep times.
    Returns list of dicts with start_time, end_time for blocks without logs.
    """
    now = timezone.localtime()
    today = now.date()

    wake = user.wake_time
    sleep = user.sleep_time
    interval = user.log_interval_hours

    # Build expected time blocks
    blocks = []
    current = datetime.combine(date, wake)
    end_dt = datetime.combine(date, sleep)

    while current < end_dt:
        block_end = current + timedelta(hours=interval)
        if block_end > end_dt:
            block_end = end_dt
        blocks.append({
            'start_time': current.time(),
            'end_time': block_end.time(),
        })
        current = block_end

    # Remove blocks that are in the future (for today only)
    if date == today:
        blocks = [b for b in blocks if b['end_time'] <= now.time()]

    # Remove blocks that have logs
    logged_blocks = set()
    for log in existing_logs:
        logged_blocks.add((log.start_time, log.end_time))

    unfilled = []
    for block in blocks:
        # Check if any log overlaps this block
        has_log = False
        for log in existing_logs:
            if log.start_time < block['end_time'] and log.end_time > block['start_time']:
                has_log = True
                break
        if not has_log:
            unfilled.append(block)

    return unfilled
