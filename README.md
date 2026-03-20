# dotgoblin

CLI tool for managing environment variable sets bound to named profiles or working directories. Secrets stay off disk via shell interpolation at runtime.

## Installation

### With uv (recommended)

```sh
# Run directly without installing
uvx dotgoblin --help

# Install globally
uv tool install dotgoblin

# Install from source
uv tool install .

# Or add to a project
uv add dotgoblin
```

### With pip

```sh
pip install dotgoblin
```

### From source

```sh
git clone https://github.com/frizzy/dotgoblin.git
cd dotgoblin
uv sync
```

## Quick start

```sh
# Create a set
dotgoblin set create myapp

# Add variables
dotgoblin var set myapp DATABASE_URL "postgres://localhost:5432/app"
dotgoblin var set myapp API_KEY '$(pass show myapp/api-key)'

# Bind your project directory to the set
cd ~/Code/myapp
dotgoblin bind myapp

# Run a command with the injected env
dotgoblin -- flask run

# Or reference a set explicitly
dotgoblin --set myapp -- flask run

# Preview what would be injected
dotgoblin --dry-run -- flask run
```

## Concepts

- **Set** — a named collection of environment variables stored as TOML
- **Binding** — maps a working directory to a set, so `dotgoblin -- <cmd>` auto-selects it
- **Section** — sets can have named sections (e.g. `local`, `prod`) that override base variables
- **Secret interpolation** — values like `$(pass show key)` are evaluated at runtime, keeping secrets off disk

## Storage

All config lives in `~/.config/dotgoblin/` (override with `DOTGOBLIN_DIR`):

```
~/.config/dotgoblin/
├── sets/
│   ├── myapp.toml
│   └── ...
└── bindings.toml
```

### Set file format

```toml
# Top-level variables apply to all sections
APP_NAME = "myapp"

[_meta]
default = "local"

[local]
DATABASE_URL = "postgres://localhost:5432/app"
API_KEY = "$(pass show local/api-key)"

[prod]
DATABASE_URL = "postgres://prod.db:5432/app"
API_KEY = "$(pass show prod/api-key)"
```

## Commands

### Run a command

```sh
dotgoblin -- <command...>
dotgoblin --set <name> -- <command...>
dotgoblin --set <name>:<section> -- <command...>
dotgoblin --set :<section> -- <command...>    # use bound set with specific section
dotgoblin --dry-run -- <command...>
```

Variables are merged on top of your current shell environment.

### Manage sets

```sh
dotgoblin set create <name>    # create a new empty set
dotgoblin set list             # list all sets
dotgoblin set show <name>      # show variables (secrets shown as raw expressions)
dotgoblin set edit <name>      # open in $EDITOR
dotgoblin set rm <name>        # delete (fails if bound)
```

### Manage variables

```sh
dotgoblin var set <set> <KEY> <value>    # set a variable
dotgoblin var rm <set> <KEY>             # remove a variable
```

### Bindings

```sh
dotgoblin bind [<set-name>]    # bind current directory to a set
dotgoblin unbind               # remove binding for current directory
dotgoblin status               # show active set and variables
```

If `bind` is called without a set name, an anonymous set is created automatically.

## Secret interpolation

Any value containing `$(...)` is treated as a shell expression and evaluated at runtime. This keeps secrets out of the store files.

```toml
API_KEY = "$(pass show myapp/api-key)"
TOKEN = "Bearer $(cat ~/.tokens/myapp)"
DB_PASS = "$(op read 'op://Vault/DB/password')"
```

Interpolation only happens during `dotgoblin -- <cmd>` and `--dry-run`. All other commands display the raw expression. If a command fails, dotgoblin aborts with the failing key and stderr.

## Resolution order

1. `--set <name>` flag (explicit, highest priority)
2. Directory binding (from `bindings.toml`)
3. Error: no set found

## Environment

| Variable        | Description                                                 |
| --------------- | ----------------------------------------------------------- |
| `DOTGOBLIN_DIR` | Override config directory (default: `~/.config/dotgoblin/`) |
| `EDITOR`        | Editor used by `dotgoblin set edit` (default: `vi`)         |

## License

MIT
