"""Template tags for Compute Mastery."""
from django import template
from compute_mastery.utils import render_markdown, format_runtime, format_count

register = template.Library()


@register.filter(name='md')
def markdown_filter(value):
    """Render Markdown to HTML."""
    if not value:
        return ''
    return render_markdown(value)


@register.filter(name='fmt_runtime')
def runtime_filter(us):
    """Format microseconds."""
    return format_runtime(us)


@register.filter(name='fmt_count')
def count_filter(n):
    """Format large number with commas."""
    return format_count(n)


@register.filter(name='status_color')
def status_color(status):
    """Return CSS color class for judge status."""
    colors = {
        'accepted': 'text-success',
        'wrong_answer': 'text-danger',
        'time_limit': 'text-warning',
        'memory_limit': 'text-warning',
        'runtime_error': 'text-danger',
        'compile_error': 'text-danger',
    }
    return colors.get(status, 'text-muted')
