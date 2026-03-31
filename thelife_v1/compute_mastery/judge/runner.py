"""Solution execution, timing collection, and perf counter parsing."""
import os
import subprocess
import statistics
import time

WARMUP_ITERATIONS = 3


def run_test_case(binary_path, input_data, expected_output,
                  time_limit_ms=2000, memory_limit_mb=256,
                  iterations=1, collect_perf=False, work_dir='/tmp'):
    """
    Run binary against a single test case.

    1. Correctness check (single run)
    2. Timing runs (warmup + measured iterations)
    3. Optional perf stat collection

    Returns a dict matching the frontend's per-test result schema.
    """
    time_limit_s = time_limit_ms / 1000.0
    cmd = [binary_path]

    # ── Correctness check ────────────────────────────────────────
    try:
        proc = subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=time_limit_s * 2,  # generous for first run
        )
    except subprocess.TimeoutExpired:
        return _error_result('time_limit',
                             stderr=f'Time limit exceeded ({time_limit_ms}ms)')

    if proc.returncode != 0:
        return _error_result('runtime_error',
                             actual=proc.stdout, stderr=proc.stderr)

    actual_output = proc.stdout

    # Compare (strip trailing whitespace per line, ignore trailing newline)
    if not _outputs_match(actual_output, expected_output):
        return {
            'status': 'wrong_answer',
            'actual_output': actual_output,
            'expected': expected_output,
            'stderr_output': proc.stderr,
            'wall_times_us': [],
            'median_time_us': None, 'min_time_us': None,
            'max_time_us': None, 'std_dev_us': None,
            'perf': None,
        }

    # ── Timing runs ──────────────────────────────────────────────
    wall_times_us = []

    # Warmup
    for _ in range(min(WARMUP_ITERATIONS, iterations)):
        try:
            subprocess.run(cmd, input=input_data, capture_output=True,
                           text=True, timeout=time_limit_s)
        except Exception:
            pass

    # Measured runs
    for _ in range(iterations):
        start = time.perf_counter_ns()
        try:
            subprocess.run(cmd, input=input_data, capture_output=True,
                           text=True, timeout=time_limit_s)
            elapsed_us = (time.perf_counter_ns() - start) / 1000.0
            wall_times_us.append(elapsed_us)
        except subprocess.TimeoutExpired:
            wall_times_us.append(time_limit_ms * 1000.0)

    timing = _compute_timing(wall_times_us)

    # ── Perf counters ────────────────────────────────────────────
    perf_data = None
    if collect_perf:
        perf_data = _collect_perf(binary_path, input_data, time_limit_s, work_dir)

    return {
        'status': 'accepted',
        'actual_output': actual_output,
        'expected': expected_output,
        'stderr_output': '',
        'wall_times_us': wall_times_us,
        **timing,
        'perf': perf_data,
    }


# ── Helpers ──────────────────────────────────────────────────────

def _outputs_match(actual, expected):
    """Compare outputs: strip trailing whitespace per line, ignore trailing newlines."""
    actual_lines = [line.rstrip() for line in actual.rstrip('\n').split('\n')]
    expected_lines = [line.rstrip() for line in expected.rstrip('\n').split('\n')]
    return actual_lines == expected_lines


def _error_result(status, actual='', stderr=''):
    return {
        'status': status,
        'actual_output': actual,
        'stderr_output': stderr,
        'wall_times_us': [],
        'median_time_us': None, 'min_time_us': None,
        'max_time_us': None, 'std_dev_us': None,
        'perf': None,
    }


def _compute_timing(wall_times_us):
    if not wall_times_us:
        return {
            'median_time_us': None, 'min_time_us': None,
            'max_time_us': None, 'std_dev_us': None,
        }
    return {
        'median_time_us': round(statistics.median(wall_times_us), 2),
        'min_time_us': round(min(wall_times_us), 2),
        'max_time_us': round(max(wall_times_us), 2),
        'std_dev_us': round(statistics.stdev(wall_times_us), 2) if len(wall_times_us) > 1 else 0.0,
    }


def _collect_perf(binary_path, input_data, timeout_s, work_dir):
    """Run once with `perf stat` and parse hardware counters."""
    perf_file = os.path.join(work_dir, 'perf_out.csv')

    try:
        cmd = [
            'perf', 'stat',
            '-e', 'instructions,cycles,cache-misses,branch-misses,context-switches',
            '-x', ',',
            '-o', perf_file,
            '--', binary_path,
        ]
        subprocess.run(
            cmd,
            input=input_data,
            capture_output=True,
            text=True,
            timeout=timeout_s * 3,
        )

        with open(perf_file, 'r') as f:
            return _parse_perf(f.read())
    except Exception:
        return None


def _parse_perf(text):
    """
    Parse perf stat CSV output (-x ',').

    Typical line format:
        12345678,,instructions,1234567,100.00,,
    """
    counters = {
        'instructions': None,
        'cycles': None,
        'cache_misses': None,
        'branch_misses': None,
        'context_switches': None,
        'ipc': None,
    }

    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        parts = line.split(',')
        if len(parts) < 3:
            continue

        raw_value = parts[0].strip()
        event = parts[2].strip() if len(parts) > 2 else ''

        try:
            value = int(raw_value)
        except (ValueError, TypeError):
            continue

        if 'instructions' in event:
            counters['instructions'] = value
        elif 'cycles' == event or (event.endswith('cycles') and 'cache' not in event):
            counters['cycles'] = value
        elif 'cache-misses' in event:
            counters['cache_misses'] = value
        elif 'branch-misses' in event:
            counters['branch_misses'] = value
        elif 'context-switches' in event:
            counters['context_switches'] = value

    # Compute IPC
    if counters['instructions'] and counters['cycles']:
        counters['ipc'] = round(counters['instructions'] / counters['cycles'], 4)

    return counters
