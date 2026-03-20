"""Storage layer for dotgoblin sets and bindings."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

import tomli_w


def get_store_dir() -> Path:
    """Return the dotgoblin config directory, creating it if needed."""
    store = Path(os.environ.get("DOTGOBLIN_DIR", "~/.config/dotgoblin")).expanduser()
    store.mkdir(parents=True, exist_ok=True)
    (store / "sets").mkdir(exist_ok=True)
    return store


def _bindings_path() -> Path:
    return get_store_dir() / "bindings.toml"


def _set_path(name: str) -> Path:
    return get_store_dir() / "sets" / f"{name}.toml"


# ── Sets ──────────────────────────────────────────────────────────────


def create_set(name: str) -> Path:
    """Create a new empty set file. Raises if it already exists."""
    path = _set_path(name)
    if path.exists():
        raise FileExistsError(f"Set '{name}' already exists")
    path.write_text("")
    return path


def list_sets() -> list[str]:
    """Return sorted names of all sets."""
    sets_dir = get_store_dir() / "sets"
    return sorted(p.stem for p in sets_dir.glob("*.toml"))


def load_set(name: str) -> dict:
    """Load and return the raw parsed TOML for a set."""
    path = _set_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Set '{name}' not found")
    text = path.read_text()
    if not text.strip():
        return {}
    return tomllib.loads(text)


def delete_set(name: str) -> None:
    """Delete a set. Fails if any binding references it."""
    path = _set_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Set '{name}' not found")
    bindings = load_bindings()
    referencing = [d for d, info in bindings.items() if info.get("set") == name]
    if referencing:
        dirs = ", ".join(referencing)
        raise RuntimeError(
            f"Cannot delete set '{name}': still bound to {dirs}"
        )
    path.unlink()


def set_path(name: str) -> Path:
    """Return the path to a set file (for editing)."""
    path = _set_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Set '{name}' not found")
    return path


def resolve_set_env(name: str, section: str | None = None) -> dict[str, str]:
    """Resolve a set into a flat dict of KEY=value pairs.

    Merges top-level variables with the chosen section.
    Section defaults to _meta.default if not specified.
    """
    data = load_set(name)

    # Separate top-level vars, _meta, and sections
    meta = data.get("_meta", {})
    top_level: dict[str, str] = {}
    sections: dict[str, dict[str, str]] = {}

    for key, value in data.items():
        if key == "_meta":
            continue
        if isinstance(value, dict):
            sections[key] = value
        else:
            top_level[key] = str(value)

    # Determine which section to apply
    if section is None:
        section = meta.get("default")

    env: dict[str, str] = dict(top_level)
    if section:
        if section not in sections:
            available = ", ".join(sorted(sections.keys())) or "(none)"
            raise KeyError(
                f"Section '{section}' not found in set '{name}'. "
                f"Available sections: {available}"
            )
        for k, v in sections[section].items():
            env[k] = str(v)

    return env


# ── Variables ─────────────────────────────────────────────────────────


def set_variable(set_name: str, key: str, value: str, section: str | None = None) -> None:
    """Set a variable in a set file."""
    data = load_set(set_name)

    if section:
        if section not in data:
            data[section] = {}
        data[section][key] = value
    else:
        data[key] = value

    _write_set(set_name, data)


def remove_variable(set_name: str, key: str, section: str | None = None) -> None:
    """Remove a variable from a set file."""
    data = load_set(set_name)

    target = data if section is None else data.get(section, {})
    if key not in target:
        where = f"section '{section}'" if section else "top level"
        raise KeyError(f"Variable '{key}' not found in {where} of set '{set_name}'")

    del target[key]
    _write_set(set_name, data)


def _write_set(name: str, data: dict) -> None:
    path = _set_path(name)
    path.write_bytes(tomli_w.dumps(data).encode())


# ── Bindings ──────────────────────────────────────────────────────────


def load_bindings() -> dict[str, dict]:
    """Load all bindings from bindings.toml."""
    path = _bindings_path()
    if not path.exists():
        return {}
    text = path.read_text()
    if not text.strip():
        return {}
    return tomllib.loads(text)


def _save_bindings(bindings: dict) -> None:
    path = _bindings_path()
    path.write_bytes(tomli_w.dumps(bindings).encode())


def bind_directory(directory: str, set_name: str) -> None:
    """Bind a directory to a set."""
    if not _set_path(set_name).exists():
        raise FileNotFoundError(f"Set '{set_name}' not found")
    bindings = load_bindings()
    bindings[directory] = {"set": set_name}
    _save_bindings(bindings)


def unbind_directory(directory: str) -> None:
    """Remove the binding for a directory."""
    bindings = load_bindings()
    if directory not in bindings:
        raise KeyError(f"No binding found for '{directory}'")
    del bindings[directory]
    _save_bindings(bindings)


def get_binding(directory: str) -> str | None:
    """Return the set name bound to a directory, or None."""
    bindings = load_bindings()
    info = bindings.get(directory)
    return info["set"] if info else None


def list_bindings_for_set(set_name: str | None = None) -> list[tuple[str, str]]:
    """Return (directory, set_name) pairs, optionally filtered by set."""
    bindings = load_bindings()
    pairs = [(d, info["set"]) for d, info in bindings.items()]
    if set_name is not None:
        pairs = [(d, s) for d, s in pairs if s == set_name]
    return sorted(pairs)
