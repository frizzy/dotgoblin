"""Command execution with environment injection."""

from __future__ import annotations

import os
import shlex
import sys


def exec_command(command: list[str], env: dict[str, str]) -> None:
    """Replace the current process with the given command, injecting env vars.

    The provided env vars are merged on top of the current shell environment.
    """
    merged = {**os.environ, **env}
    os.execvpe(command[0], command, merged)


def print_dry_run(env: dict[str, str]) -> None:
    """Print resolved environment variables without running a command."""
    if not env:
        print("(no variables)")
        return
    max_key = max(len(k) for k in env)
    for key in sorted(env):
        print(f"  {key:<{max_key}} = {env[key]}")


def format_envfile(env: dict[str, str], export: bool = False) -> str:
    """Format env vars as a newline-terminated envfile string.

    Values are shell-quoted with shlex.quote so output is safe to source/eval.
    With export=True, prefixes each line with `export `.
    """
    prefix = "export " if export else ""
    lines = [f"{prefix}{key}={shlex.quote(env[key])}" for key in sorted(env)]
    return "\n".join(lines) + ("\n" if lines else "")
