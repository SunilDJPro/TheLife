"""
Judge daemon — dequeues jobs from Redis, compiles, runs, collects results.

Usage:
    python manage.py run_judge

Designed to run as a systemd service, started manually each morning.
"""
import json
import os
import shutil
import signal
import sys
import tempfile

import redis
from django.core.management.base import BaseCommand
from django.conf import settings

from compute_mastery.judge.compiler import compile_cpp
from compute_mastery.judge.runner import run_test_case
from compute_mastery.models import Solution, JudgeResult, TestCase
from compute_mastery.llm import analyze_solution
from compute_mastery.activity_sync import create_activity_from_submission


JUDGE_WORK_DIR = os.path.join(tempfile.gettempdir(), 'mastery_judge')
RESULT_EXPIRY = 3600  # Redis key TTL in seconds


class Command(BaseCommand):
    help = 'Run the Compute Mastery judge daemon (listens on Redis queue)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.running = True

    def add_arguments(self, parser):
        parser.add_argument(
            '--queue', default='judge:queue',
            help='Redis queue key (default: judge:queue)',
        )

    def handle(self, *args, **options):
        queue_key = options['queue']
        redis_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
        rc = redis.Redis.from_url(redis_url)

        # Verify Redis connection
        try:
            rc.ping()
        except redis.ConnectionError:
            self.stderr.write(self.style.ERROR('Cannot connect to Redis. Exiting.'))
            sys.exit(1)

        # Ensure work directory exists
        os.makedirs(JUDGE_WORK_DIR, exist_ok=True)

        # Graceful shutdown on SIGTERM/SIGINT
        def _shutdown(signum, frame):
            self.stdout.write(self.style.WARNING('\nShutting down judge daemon...'))
            self.running = False

        signal.signal(signal.SIGTERM, _shutdown)
        signal.signal(signal.SIGINT, _shutdown)

        self.stdout.write(self.style.SUCCESS(
            f'Judge daemon started — listening on "{queue_key}"'
        ))

        while self.running:
            # Blocking pop with 5s timeout so we can check self.running
            item = rc.brpop(queue_key, timeout=5)
            if item is None:
                continue

            _, raw = item
            try:
                job = json.loads(raw)
            except json.JSONDecodeError as e:
                self.stderr.write(self.style.ERROR(f'Bad job JSON: {e}'))
                continue

            job_id = job.get('job_id', '?')
            self.stdout.write(f'[{job_id}] Processing job...')

            try:
                result = self._process_job(job)
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'[{job_id}] Unhandled error: {e}'))
                result = {'compile_error': None, 'test_results': [],
                          'timing': None, 'perf': None,
                          'error': str(e)}

            # Push result to Redis (frontend gets this immediately)
            rc.set(f'judge:result:{job_id}', json.dumps(result), ex=RESULT_EXPIRY)

            # Update DB if this was a full submission
            solution_id = job.get('solution_id')
            if solution_id:
                try:
                    self._update_db(solution_id, job, result)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f'[{job_id}] DB update failed: {e}'
                    ))

                # ── AI Analysis (async — runs after result is already available) ──
                try:
                    solution = Solution.objects.select_related('problem').get(id=solution_id)
                    self.stdout.write(f'[{job_id}] Running AI analysis...')
                    analysis = analyze_solution(
                        solution,
                        timing_data=result.get('timing'),
                        perf_data=result.get('perf'),
                    )
                    # Update Redis result with analysis so frontend can poll for it
                    result['llm_analysis'] = analysis
                    rc.set(f'judge:result:{job_id}', json.dumps(result), ex=RESULT_EXPIRY)
                    self.stdout.write(f'[{job_id}] AI analysis complete.')
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f'[{job_id}] AI analysis failed: {e}'
                    ))

                # ── Activity Log ─────────────────────────────────────
                try:
                    solution = Solution.objects.select_related(
                        'problem', 'problem__user'
                    ).get(id=solution_id)
                    create_activity_from_submission(
                        solution,
                        timing_data=result.get('timing'),
                        perf_data=result.get('perf'),
                        llm_verdict=result.get('llm_analysis'),
                    )
                    self.stdout.write(f'[{job_id}] Activity logged.')
                except Exception as e:
                    self.stderr.write(self.style.ERROR(
                        f'[{job_id}] Activity sync failed: {e}'
                    ))

            status = 'OK' if not result.get('compile_error') and not result.get('error') else 'FAIL'
            self.stdout.write(f'[{job_id}] Done — {status}')

        self.stdout.write(self.style.SUCCESS('Judge daemon stopped.'))

    # ── Core processing ──────────────────────────────────────────

    def _process_job(self, job):
        """Compile, run all test cases, aggregate results."""
        job_id = job['job_id']
        code = job['code']
        language = job.get('language', 'cpp')
        test_cases = job.get('test_cases', [])
        config = job.get('config', {})

        iterations = config.get('iterations', 5)
        collect_perf = config.get('collect_perf', False)
        compiler_flags = config.get('compiler_flags', '-O2 -std=c++20')
        custom_flags = config.get('custom_flags', '')

        # Per-job working directory
        work_dir = os.path.join(JUDGE_WORK_DIR, job_id)
        os.makedirs(work_dir, exist_ok=True)

        try:
            # ── Compile ──────────────────────────────────────────
            if language == 'cpp':
                binary_path, compile_err = compile_cpp(
                    code, work_dir, compiler_flags, custom_flags)
            else:
                return {'compile_error': f'Unsupported language: {language}',
                        'test_results': [], 'timing': None, 'perf': None}

            if compile_err:
                return {'compile_error': compile_err,
                        'test_results': [], 'timing': None, 'perf': None}

            # ── Run each test case ───────────────────────────────
            test_results = []
            all_accepted = True

            for tc in test_cases:
                tr = run_test_case(
                    binary_path=binary_path,
                    input_data=tc['input'],
                    expected_output=tc['expected'],
                    time_limit_ms=tc.get('time_limit_ms', 2000),
                    memory_limit_mb=tc.get('memory_limit_mb', 256),
                    iterations=iterations,
                    collect_perf=collect_perf,
                    work_dir=work_dir,
                )
                tr['test_id'] = tc.get('id')
                test_results.append(tr)

                if tr['status'] != 'accepted':
                    all_accepted = False
                    # On failure during quick run, skip remaining tests
                    if not collect_perf:
                        break

            # ── Aggregate timing ─────────────────────────────────
            timing = self._aggregate_timing(test_results)

            # ── Aggregate perf ───────────────────────────────────
            perf = self._aggregate_perf(test_results) if collect_perf else None

            return {
                'compile_error': None,
                'test_results': test_results,
                'timing': timing,
                'perf': perf,
            }

        finally:
            # Clean up work directory
            shutil.rmtree(work_dir, ignore_errors=True)

    def _aggregate_timing(self, test_results):
        """Aggregate timing across all accepted test cases."""
        medians = []
        mins = []
        maxs = []
        variances = []

        for tr in test_results:
            if tr.get('median_time_us') is not None:
                medians.append(tr['median_time_us'])
            if tr.get('min_time_us') is not None:
                mins.append(tr['min_time_us'])
            if tr.get('max_time_us') is not None:
                maxs.append(tr['max_time_us'])
            if tr.get('std_dev_us') is not None:
                variances.append(tr['std_dev_us'] ** 2)

        if not medians:
            return None

        import math
        return {
            'median_us': round(sum(medians), 2),
            'min_us': round(sum(mins), 2) if mins else None,
            'max_us': round(sum(maxs), 2) if maxs else None,
            'std_dev_us': round(math.sqrt(sum(variances)), 2) if variances else None,
        }

    def _aggregate_perf(self, test_results):
        """Sum perf counters across all test cases, recompute IPC."""
        totals = {
            'instructions': 0,
            'cycles': 0,
            'cache_misses': 0,
            'branch_misses': 0,
            'context_switches': 0,
            'ipc': None,
        }

        has_perf = False
        for tr in test_results:
            p = tr.get('perf')
            if not p:
                continue
            has_perf = True
            for key in ('instructions', 'cycles', 'cache_misses',
                        'branch_misses', 'context_switches'):
                if p.get(key) is not None:
                    totals[key] += p[key]

        if not has_perf:
            return None

        if totals['instructions'] and totals['cycles']:
            totals['ipc'] = round(totals['instructions'] / totals['cycles'], 4)

        return totals

    # ── DB updates ───────────────────────────────────────────────

    def _update_db(self, solution_id, job, result):
        """Update Solution record and create JudgeResult entries."""
        try:
            solution = Solution.objects.get(id=solution_id)
        except Solution.DoesNotExist:
            self.stderr.write(f'Solution {solution_id} not found — skipping DB update')
            return

        # Handle compile errors
        if result.get('compile_error'):
            solution.is_accepted = False
            solution.save(update_fields=['is_accepted'])

            JudgeResult.objects.create(
                solution=solution,
                test_case=None,
                status='compile_error',
                stderr_output=result['compile_error'],
            )
            return

        # Per-test results
        all_accepted = True
        test_results = result.get('test_results', [])

        for tr in test_results:
            test_case = None
            tc_id = tr.get('test_id')
            if tc_id:
                try:
                    test_case = TestCase.objects.get(id=tc_id)
                except TestCase.DoesNotExist:
                    pass

            perf = tr.get('perf') or {}

            JudgeResult.objects.create(
                solution=solution,
                test_case=test_case,
                status=tr['status'],
                actual_output=tr.get('actual_output', ''),
                stderr_output=tr.get('stderr_output', ''),
                wall_times_us=tr.get('wall_times_us', []),
                median_time_us=tr.get('median_time_us'),
                min_time_us=tr.get('min_time_us'),
                max_time_us=tr.get('max_time_us'),
                std_dev_us=tr.get('std_dev_us'),
                instructions=perf.get('instructions'),
                cycles=perf.get('cycles'),
                cache_misses=perf.get('cache_misses'),
                branch_misses=perf.get('branch_misses'),
                ipc=perf.get('ipc'),
                context_switches=perf.get('context_switches'),
            )

            if tr['status'] != 'accepted':
                all_accepted = False

        # Update denormalized fields on Solution
        solution.is_accepted = all_accepted

        agg_timing = result.get('timing')
        if agg_timing:
            solution.median_runtime_us = agg_timing.get('median_us')

        agg_perf = result.get('perf')
        if agg_perf:
            solution.perf_counters = agg_perf

        solution.save(update_fields=[
            'is_accepted', 'median_runtime_us', 'perf_counters',
        ])
