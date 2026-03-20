"""Shell interpolation for secret expressions."""

from __future__ import annotations

import re
import subprocess


_SHELL_EXPR = re.compile(r"\$\((.+?)\)")


def interpolate_value(key: str, value: str) -> str:
    """Interpolate all $(…) expressions in a value via the user's shell.

    Raises RuntimeError with the key name and stderr if any command fails.
    """

    def _replace(match: re.Match) -> str:
        cmd = match.group(1)
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                f"Interpolation failed for '{key}': command `{cmd}` "
                f"exited with code {result.returncode}"
                + (f"\n  stderr: {stderr}" if stderr else "")
            )
        return result.stdout.rstrip("\n")

    return _SHELL_EXPR.sub(_replace, value)


def interpolate_env(env: dict[str, str]) -> dict[str, str]:
    """Interpolate all values in an env dict. Returns a new dict."""
    return {k: interpolate_value(k, v) for k, v in env.items()}


def has_interpolation(value: str) -> bool:
    """Check if a value contains shell expressions."""
    return bool(_SHELL_EXPR.search(value))
