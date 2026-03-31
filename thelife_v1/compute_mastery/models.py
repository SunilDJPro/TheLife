"""
Compute Mastery models — LeetCode-style coding environment with deep perf analysis.
Phase 1: C++ only. Models keep extensibility for Rust/HDL later.
"""
import uuid
from django.db import models
from django.conf import settings
from django.utils.text import slugify


class Tag(models.Model):
    """Problem tags: dp, simd, concurrency, pragma, etc."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=120, unique=True)

    class Meta:
        db_table = 'mastery_tags'
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Problem(models.Model):
    """A coding problem with metadata, test cases, and starter code."""
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]
    CATEGORY_CHOICES = [
        ('algorithm', 'Algorithm'),
        ('systems', 'Systems'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name='mastery_problems')
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True)
    description = models.TextField(help_text="Markdown-formatted problem statement")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    tags = models.ManyToManyField(Tag, blank=True, related_name='problems')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='algorithm')
    constraints = models.TextField(blank=True, help_text="Input constraints")
    hints = models.TextField(blank=True)

    # Template code per language — {"cpp": "...", "rust": "..."}
    starter_code = models.JSONField(default=dict, blank=True)

    # Reference solution (hidden from UI, used by LLM analysis)
    reference_solution = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mastery_problems'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_difficulty_display()})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness
            base_slug = self.slug
            counter = 1
            while Problem.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def solution_count(self):
        return self.solutions.count()

    @property
    def best_runtime(self):
        best = self.solutions.filter(is_accepted=True, median_runtime_us__isnull=False)\
            .order_by('median_runtime_us').first()
        return best.median_runtime_us if best else None

    @property
    def is_solved(self):
        return self.solutions.filter(is_accepted=True).exists()


class TestCase(models.Model):
    """Test case for a problem — input/output pair with limits."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='test_cases')
    input_data = models.TextField(help_text="Raw stdin input")
    expected_output = models.TextField(help_text="Expected stdout output")
    is_sample = models.BooleanField(default=False, help_text="Visible in problem statement")
    order = models.PositiveIntegerField(default=0)
    time_limit_ms = models.PositiveIntegerField(default=2000)
    memory_limit_mb = models.PositiveIntegerField(default=256)

    class Meta:
        db_table = 'mastery_test_cases'
        ordering = ['order']

    def __str__(self):
        label = "Sample" if self.is_sample else "Hidden"
        return f"{label} #{self.order} for {self.problem.title}"


class Solution(models.Model):
    """Immutable snapshot of a solution version. Multiple versions per problem per language."""
    LANGUAGE_CHOICES = [
        ('cpp', 'C++'),
        ('rust', 'Rust'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    problem = models.ForeignKey(Problem, on_delete=models.CASCADE, related_name='solutions')
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='cpp')
    version = models.PositiveIntegerField()
    code = models.TextField()
    notes = models.TextField(blank=True, help_text="e.g., 'Added SIMD', 'Tried lock-free queue'")

    # Denormalized latest run results for quick display
    is_accepted = models.BooleanField(null=True)
    median_runtime_us = models.FloatField(null=True, blank=True)
    peak_memory_kb = models.PositiveIntegerField(null=True, blank=True)
    perf_counters = models.JSONField(default=dict, blank=True)

    # Compiler config used
    compiler_flags = models.CharField(max_length=100, default='-O2 -std=c++20')
    custom_flags = models.CharField(max_length=200, blank=True)

    # AI analysis from qwen2.5-coder
    llm_analysis = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mastery_solutions'
        unique_together = ['problem', 'language', 'version']
        ordering = ['-version']

    def __str__(self):
        status = "AC" if self.is_accepted else ("WA" if self.is_accepted is False else "?")
        return f"v{self.version} [{status}] — {self.problem.title}"

    @property
    def runtime_display(self):
        if self.median_runtime_us is None:
            return "—"
        if self.median_runtime_us >= 1000:
            return f"{self.median_runtime_us / 1000:.2f} ms"
        return f"{self.median_runtime_us:.1f} us"


class JudgeResult(models.Model):
    """Detailed per-test-case results for a solution run."""
    STATUS_CHOICES = [
        ('accepted', 'Accepted'),
        ('wrong_answer', 'Wrong Answer'),
        ('time_limit', 'Time Limit Exceeded'),
        ('memory_limit', 'Memory Limit Exceeded'),
        ('runtime_error', 'Runtime Error'),
        ('compile_error', 'Compile Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    solution = models.ForeignKey(Solution, on_delete=models.CASCADE, related_name='results')
    test_case = models.ForeignKey(TestCase, on_delete=models.CASCADE, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    actual_output = models.TextField(blank=True)
    stderr_output = models.TextField(blank=True)

    # Timing — collected over N iterations
    wall_times_us = models.JSONField(default=list)
    median_time_us = models.FloatField(null=True)
    min_time_us = models.FloatField(null=True)
    max_time_us = models.FloatField(null=True)
    std_dev_us = models.FloatField(null=True)

    # perf stat counters
    instructions = models.BigIntegerField(null=True)
    cycles = models.BigIntegerField(null=True)
    cache_misses = models.BigIntegerField(null=True)
    branch_misses = models.BigIntegerField(null=True)
    ipc = models.FloatField(null=True)
    context_switches = models.PositiveIntegerField(null=True)

    # Memory
    peak_memory_kb = models.PositiveIntegerField(null=True)

    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'mastery_judge_results'
        ordering = ['test_case__order']

    def __str__(self):
        return f"{self.get_status_display()} — TC#{self.test_case.order if self.test_case else '?'}"
