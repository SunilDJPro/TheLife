"""Utility functions for Compute Mastery."""
import difflib
import markdown as md


def render_markdown(text):
    """Render Markdown text to HTML."""
    return md.markdown(
        text,
        extensions=['fenced_code', 'tables', 'codehilite'],
        extension_configs={
            'codehilite': {'css_class': 'code-highlight', 'linenums': False},
        },
    )


def generate_diff(code_old, code_new):
    """Returns unified diff lines between two code versions."""
    return list(difflib.unified_diff(
        code_old.splitlines(keepends=True),
        code_new.splitlines(keepends=True),
        fromfile="Previous Version",
        tofile="Current Version",
        lineterm="",
    ))


def format_runtime(us):
    """Format microseconds into human-readable string."""
    if us is None:
        return "—"
    if us >= 1_000_000:
        return f"{us / 1_000_000:.2f} s"
    if us >= 1000:
        return f"{us / 1000:.2f} ms"
    return f"{us:.1f} us"


def format_count(n):
    """Format large numbers with commas."""
    if n is None:
        return "—"
    return f"{n:,}"
