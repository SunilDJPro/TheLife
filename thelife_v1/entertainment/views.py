"""Entertainment views for TheLife."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .models import EntertainmentLog
from .forms import EntertainmentLogForm
from activities.sync import create_activity_from_entertainment
from activities.models import ActivityLog


@login_required
def entertainment_list(request):
    """List entertainment logs."""
    logs = EntertainmentLog.objects.filter(user=request.user)
    type_filter = request.GET.get('type')
    if type_filter:
        logs = logs.filter(entertainment_type=type_filter)

    context = {'logs': logs[:30], 'type_filter': type_filter}
    if request.htmx:
        return render(request, 'entertainment/partials/log_list.html', context)
    return render(request, 'entertainment/entertainment_list.html', context)


@login_required
def entertainment_create(request):
    """Create an entertainment log."""
    form = EntertainmentLogForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        log = form.save(commit=False)
        log.user = request.user
        log.save()
        create_activity_from_entertainment(request.user, log)
        if request.htmx:
            logs = EntertainmentLog.objects.filter(user=request.user)[:30]
            return render(request, 'entertainment/partials/log_list.html', {'logs': logs})
        return redirect('entertainment:list')

    context = {'form': form}
    if request.htmx:
        return render(request, 'entertainment/partials/log_form.html', context)
    return render(request, 'entertainment/entertainment_form.html', context)


@login_required
def entertainment_edit(request, log_id):
    """Edit an entertainment log."""
    log = get_object_or_404(EntertainmentLog, id=log_id, user=request.user)
    form = EntertainmentLogForm(request.POST or None, instance=log)
    if request.method == 'POST' and form.is_valid():
        form.save()
        create_activity_from_entertainment(request.user, log)
        return redirect('entertainment:list')
    return render(request, 'entertainment/entertainment_form.html', {'form': form, 'log': log})


@login_required
def entertainment_delete(request, log_id):
    """Delete an entertainment log."""
    # Also remove the synced ActivityLog
    ent = EntertainmentLog.objects.filter(id=log_id, user=request.user).first()
    if ent:
        ActivityLog.objects.filter(
            user=request.user,
            metadata__contains={'source': 'entertainment', 'source_id': str(ent.id)},
        ).delete()
        ent.delete()
    if request.htmx:
        logs = EntertainmentLog.objects.filter(user=request.user)[:30]
        return render(request, 'entertainment/partials/log_list.html', {'logs': logs})
    return redirect('entertainment:list')