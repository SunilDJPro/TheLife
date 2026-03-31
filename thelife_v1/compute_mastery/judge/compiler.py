"""C++ compilation for the judge daemon."""
import os
import subprocess

COMPILE_TIMEOUT = 30  # seconds


def compile_cpp(code, work_dir, compiler_flags='-O2 -std=c++20', custom_flags=''):
    """
    Compile C++ source code.

    Returns (binary_path, error_message).
    binary_path is None on failure; error_message is None on success.
    """
    source_path = os.path.join(work_dir, 'solution.cpp')
    binary_path = os.path.join(work_dir, 'solution')

    with open(source_path, 'w') as f:
        f.write(code)

    cmd = ['g++']
    cmd.extend(compiler_flags.split())
    if custom_flags.strip():
        cmd.extend(custom_flags.split())
    cmd.extend(['-o', binary_path, source_path])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=COMPILE_TIMEOUT,
        )
        if result.returncode != 0:
            return None, result.stderr
        return binary_path, None
    except subprocess.TimeoutExpired:
        return None, 'Compilation timed out (30s limit)'
    except Exception as e:
        return None, str(e)
