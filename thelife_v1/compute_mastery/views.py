"""Compute Mastery views — Problem CRUD, solution management, judge interface."""
import json
import uuid
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Max, Q
from django.views.decorators.http import require_POST

from .models import Problem, Tag, TestCase, Solution, JudgeResult
from .forms import ProblemForm, TestCaseFormSet

try:
    import redis
    redis_client = redis.Redis.from_url('redis://localhost:6379/0')
except Exception:
    redis_client = None


# ── Problem Browsing ──────────────────────────────────────────────

@login_required
def problem_list(request):
    """List all problems with filtering by difficulty, tags, category."""
    problems = Problem.objects.filter(user=request.user)

    # Filters
    difficulty = request.GET.get('difficulty')
    category = request.GET.get('category')
    tag_slug = request.GET.get('tag')
    search = request.GET.get('q')

    if difficulty:
        problems = problems.filter(difficulty=difficulty)
    if category:
        problems = problems.filter(category=category)
    if tag_slug:
        problems = problems.filter(tags__slug=tag_slug)
    if search:
        problems = problems.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )

    all_tags = Tag.objects.filter(problems__user=request.user).distinct()

    context = {
        'problems': problems,
        'all_tags': all_tags,
        'current_difficulty': difficulty or '',
        'current_category': category or '',
        'current_tag': tag_slug or '',
        'search_query': search or '',
    }
    return render(request, 'compute_mastery/problem_list.html', context)


@login_required
def problem_detail(request, slug):
    """Problem workspace — statement + code editor + results panel."""
    problem = get_object_or_404(Problem, slug=slug, user=request.user)
    sample_tests = problem.test_cases.filter(is_sample=True)
    solutions = problem.solutions.all()[:10]
    starter_code = problem.starter_code.get('cpp', '#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    \n    return 0;\n}')

    # If there's a latest solution, pre-fill the editor with it
    latest_solution = problem.solutions.first()
    editor_code = latest_solution.code if latest_solution else starter_code

    context = {
        'problem': problem,
        'sample_tests': sample_tests,
        'solutions': solutions,
        'editor_code': editor_code,
        'starter_code': starter_code,
    }
    return render(request, 'compute_mastery/problem_detail.html', context)


# ── Problem CRUD ──────────────────────────────────────────────────

@login_required
def problem_create(request):
    if request.method == 'POST':
        form = ProblemForm(request.POST)
        if form.is_valid():
            problem = form.save(commit=False)
            problem.user = request.user
            problem.save()
            form._save_tags(problem)
            form.save_m2m()
            messages.success(request, f'Problem "{problem.title}" created.')
            return redirect('compute_mastery:test_case_manage', slug=problem.slug)
    else:
        form = ProblemForm()

    return render(request, 'compute_mastery/problem_form.html', {
        'form': form,
        'is_edit': False,
    })


@login_required
def problem_edit(request, slug):
    problem = get_object_or_404(Problem, slug=slug, user=request.user)
    if request.method == 'POST':
        form = ProblemForm(request.POST, instance=problem)
        if form.is_valid():
            form.save()
            messages.success(request, f'Problem "{problem.title}" updated.')
            return redirect('compute_mastery:problem_detail', slug=problem.slug)
    else:
        form = ProblemForm(instance=problem)

    return render(request, 'compute_mastery/problem_form.html', {
        'form': form,
        'is_edit': True,
        'problem': problem,
    })


@login_required
@require_POST
def problem_delete(request, slug):
    problem = get_object_or_404(Problem, slug=slug, user=request.user)
    title = problem.title
    problem.delete()
    messages.success(request, f'Problem "{title}" deleted.')
    return redirect('compute_mastery:problem_list')


# ── Test Case Management ──────────────────────────────────────────

@login_required
def test_case_manage(request, slug):
    problem = get_object_or_404(Problem, slug=slug, user=request.user)

    if request.method == 'POST':
        formset = TestCaseFormSet(request.POST, instance=problem)
        if formset.is_valid():
            formset.save()
            messages.success(request, 'Test cases saved.')
            return redirect('compute_mastery:problem_detail', slug=problem.slug)
    else:
        formset = TestCaseFormSet(instance=problem)

    return render(request, 'compute_mastery/test_case_form.html', {
        'problem': problem,
        'formset': formset,
    })


# ── Solution Views ────────────────────────────────────────────────

@login_required
def solution_list(request, slug):
    """All solution versions for a problem."""
    problem = get_object_or_404(Problem, slug=slug, user=request.user)
    solutions = problem.solutions.all()

    return render(request, 'compute_mastery/solution_list.html', {
        'problem': problem,
        'solutions': solutions,
    })


@login_required
def solution_compare(request, slug):
    """Compare 2+ solution versions side-by-side."""
    problem = get_object_or_404(Problem, slug=slug, user=request.user)
    version_ids = request.GET.getlist('v')

    solutions = Solution.objects.filter(
        problem=problem, id__in=version_ids
    ).prefetch_related('results')

    comparison = []
    for sol in solutions:
        best_result = sol.results.filter(status='accepted').first()
        comparison.append({
            'solution': sol,
            'code': sol.code,
            'perf': {
                'median_us': best_result.median_time_us if best_result else None,
                'instructions': best_result.instructions if best_result else None,
                'cycles': best_result.cycles if best_result else None,
                'cache_misses': best_result.cache_misses if best_result else None,
                'branch_misses': best_result.branch_misses if best_result else None,
                'ipc': best_result.ipc if best_result else None,
            }
        })

    return render(request, 'compute_mastery/compare.html', {
        'problem': problem,
        'comparison': comparison,
    })


# ── Judge API Endpoints ───────────────────────────────────────────

@login_required
@require_POST
def api_run_code(request):
    """Run code against sample test cases only (quick feedback)."""
    data = json.loads(request.body)
    problem = get_object_or_404(Problem, slug=data['slug'], user=request.user)

    sample_tests = problem.test_cases.filter(is_sample=True)
    if not sample_tests.exists():
        return JsonResponse({'error': 'No sample test cases defined.'}, status=400)

    job_id = str(uuid.uuid4())

    job = {
        'job_id': job_id,
        'solution_id': None,  # Not saved — just a quick run
        'language': data.get('language', 'cpp'),
        'code': data['code'],
        'test_cases': [
            {
                'id': str(tc.id),
                'input': tc.input_data,
                'expected': tc.expected_output,
                'time_limit_ms': tc.time_limit_ms,
                'memory_limit_mb': tc.memory_limit_mb,
            }
            for tc in sample_tests
        ],
        'config': {
            'iterations': 5,  # Quick run — fewer iterations
            'collect_perf': False,
            'compiler_flags': data.get('compiler_flags', '-O2 -std=c++20'),
            'custom_flags': data.get('custom_flags', ''),
        }
    }

    if redis_client:
        redis_client.lpush('judge:queue', json.dumps(job))

    return JsonResponse({'job_id': job_id})


@login_required
@require_POST
def api_submit_code(request):
    """Submit code against all test cases — saves solution and runs full judge."""
    data = json.loads(request.body)
    problem = get_object_or_404(Problem, slug=data['slug'], user=request.user)

    language = data.get('language', 'cpp')

    # Auto-increment version
    latest_version = Solution.objects.filter(
        problem=problem, language=language
    ).aggregate(Max('version'))['version__max'] or 0

    solution = Solution.objects.create(
        problem=problem,
        language=language,
        version=latest_version + 1,
        code=data['code'],
        notes=data.get('notes', ''),
        compiler_flags=data.get('compiler_flags', '-O2 -std=c++20'),
        custom_flags=data.get('custom_flags', ''),
    )

    all_tests = problem.test_cases.all()
    if not all_tests.exists():
        return JsonResponse({'error': 'No test cases defined for this problem.'}, status=400)

    job_id = str(uuid.uuid4())

    job = {
        'job_id': job_id,
        'solution_id': str(solution.id),
        'language': language,
        'code': data['code'],
        'test_cases': [
            {
                'id': str(tc.id),
                'input': tc.input_data,
                'expected': tc.expected_output,
                'time_limit_ms': tc.time_limit_ms,
                'memory_limit_mb': tc.memory_limit_mb,
            }
            for tc in all_tests
        ],
        'config': {
            'iterations': int(data.get('iterations', 200)),
            'collect_perf': True,
            'compiler_flags': data.get('compiler_flags', '-O2 -std=c++20'),
            'custom_flags': data.get('custom_flags', ''),
        }
    }

    if redis_client:
        redis_client.lpush('judge:queue', json.dumps(job))

    return JsonResponse({
        'job_id': job_id,
        'solution_id': str(solution.id),
        'version': solution.version,
    })


@login_required
def judge_poll_status(request, job_id):
    """AJAX polling endpoint — returns judge result if available."""
    if not redis_client:
        return JsonResponse({'status': 'error', 'message': 'Redis unavailable'}, status=503)

    result = redis_client.get(f'judge:result:{job_id}')
    if result:
        return JsonResponse({
            'status': 'completed',
            'result': json.loads(result.decode()),
        })

    return JsonResponse({'status': 'pending'})
