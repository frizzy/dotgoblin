"""dotgoblin CLI interface."""

from __future__ import annotations

import os
import sys
import uuid

import click

from . import store, interpolate, runner


class DotgoblinGroup(click.Group):
    """Custom group that supports `dotgoblin [options] -- <command...>`."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # Extract everything after `--` before click sees it
        if "--" in args:
            idx = args.index("--")
            ctx.ensure_object(dict)
            ctx.obj["passthrough"] = args[idx + 1 :]
            args = args[:idx]
        return super().parse_args(ctx, args)


@click.group(cls=DotgoblinGroup, invoke_without_command=True)
@click.option("-s", "--set", "set_ref", default=None, help="Set name or name:section")
@click.option("--dry-run", is_flag=True, help="Print resolved env vars without running")
@click.pass_context
def cli(ctx: click.Context, set_ref: str | None, dry_run: bool) -> None:
    """Manage environment variable sets bound to profiles or directories.

    Run a command with injected env vars:

    \b
        dotgoblin -- flask run
        dotgoblin --set myapp:prod -- flask run
    """
    if ctx.invoked_subcommand is not None:
        return

    ctx.ensure_object(dict)
    command = ctx.obj.get("passthrough", [])

    if not command:
        click.echo(ctx.get_help())
        return

    set_name, section = _resolve_set_ref(set_ref)

    if set_name is None:
        cwd = os.getcwd()
        set_name = store.get_binding(cwd)
        if set_name is None:
            click.echo("Error: no set specified and no binding for current directory", err=True)
            sys.exit(1)

    try:
        env = store.resolve_set_env(set_name, section)
    except (FileNotFoundError, KeyError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    try:
        env = interpolate.interpolate_env(env)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if dry_run:
        runner.print_dry_run(env)
        return

    runner.exec_command(command, env)


def _resolve_set_name(name: str | None) -> str:
    """Resolve a set name, falling back to the CWD binding."""
    if name is not None:
        return name
    cwd = os.getcwd()
    bound = store.get_binding(cwd)
    if bound is None:
        click.echo("Error: no set specified and no binding for current directory", err=True)
        sys.exit(1)
    return bound


def _resolve_set_ref(ref: str | None) -> tuple[str | None, str | None]:
    """Parse a set reference like 'name', 'name:section', or ':section'."""
    if ref is None:
        return None, None
    if ":" in ref:
        name, section = ref.split(":", 1)
        return (name or None), (section or None)
    return ref, None


# ── set commands ──────────────────────────────────────────────────────


@cli.group("set")
def set_group() -> None:
    """Manage environment variable sets."""


@set_group.command("create")
@click.argument("name")
def set_create(name: str) -> None:
    """Create a new empty set."""
    try:
        path = store.create_set(name)
        click.echo(f"Created set '{name}' at {path}")
    except FileExistsError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@set_group.command("list")
def set_list() -> None:
    """List all sets."""
    sets = store.list_sets()
    if not sets:
        click.echo("No sets found")
        return
    for name in sets:
        click.echo(name)


@set_group.command("show")
@click.argument("name", required=False)
def set_show(name: str | None) -> None:
    """Show variables in a set (secrets shown as raw expressions).

    If NAME is omitted, uses the set bound to the current directory.
    """
    name = _resolve_set_name(name)
    try:
        data = store.load_set(name)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    if not data:
        click.echo("(empty set)")
        return

    meta = data.get("_meta", {})
    sections: dict[str, dict] = {}
    top_level: dict[str, str] = {}

    for key, value in data.items():
        if key == "_meta":
            continue
        if isinstance(value, dict):
            sections[key] = value
        else:
            top_level[key] = str(value)

    if meta:
        click.echo("[_meta]")
        for k, v in meta.items():
            click.echo(f"  {k} = {v!r}")
        click.echo()

    if top_level:
        for k, v in sorted(top_level.items()):
            click.echo(f"{k} = {v!r}")
        click.echo()

    for sec_name in sorted(sections):
        click.echo(f"[{sec_name}]")
        for k, v in sorted(sections[sec_name].items()):
            click.echo(f"  {k} = {str(v)!r}")
        click.echo()


@set_group.command("edit")
@click.argument("name", required=False)
def set_edit(name: str | None) -> None:
    """Open a set file in $EDITOR.

    If NAME is omitted, uses the set bound to the current directory.
    """
    name = _resolve_set_name(name)
    try:
        path = store.set_path(name)
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    editor = os.environ.get("EDITOR", "vi")
    os.execvp(editor, [editor, str(path)])


@set_group.command("rm")
@click.argument("name")
def set_rm(name: str) -> None:
    """Delete a set. Fails if active bindings reference it."""
    try:
        store.delete_set(name)
        click.echo(f"Deleted set '{name}'")
    except (FileNotFoundError, RuntimeError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ── var commands ──────────────────────────────────────────────────────


@cli.group("var")
def var_group() -> None:
    """Manage variables within a set."""


@var_group.command("set")
@click.argument("set_name")
@click.argument("key")
@click.argument("value")
def var_set(set_name: str, key: str, value: str) -> None:
    """Set a variable in a set."""
    try:
        store.set_variable(set_name, key, value)
        click.echo(f"Set {key} in '{set_name}'")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@var_group.command("rm")
@click.argument("set_name")
@click.argument("key")
def var_rm(set_name: str, key: str) -> None:
    """Remove a variable from a set."""
    try:
        store.remove_variable(set_name, key)
        click.echo(f"Removed {key} from '{set_name}'")
    except (FileNotFoundError, KeyError) as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ── bind / unbind ────────────────────────────────────────────────────


class BindGroup(click.Group):
    """Group that treats unknown first args as set names for CWD binding."""

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        # If first arg is not a known subcommand or flag, treat it as a set name
        if args and args[0] not in self.commands and not args[0].startswith("-"):
            ctx.ensure_object(dict)
            ctx.obj["bind_set_name"] = args[0]
            args = args[1:]
            ctx.invoked_subcommand = "*"  # prevent subcommand dispatch
        return super().parse_args(ctx, args)

    def invoke(self, ctx: click.Context) -> None:
        ctx.ensure_object(dict)
        if "bind_set_name" in ctx.obj:
            # Direct CWD binding mode
            _do_bind_cwd(ctx.obj["bind_set_name"])
            return
        super().invoke(ctx)


def _do_bind_cwd(set_name: str | None) -> None:
    """Bind CWD to a set, creating an anonymous one if needed."""
    cwd = os.getcwd()
    if set_name is None:
        set_name = uuid.uuid4().hex[:8]
        store.create_set(set_name)
        click.echo(f"Created anonymous set '{set_name}'")
    try:
        store.bind_directory(cwd, set_name)
        click.echo(f"Bound {cwd} → {set_name}")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group("bind", cls=BindGroup, invoke_without_command=True)
@click.pass_context
def bind_group(ctx: click.Context) -> None:
    """Manage directory-to-set bindings.

    When called without a subcommand, binds the current directory to a set.
    """
    if ctx.invoked_subcommand is not None:
        return
    _do_bind_cwd(None)


@bind_group.command("add")
@click.argument("set_name")
@click.argument("directory")
def bind_add(set_name: str, directory: str) -> None:
    """Bind an arbitrary directory to a set."""
    directory = os.path.abspath(os.path.expanduser(directory))
    try:
        store.bind_directory(directory, set_name)
        click.echo(f"Bound {directory} → {set_name}")
    except FileNotFoundError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@bind_group.command("list")
@click.argument("set_name", required=False)
def bind_list(set_name: str | None) -> None:
    """List all bindings, optionally filtered by set name."""
    pairs = store.list_bindings_for_set(set_name)
    if not pairs:
        if set_name:
            click.echo(f"No bindings for set '{set_name}'")
        else:
            click.echo("No bindings")
        return
    max_dir = max(len(d) for d, _ in pairs)
    for directory, sname in pairs:
        click.echo(f"  {directory:<{max_dir}}  → {sname}")


@bind_group.command("rm")
@click.argument("directory", required=False)
def bind_rm(directory: str | None) -> None:
    """Remove a binding. Defaults to current directory."""
    if directory is None:
        directory = os.getcwd()
    else:
        directory = os.path.abspath(os.path.expanduser(directory))
    try:
        store.unbind_directory(directory)
        click.echo(f"Unbound {directory}")
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command("unbind")
def unbind() -> None:
    """Remove the binding for the current directory (shortcut for bind rm)."""
    cwd = os.getcwd()
    try:
        store.unbind_directory(cwd)
        click.echo(f"Unbound {cwd}")
    except KeyError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


# ── status ────────────────────────────────────────────────────────────


@cli.command("status")
def status() -> None:
    """Show the active set for the current directory."""
    cwd = os.getcwd()
    set_name = store.get_binding(cwd)

    if set_name is None:
        click.echo(f"No binding for {cwd}")
        return

    click.echo(f"Directory: {cwd}")
    click.echo(f"Set:       {set_name}")
    click.echo()

    try:
        env = store.resolve_set_env(set_name)
    except FileNotFoundError:
        click.echo("(set file missing)")
        return

    if not env:
        click.echo("(no variables)")
        return

    max_key = max(len(k) for k in env)
    for key in sorted(env):
        click.echo(f"  {key:<{max_key}} = {env[key]}")


def main() -> None:
    cli()
