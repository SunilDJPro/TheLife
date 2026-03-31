"""
AI code analysis for Compute Mastery using qwen2.5-coder:32b via LiteLLM + Ollama.
"""
import logging

import litellm
from django.conf import settings

logger = logging.getLogger(__name__)


def analyze_solution(solution, timing_data=None, perf_data=None):
    """
    Analyze a submitted solution. Saves analysis to solution.llm_analysis.

    Args:
        solution: Solution model instance (with problem relation)
        timing_data: dict with median_us, min_us, max_us, std_dev_us
        perf_data: dict with instructions, cycles, ipc, cache_misses, etc.

    Returns:
        The analysis text (also saved on the solution).
    """
    problem = solution.problem

    # Get previous version for comparison
    previous = solution.problem.solutions.filter(
        language=solution.language,
        version__lt=solution.version,
    ).first()

    prompt = _build_prompt(
        code=solution.code,
        language=solution.get_language_display(),
        problem_title=problem.title,
        problem_description=problem.description[:800],
        constraints=problem.constraints,
        is_accepted=solution.is_accepted,
        compiler_flags=f"{solution.compiler_flags} {solution.custom_flags}".strip(),
        timing_data=timing_data,
        perf_data=perf_data,
        previous_code=previous.code if previous else None,
        previous_version=previous.version if previous else None,
    )

    try:
        response = litellm.completion(
            model=settings.COMPUTE_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            api_base=settings.OLLAMA_BASE_URL,
            temperature=0.3,
            max_tokens=1000,
        )
        analysis = response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"LLM analysis failed for solution {solution.id}: {e}")
        analysis = f"Analysis unavailable: {e}"

    solution.llm_analysis = analysis
    solution.save(update_fields=['llm_analysis'])

    return analysis


def _build_prompt(code, language, problem_title, problem_description,
                  constraints, is_accepted, compiler_flags,
                  timing_data, perf_data, previous_code, previous_version):
    """Build the analysis prompt."""
    parts = [
        f"Analyze this {language} solution for the problem \"{problem_title}\".",
        "",
        f"## Problem Statement\n{problem_description}",
    ]

    if constraints:
        parts.append(f"\n## Constraints\n{constraints}")

    parts.append(f"\n## Solution (Flags: `{compiler_flags}`)\n```cpp\n{code}\n```")
    parts.append(f"\n## Judge Verdict: {'ACCEPTED' if is_accepted else 'FAILED'}")

    if timing_data:
        parts.append(
            f"\n## Timing\n"
            f"- Median: {timing_data.get('median_us', '?')} us\n"
            f"- Min: {timing_data.get('min_us', '?')} us\n"
            f"- Max: {timing_data.get('max_us', '?')} us\n"
            f"- Std Dev: {timing_data.get('std_dev_us', '?')} us"
        )

    if perf_data and any(v for k, v in perf_data.items() if v and k != 'ipc'):
        parts.append(
            f"\n## Hardware Performance Counters\n"
            f"- Instructions: {perf_data.get('instructions', 'N/A')}\n"
            f"- Cycles: {perf_data.get('cycles', 'N/A')}\n"
            f"- IPC: {perf_data.get('ipc', 'N/A')}\n"
            f"- Cache Misses: {perf_data.get('cache_misses', 'N/A')}\n"
            f"- Branch Misses: {perf_data.get('branch_misses', 'N/A')}"
        )

    if previous_code:
        parts.append(
            f"\n## Previous Version (v{previous_version}) for Comparison\n"
            f"```cpp\n{previous_code}\n```"
        )

    parts.append("""
## Your Task
Provide a concise performance-focused analysis:
1. **Approach** — Algorithm/technique used, time & space complexity
2. **Performance Assessment** — Interpret the perf counters if available (IPC, cache behavior, branch prediction)
3. **Optimization Suggestions** — Concrete improvements: SIMD intrinsics, cache-friendly data layout, algorithmic changes, compiler hints, pragma directives, loop unrolling, memory access patterns
4. **Comparison** — If a previous version exists, what changed and did it help?

Be specific and actionable. Focus on performance, not style. Keep it under 400 words. Use markdown.""")

    return "\n".join(parts)
