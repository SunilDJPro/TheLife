from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

from .forms import TheLifeLoginForm, UserProfileForm, UserGoalForm
from .models import UserGoal


def login_view(request):
    """Login page."""
    if request.user.is_authenticated:
        return redirect('dashboard:home')

    form = TheLifeLoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('dashboard:home')

    return render(request, 'accounts/login.html', {'form': form})


@login_required
def logout_view(request):
    """Logout and redirect to login."""
    logout(request)
    return redirect('accounts:login')


@login_required
def profile_view(request):
    """User profile/settings page."""
    if request.method == 'POST':
        if 'save_profile' in request.POST:
            form = UserProfileForm(request.POST, instance=request.user)
            if form.is_valid():
                form.save()
            return redirect('accounts:profile')

        if 'add_goal' in request.POST:
            goal_form = UserGoalForm(request.POST)
            if goal_form.is_valid():
                goal = goal_form.save(commit=False)
                goal.user = request.user
                goal.save()
            if request.htmx:
                goals = request.user.goals.all()
                return render(request, 'accounts/partials/goals_list.html', {'goals': goals})
            return redirect('accounts:profile')

    form = UserProfileForm(instance=request.user)
    goal_form = UserGoalForm()
    goals = request.user.goals.all()
    return render(request, 'accounts/profile.html', {
        'form': form,
        'goal_form': goal_form,
        'goals': goals,
    })


@login_required
@require_POST
def delete_goal(request, goal_id):
    """Delete a user goal."""
    UserGoal.objects.filter(id=goal_id, user=request.user).delete()
    if request.htmx:
        goals = request.user.goals.all()
        return render(request, 'accounts/partials/goals_list.html', {'goals': goals})
    return redirect('accounts:profile')


@login_required
@require_POST
def save_push_subscription(request):
    """Save push notification subscription."""
    try:
        data = json.loads(request.body)
        request.user.push_subscription = data
        request.user.save(update_fields=['push_subscription'])
        return JsonResponse({'status': 'ok'})
    except (json.JSONDecodeError, Exception) as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)