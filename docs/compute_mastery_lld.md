# Compute Mastery — Low-Level Design Document

## 1. Context

This document describes the **Compute Mastery** module to be added to **TheLife** — an existing Django SSR application used for daily activity tracking with local LLM analysis. Compute Mastery is a LeetCode-style coding environment purpose-built for deep performance analysis, supporting **C++**, **Rust**, and **Verilog/HDL** (hardware playground). The system is **self-hosted** on a dedicated machine.

The goal is NOT just correctness checking — it is to enable studying low-level optimization: pragmas, concurrency primitives, register utilization, cache behavior — by comparing multiple solution versions of the same problem with deterministic, low-noise measurements.

---

## 2. Data Models

All models live under a new Django app: `compute_mastery`.

### 2.1 Problem

```python
class Problem(models.Model):
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    description = models.TextField()  # Markdown-formatted problem statement
    difficulty = models.CharField(
        max_length=10,
        choices=[("easy", "Easy"), ("medium", "Medium"), ("hard", "Hard")]
    )
    tags = models.ManyToManyField("Tag", blank=True)
    category = models.CharField(
        max_length=20,
        choices=[
            ("algorithm", "Algorithm"),       # Standard DSA problems
            ("systems", "Systems"),            # Concurrency, OS-level
            ("hardware", "Hardware"),          # Verilog/HDL
        ],
        default="algorithm"
    )
    constraints = models.TextField(blank=True)  # Input constraints as text
    hints = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Template code per language — stored as JSON: {"cpp": "...", "rust": "...", "verilog": "..."}
    # Only relevant languages populated per problem
    starter_code = models.JSONField(default=dict)

    # Optional: reference solution (encrypted/hidden from UI, used by LLM analysis)
    reference_solution = models.JSONField(default=dict, blank=True)
```

### 2.2 Tag

```python
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)  # e.g., "dp", "pragma", "simd", "concurrency", "combinational"
    slug = models.SlugField(unique=True)
```

### 2.3 TestCase

```python
class TestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="test_cases")
    input_data = models.TextField()       # Raw stdin input
    expected_output = models.TextField()   # Expected stdout output
    is_sample = models.BooleanField(default=False)  # Visible in problem statement
    order = models.PositiveIntegerField(default=0)
    time_limit_ms = models.PositiveIntegerField(default=2000)   # Per-test override
    memory_limit_mb = models.PositiveIntegerField(default=256)  # Per-test override

    class Meta:
        ordering = ["order"]
```

**For Verilog/HDL problems**, the test case model is extended:

```python
class HDLTestCase(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="hdl_test_cases")
    testbench_code = models.TextField()     # Verilog testbench that instantiates the user's module
    expected_waveform = models.JSONField(default=dict, blank=True)  # signal->value mappings per cycle
    expected_output = models.TextField(blank=True)  # $display output to match
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]
```

### 2.4 Solution (Versioned)

Each solution is an immutable snapshot. Multiple versions per problem per language.

```python
class Solution(models.Model):
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name="solutions")
    language = models.CharField(
        max_length=10,
        choices=[("cpp", "C++"), ("rust", "Rust"), ("verilog", "Verilog")]
    )
    version = models.PositiveIntegerField()  # Auto-incremented per (problem, language)
    code = models.TextField()
    notes = models.TextField(blank=True)  # User notes: "Added SIMD", "Tried lock-free queue"
    created_at = models.DateTimeField(auto_now_add=True)

    # Denormalized latest run results for quick display
    is_accepted = models.BooleanField(null=True)
    median_runtime_us = models.FloatField(null=True)       # Microseconds
    peak_memory_kb = models.PositiveIntegerField(null=True)
    perf_counters = models.JSONField(default=dict, blank=True)  # Snapshot of best run's counters

    class Meta:
        unique_together = ["problem", "language", "version"]
        ordering = ["-version"]
```

### 2.5 JudgeResult

Detailed per-test-case results for a solution run.

```python
class JudgeResult(models.Model):
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name="results")
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, null=True, blank=True)
    hdl_test_case = models.ForeignKey(HDLTestCase, on_delete=models.CASCADE, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("accepted", "Accepted"),
            ("wrong_answer", "Wrong Answer"),
            ("time_limit", "Time Limit Exceeded"),
            ("memory_limit", "Memory Limit Exceeded"),
            ("runtime_error", "Runtime Error"),
            ("compile_error", "Compile Error"),
        ]
    )
    actual_output = models.TextField(blank=True)
    stderr_output = models.TextField(blank=True)

    # Timing — collected over N iterations, stored as list for analysis
    wall_times_us = models.JSONField(default=list)   # All iteration times
    median_time_us = models.FloatField(null=True)
    min_time_us = models.FloatField(null=True)
    max_time_us = models.FloatField(null=True)
    std_dev_us = models.FloatField(null=True)

    # perf stat counters
    instructions = models.BigIntegerField(null=True)
    cycles = models.BigIntegerField(null=True)
    cache_misses = models.BigIntegerField(null=True)
    branch_misses = models.BigIntegerField(null=True)
    ipc = models.FloatField(null=True)  # Instructions per cycle
    context_switches = models.PositiveIntegerField(null=True)

    # Memory
    peak_memory_kb = models.PositiveIntegerField(null=True)

    created_at = models.DateTimeField(auto_now=True)
```

---

## 3. Judge Service

The judge is a **standalone daemon process**, NOT part of Django. Django communicates with it via a **Redis task queue**.

### 3.1 Architecture

```
Django View                Redis Queue              Judge Daemon
    │                          │                         │
    ├── submit solution ──────>│                         │
    │   (enqueue job)          ├── dequeue ─────────────>│
    │                          │                         ├── compile
    │                          │                         ├── run on isolated core
    │                          │                         ├── collect perf counters
    │                          │                         ├── compare output
    │   <──────────────────────│<── push result ─────────┤
    │   (poll or SSE)          │                         │
```

### 3.2 Job Schema

Enqueued by Django into Redis:

```json
{
    "job_id": "uuid4",
    "solution_id": 42,
    "language": "cpp",
    "code": "...",
    "test_cases": [
        {"id": 1, "input": "6\nabcdba\ncabdab", "expected": "true", "time_limit_ms": 2000, "memory_limit_mb": 256}
    ],
    "config": {
        "iterations": 200,
        "collect_perf": true,
        "compiler_flags": "-O2 -std=c++20",
        "custom_flags": "-march=native -fopenmp"
    }
}
```

For HDL jobs:

```json
{
    "job_id": "uuid4",
    "solution_id": 42,
    "language": "verilog",
    "code": "...",
    "hdl_test_cases": [
        {"id": 1, "testbench": "...", "expected_output": "PASS"}
    ],
    "config": {
        "simulator": "verilator"
    }
}
```

### 3.3 Judge Daemon Implementation

The daemon is written in **Python** (for simplicity with Django ecosystem) but shells out to compilers natively. Located at `judge/daemon.py` — run as a systemd service.

```
judge/
├── daemon.py          # Main loop: dequeue from Redis, dispatch
├── compilers/
│   ├── cpp.py         # g++/clang++ compilation
│   ├── rust.py        # rustc compilation
│   └── verilog.py     # verilator / iverilog compilation + simulation
├── runner.py          # Execute binary with taskset + perf, collect results
├── sandbox.py         # cgroups + seccomp setup
└── config.py          # Paths, isolated core IDs, iteration counts
```

#### 3.3.1 Compilation Step

**C++:**
```bash
g++ -O2 -std=c++20 -o /tmp/judge/{job_id}/solution {custom_flags} solution.cpp
```
- Allow user-controlled flags like `-march=native`, `-fopenmp`, `-mavx2`, `#pragma` directives in code
- Compile timeout: 30 seconds
- Capture stderr for compile errors

**Rust:**
```bash
rustc --edition 2021 -O -o /tmp/judge/{job_id}/solution solution.rs
```

**Verilog:**
```bash
verilator --cc --exe --build -Wall user_module.v testbench.cpp -o /tmp/judge/{job_id}/simulation
# OR for simpler cases:
iverilog -o /tmp/judge/{job_id}/simulation user_module.v testbench.v
```

#### 3.3.2 Execution Step — The Core of Low-Noise Timing

This is the critical differentiator. The runner performs:

**Step A — Pre-run setup (done once at daemon startup / system boot):**

```bash
# 1. Isolate CPUs 2,3 from the OS scheduler (set in /etc/default/grub, reboot once)
GRUB_CMDLINE_LINUX="isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3"

# 2. Lock CPU frequency (no turbo, no scaling)
echo performance | tee /sys/devices/system/cpu/cpu2/cpufreq/scaling_governor
echo performance | tee /sys/devices/system/cpu/cpu3/cpufreq/scaling_governor
echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo  # Intel
# OR for AMD:
echo 0 > /sys/devices/system/cpu/cpufreq/boost

# 3. Disable hyperthreading on judge cores (if sibling is core 6,7)
echo 0 > /sys/devices/system/cpu/cpu6/online
echo 0 > /sys/devices/system/cpu/cpu7/online
```

**Step B — Per-execution (for each test case, repeated N iterations):**

```bash
# Run with CPU pinning + perf counters
taskset -c 2 perf stat -e instructions,cycles,cache-misses,branch-misses,context-switches \
    -x ',' -o /tmp/judge/{job_id}/perf_out.csv \
    /tmp/judge/{job_id}/solution < input.txt > output.txt 2> stderr.txt
```

**Step C — Timing collection strategy:**

```python
# runner.py pseudocode
def run_solution(binary_path, input_data, iterations, time_limit_ms):
    times = []

    # Warmup: 3 runs, discard results (prime caches)
    for _ in range(3):
        run_once(binary_path, input_data, time_limit_ms)

    # Measured runs
    for i in range(iterations):
        start = time.perf_counter_ns()
        result = run_once(binary_path, input_data, time_limit_ms)
        elapsed_us = (time.perf_counter_ns() - start) / 1000

        if result.timeout or result.error:
            return error_result(result)

        times.append(elapsed_us)

    # Perf counters from the last run (deterministic — same every run)
    perf = parse_perf_output("/tmp/judge/{job_id}/perf_out.csv")

    return {
        "wall_times_us": times,
        "median_us": statistics.median(times),
        "min_us": min(times),
        "max_us": max(times),
        "std_dev_us": statistics.stdev(times),
        "instructions": perf["instructions"],
        "cycles": perf["cycles"],
        "cache_misses": perf["cache-misses"],
        "branch_misses": perf["branch-misses"],
        "ipc": perf["instructions"] / perf["cycles"],
        "context_switches": perf["context-switches"],
    }
```

**For Verilog/HDL**, timing is not the focus — correctness is. The runner simply:
1. Runs the simulation binary
2. Captures `$display` / `$monitor` output
3. Compares against expected output or waveform values
4. Optionally generates a VCD waveform file for UI display

#### 3.3.3 Sandbox / Security

Even on a single-user self-hosted system, sandboxing prevents accidental damage:

```python
# sandbox.py
def create_sandbox(job_id):
    """
    Uses cgroups v2 to limit:
    - memory.max = 512MB (configurable per test)
    - cpu.max = time_limit * 1.5 (hard kill)
    - pids.max = 64 (prevent fork bombs)

    Uses seccomp to block:
    - execve (no spawning shells from solution)
    - network syscalls (no socket, connect, bind)
    - filesystem writes outside /tmp/judge/{job_id}/
    """
    cgroup_path = f"/sys/fs/cgroup/judge/{job_id}"
    os.makedirs(cgroup_path, exist_ok=True)

    write(f"{cgroup_path}/memory.max", str(memory_limit_mb * 1024 * 1024))
    write(f"{cgroup_path}/pids.max", "64")

    return cgroup_path
```

#### 3.3.4 Result Delivery

The judge daemon pushes results back to Redis:

```python
# daemon.py
redis_client.publish(f"judge:result:{job_id}", json.dumps(result))
# Also store persistently:
redis_client.set(f"judge:result:{job_id}", json.dumps(result), ex=3600)
```

Django consumes this via:
- **Polling**: AJAX endpoint that checks `redis.get(f"judge:result:{job_id}")`
- **SSE (preferred)**: Django view that subscribes to the Redis channel and streams to browser

---

## 4. Django Views & URL Structure

All under `/mastery/` prefix.

### 4.1 URL Patterns

```python
# compute_mastery/urls.py
urlpatterns = [
    # Problem browsing
    path("", views.problem_list, name="mastery_home"),
    path("problem/<slug:slug>/", views.problem_detail, name="problem_detail"),

    # Problem management (CRUD)
    path("problem/new/", views.problem_create, name="problem_create"),
    path("problem/<slug:slug>/edit/", views.problem_edit, name="problem_edit"),
    path("problem/<slug:slug>/test-cases/", views.test_case_manage, name="test_case_manage"),

    # Solution & judge
    path("problem/<slug:slug>/submit/", views.solution_submit, name="solution_submit"),
    path("problem/<slug:slug>/solutions/", views.solution_list, name="solution_list"),
    path("problem/<slug:slug>/solutions/compare/", views.solution_compare, name="solution_compare"),

    # Judge result stream
    path("judge/status/<uuid:job_id>/", views.judge_status_sse, name="judge_status"),

    # API endpoints for AJAX (editor interactions)
    path("api/run/", views.api_run_code, name="api_run"),          # Run against sample tests only
    path("api/submit/", views.api_submit_code, name="api_submit"), # Run against all tests + save
]
```

### 4.2 Key Views

#### Problem List (mastery_home)
- Filterable by difficulty, tags, category (algorithm/systems/hardware)
- Shows solve status, best runtime, version count per problem
- SSR template with optional HTMX for filter interactions

#### Problem Detail (problem_detail)
- Left panel: problem statement (rendered Markdown), sample test cases, constraints
- Right panel: code editor (see Section 5), language selector
- Bottom panel: test results, timing, perf counters

#### Solution Submit Flow

```python
# views.py
def api_submit_code(request):
    data = json.loads(request.body)
    problem = get_object_or_404(Problem, slug=data["slug"])

    # Auto-increment version
    latest_version = Solution.objects.filter(
        problem=problem, language=data["language"]
    ).aggregate(Max("version"))["version__max"] or 0

    solution = Solution.objects.create(
        problem=problem,
        language=data["language"],
        version=latest_version + 1,
        code=data["code"],
        notes=data.get("notes", ""),
    )

    # Determine test cases based on category
    if problem.category == "hardware":
        test_cases = [
            {"id": tc.id, "testbench": tc.testbench_code, "expected_output": tc.expected_output}
            for tc in problem.hdl_test_cases.all()
        ]
        job_key = "hdl_test_cases"
    else:
        test_cases = [
            {
                "id": tc.id,
                "input": tc.input_data,
                "expected": tc.expected_output,
                "time_limit_ms": tc.time_limit_ms,
                "memory_limit_mb": tc.memory_limit_mb,
            }
            for tc in problem.test_cases.all()
        ]
        job_key = "test_cases"

    job_id = str(uuid4())
    redis_client.lpush("judge:queue", json.dumps({
        "job_id": job_id,
        "solution_id": solution.id,
        "language": data["language"],
        "code": data["code"],
        job_key: test_cases,
        "config": {
            "iterations": 200,
            "collect_perf": True,
            "compiler_flags": data.get("compiler_flags", "-O2 -std=c++20"),
            "custom_flags": data.get("custom_flags", ""),
        }
    }))

    return JsonResponse({"job_id": job_id, "solution_id": solution.id})
```

#### Solution Compare View

```python
def solution_compare(request, slug):
    """Compare 2 or more solution versions side-by-side."""
    problem = get_object_or_404(Problem, slug=slug)
    version_ids = request.GET.getlist("v")  # e.g., ?v=3&v=5&v=7

    solutions = Solution.objects.filter(
        problem=problem, id__in=version_ids
    ).prefetch_related("results")

    # Build comparison data: code diff + perf diff
    comparison = []
    for sol in solutions:
        best_result = sol.results.filter(status="accepted").first()
        comparison.append({
            "solution": sol,
            "code": sol.code,
            "perf": {
                "median_us": best_result.median_time_us if best_result else None,
                "instructions": best_result.instructions if best_result else None,
                "cache_misses": best_result.cache_misses if best_result else None,
                "branch_misses": best_result.branch_misses if best_result else None,
                "ipc": best_result.ipc if best_result else None,
            }
        })

    return render(request, "compute_mastery/compare.html", {
        "problem": problem,
        "comparison": comparison,
    })
```

#### SSE Endpoint for Live Results

```python
import redis
from django.http import StreamingHttpResponse

def judge_status_sse(request, job_id):
    """Server-Sent Events stream for judge results."""
    def event_stream():
        r = redis.Redis()
        pubsub = r.pubsub()
        pubsub.subscribe(f"judge:result:{job_id}")

        # Check if result already exists
        existing = r.get(f"judge:result:{job_id}")
        if existing:
            yield f"data: {existing.decode()}\n\n"
            return

        # Wait for result with timeout
        for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data'].decode()}\n\n"
                break

    return StreamingHttpResponse(
        event_stream(),
        content_type="text/event-stream"
    )
```

---

## 5. Frontend — Code Editor Integration

### 5.1 Editor Choice: CodeMirror 6

Embedded in Django SSR templates via CDN. CodeMirror 6 is modular, lightweight, and has excellent language support.

```html
<!-- templates/compute_mastery/problem_detail.html -->

<!-- CodeMirror 6 via CDN -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/6.65.7/...">

<div id="editor-container">
    <div id="editor-toolbar">
        <select id="language-select">
            <option value="cpp">C++</option>
            <option value="rust">Rust</option>
            <option value="verilog">Verilog</option>
        </select>
        <select id="compiler-flags">
            <option value="-O0">-O0 (No optimization)</option>
            <option value="-O2" selected>-O2 (Standard)</option>
            <option value="-O3">-O3 (Aggressive)</option>
            <option value="-Ofast">-Ofast (Fast math)</option>
        </select>
        <input type="text" id="custom-flags" placeholder="Custom flags: -mavx2 -fopenmp">
        <button id="run-btn">Run (Samples)</button>
        <button id="submit-btn">Submit (All Tests)</button>
    </div>
    <div id="code-editor"></div>
</div>

<div id="results-panel">
    <div id="result-tabs">
        <button class="tab active" data-tab="output">Output</button>
        <button class="tab" data-tab="timing">Timing</button>
        <button class="tab" data-tab="perf">Perf Counters</button>
    </div>
    <div id="tab-content"></div>
</div>
```

### 5.2 Editor JavaScript

```javascript
// static/compute_mastery/editor.js

// Initialize CodeMirror 6 with language-specific mode
const editor = createCodeMirrorEditor({
    parent: document.getElementById("code-editor"),
    language: "cpp",  // switches with dropdown
    theme: "dark",    // match TheLife theme
    extensions: [
        lineNumbers(),
        bracketMatching(),
        autocompletion(),  // basic keyword completion
    ]
});

// Submit handler
document.getElementById("submit-btn").addEventListener("click", async () => {
    const response = await fetch("/mastery/api/submit/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken },
        body: JSON.stringify({
            slug: PROBLEM_SLUG,
            language: document.getElementById("language-select").value,
            code: editor.state.doc.toString(),
            compiler_flags: document.getElementById("compiler-flags").value,
            custom_flags: document.getElementById("custom-flags").value,
            notes: "",  // Optional: prompt user
        })
    });

    const { job_id } = await response.json();
    listenForResults(job_id);
});

// SSE listener for judge results
function listenForResults(jobId) {
    showLoadingState();
    const source = new EventSource(`/mastery/judge/status/${jobId}/`);

    source.onmessage = (event) => {
        const result = JSON.parse(event.data);
        source.close();
        renderResults(result);
    };

    source.onerror = () => {
        source.close();
        showError("Judge connection lost. Retrying...");
        // Fallback: poll via AJAX
    };
}
```

### 5.3 Results Display

#### Timing Tab
```
Median: 142 μs | Min: 138 μs | Max: 167 μs | Std Dev: 4.2 μs
Distribution: [histogram of wall_times_us array]
```

#### Perf Counters Tab
```
Instructions:    1,247,832
Cycles:            892,441
IPC:                  1.40
Cache Misses:        1,204
Branch Misses:         87
Context Switches:       0
```

#### Comparison View (when comparing versions)
```
                     v3 (baseline)    v5 (+SIMD)     v7 (+pragma unroll)
Median Time          142 μs           68 μs (-52%)   51 μs (-64%)
Instructions         1,247,832        623,104        498,882
IPC                  1.40             2.31           2.44
Cache Misses         1,204            312            298
```

---

## 6. Solution Versioning & Diff

### 6.1 Diff Generation

Diffs are computed on-the-fly using Python's `difflib`, not stored.

```python
# compute_mastery/utils.py
import difflib

def generate_diff(code_old, code_new):
    """Returns unified diff as HTML-safe string."""
    diff = difflib.unified_diff(
        code_old.splitlines(keepends=True),
        code_new.splitlines(keepends=True),
        fromfile="Previous Version",
        tofile="Current Version",
        lineterm=""
    )
    return list(diff)
```

### 6.2 Version Navigation

In the solution list view, each solution shows:
- Version number, timestamp, user notes
- Accept/reject status badge
- Quick stats: median time, instruction count
- Actions: View, Compare (checkbox to select 2+ for comparison), Re-run

The compare view shows:
- Side-by-side code with diff highlighting
- Side-by-side perf counter table
- Timing distribution overlay chart (histogram of both versions overlaid)

---

## 7. Verilog/HDL Playground

### 7.1 Simulator Backend

Two options based on complexity:

- **Icarus Verilog (iverilog)**: Simple, interprets Verilog. Good for combinational logic, basic sequential. Matches HDLBits style.
- **Verilator**: Compiles Verilog to C++, then runs. Much faster. Use for complex designs.

The judge auto-selects based on problem category or allows manual override.

### 7.2 Problem Structure for HDL

HDL problems differ from algorithm problems:
- No stdin/stdout — user writes a **module definition**
- The testbench is provided by the problem and instantiates the user's module
- Correctness is checked by the testbench's `$display` output or waveform comparison

Example problem structure:

```
Problem: "4-bit Ripple Carry Adder"
Starter Code (Verilog):
    module adder4(
        input  [3:0] a, b,
        input        cin,
        output [3:0] sum,
        output       cout
    );
        // Your code here
    endmodule

Testbench (hidden, part of HDLTestCase):
    module tb;
        reg [3:0] a, b;
        reg cin;
        wire [3:0] sum;
        wire cout;

        adder4 uut(.a(a), .b(b), .cin(cin), .sum(sum), .cout(cout));

        initial begin
            a=4'd3; b=4'd5; cin=0; #10;
            $display("sum=%d cout=%d", sum, cout);
            // ... more vectors
            $display("PASS");
        end
    endmodule
```

### 7.3 Waveform Viewer (Optional Enhancement)

If the simulation produces a VCD file:

```bash
iverilog -o sim design.v testbench.v
vvp sim  # produces dump.vcd
```

The VCD file can be rendered in-browser using a JavaScript waveform viewer like **WaveDrom** or a custom lightweight viewer.

---

## 8. LLM Analysis Integration

Since TheLife already has local LLM integration, Compute Mastery hooks into it for solution analysis.

### 8.1 Trigger Points

- **Post-submission**: After a solution is judged, optionally send the code + perf data to the LLM for analysis
- **Version comparison**: Send two versions' code + perf diffs for explanation of what changed and why
- **Learning log**: Auto-generate a learning entry in the daily tracker when a problem is solved

### 8.2 LLM Prompt Template

```python
ANALYSIS_PROMPT = """
Analyze this C++ solution for the problem "{problem_title}".

## Code
```{language}
{code}
```

## Performance Metrics
- Median runtime: {median_us} μs
- Instructions: {instructions}
- IPC: {ipc}
- Cache misses: {cache_misses}
- Branch mispredictions: {branch_misses}

## Compiler Flags Used
{compiler_flags} {custom_flags}

Provide:
1. Algorithm complexity analysis
2. Why the IPC is {high/low} for this workload
3. What the cache miss pattern suggests
4. Specific suggestions for optimization (pragma, SIMD, data layout)
5. Whether the compiler flags are appropriate
"""
```

### 8.3 Version Comparison Prompt

```python
COMPARE_PROMPT = """
Compare these two versions of solution for "{problem_title}".

## Version {v1_num} ({v1_notes})
```{language}
{v1_code}
```
Perf: {v1_median_us}μs | {v1_instructions} insn | IPC {v1_ipc} | {v1_cache_misses} cache misses

## Version {v2_num} ({v2_notes})
```{language}
{v2_code}
```
Perf: {v2_median_us}μs | {v2_instructions} insn | IPC {v2_ipc} | {v2_cache_misses} cache misses

Explain:
1. What changed between versions and the intent behind it
2. Why the performance changed the way it did
3. Which version is better and in what scenarios
4. What to try next for further improvement
"""
```

---

## 9. File & Directory Structure

```
thelife/                          # Existing Django project root
├── compute_mastery/              # New Django app
│   ├── models.py                 # Section 2 models
│   ├── views.py                  # Section 4 views
│   ├── urls.py                   # Section 4.1 URL patterns
│   ├── forms.py                  # Problem create/edit, test case management
│   ├── utils.py                  # Diff generation, perf data parsing
│   ├── admin.py                  # Admin for Problem, TestCase, Tag
│   ├── templatetags/
│   │   └── mastery_tags.py       # Custom tags: render_markdown, format_perf
│   ├── templates/
│   │   └── compute_mastery/
│   │       ├── problem_list.html
│   │       ├── problem_detail.html    # Editor + results panel
│   │       ├── problem_form.html      # Create/edit problem
│   │       ├── test_case_form.html
│   │       ├── solution_list.html
│   │       └── compare.html           # Side-by-side version comparison
│   ├── static/
│   │   └── compute_mastery/
│   │       ├── editor.js              # CodeMirror init + submit logic
│   │       ├── results.js             # SSE listener + result rendering
│   │       ├── compare.js             # Diff + perf chart rendering
│   │       └── styles.css
│   └── migrations/
│
├── judge/                         # Standalone judge daemon (NOT a Django app)
│   ├── daemon.py                  # Main loop: Redis dequeue, dispatch
│   ├── compilers/
│   │   ├── __init__.py
│   │   ├── cpp.py                 # g++/clang++ compilation
│   │   ├── rust.py                # rustc compilation
│   │   └── verilog.py             # iverilog/verilator compilation
│   ├── runner.py                  # taskset + perf execution, timing collection
│   ├── sandbox.py                 # cgroups + seccomp setup
│   ├── config.py                  # Isolated core IDs, iteration counts, paths
│   └── requirements.txt           # redis, psutil
│
├── systemd/
│   └── judge.service              # systemd unit file for judge daemon
│
└── scripts/
    └── setup_isolation.sh         # CPU isolation, governor, HT disable
```

---

## 10. System Setup Script

```bash
#!/bin/bash
# scripts/setup_isolation.sh
# Run once after boot, or add to rc.local

# === CPU Frequency: lock to max, no turbo ===
for cpu in 2 3; do
    echo performance > /sys/devices/system/cpu/cpu${cpu}/cpufreq/scaling_governor
done

# Intel: disable turbo
if [ -f /sys/devices/system/cpu/intel_pstate/no_turbo ]; then
    echo 1 > /sys/devices/system/cpu/intel_pstate/no_turbo
fi
# AMD: disable boost
if [ -f /sys/devices/system/cpu/cpufreq/boost ]; then
    echo 0 > /sys/devices/system/cpu/cpufreq/boost
fi

# === Disable HT siblings of isolated cores ===
# Find siblings: cat /sys/devices/system/cpu/cpu2/topology/thread_siblings_list
# Disable the sibling (adjust core numbers for your hardware)
# echo 0 > /sys/devices/system/cpu/cpu6/online
# echo 0 > /sys/devices/system/cpu/cpu7/online

# === Verify isolation ===
cat /sys/devices/system/cpu/isolated   # Should show: 2-3
echo "CPU isolation active on cores 2,3"
```

### GRUB Configuration (one-time)

```bash
# /etc/default/grub
GRUB_CMDLINE_LINUX="isolcpus=2,3 nohz_full=2,3 rcu_nocbs=2,3"
# Then: sudo update-grub && sudo reboot
```

---

## 11. systemd Service for Judge

```ini
# systemd/judge.service
[Unit]
Description=Compute Mastery Judge Daemon
After=redis.service
Requires=redis.service

[Service]
Type=simple
User=judge
Group=judge
WorkingDirectory=/path/to/thelife/judge
ExecStart=/usr/bin/python3 daemon.py
Restart=always
RestartSec=5

# Security
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/tmp/judge

# Resource limits
LimitNPROC=128
LimitNOFILE=1024

[Install]
WantedBy=multi-user.target
```

---

## 12. Dependencies

### System Packages
```
gcc / g++ (>= 12, for C++20)
clang (optional, alternative compiler)
rustc (via rustup)
iverilog (Icarus Verilog)
verilator
redis-server
linux-tools-$(uname -r)   # for perf
libseccomp-dev
```

### Python Packages (judge daemon)
```
redis
psutil
```

### Python Packages (Django app, additions to existing)
```
redis
markdown          # Render problem descriptions
```

### Frontend (CDN, no build step)
```
CodeMirror 6      # Code editor
```

---

## 13. Phase-wise Build Order

| Phase | Scope | Deliverable |
|-------|-------|-------------|
| **1** | Data models + Problem CRUD + test case management | Admin can create problems via forms, store test cases |
| **2** | Code editor integration + basic judge (compile + run, no isolation) | User can write code, submit, see pass/fail |
| **3** | CPU isolation setup + perf counters + timing collection | Low-noise benchmarking operational |
| **4** | Solution versioning + diff view + perf comparison | Compare optimization attempts side-by-side |
| **5** | Verilog/HDL playground with iverilog backend | Hardware problems solvable |
| **6** | LLM analysis hooks | Auto-analysis of solutions and version diffs |
| **7** | Polish: histograms, waveform viewer, tag-based filtering | Full UX |