# Transparentlation

`Transparentlation` is an experimental i18n library for Python `f-string` call sites.
It lets you write `_(f"...")`, reconstructs the original template at runtime, looks up a translated template from TOML, and re-evaluates the translated placeholders with Babel-aware formatting.

## Status

This project is under active development.

Stable today:
- Module-level `_(...)` translation helper
- Module-level `collect(...)` helper for runtime string capture
- `install(locale, locale_dir)` to switch the default translator
- `TransparentTranslator` for explicit instances
- TOML-backed translation lookup
- Babel `fmt.*` placeholder support inside translated templates
- Per-instance call-site cache with `reload()` and `clear_cache()`
- Optional runtime collection of missing strings into TOML

Planned:
- AI-assisted translation generation
- Automatic TOML comparison and sync tools
- Better extraction and review workflows

## Installation

```bash
pip install transparentlation
```

## Quick Start

Project layout:

```text
your_app/
  app.py
  locales/
    es.toml
```

`locales/es.toml`

```toml
"Hello {name}" = "Hola {name}"
"Today is {fmt.date(now, format='short')}" = "Hoy es {fmt.date(now, format='short')}"
```

`app.py`

```python
from datetime import datetime

from babel import Locale
from babel.support import Format

from transparentlation import _, install

install("es", "locales")

# A local fmt object keeps the original f-string valid before translation happens.
fmt = Format(Locale.parse("en"))

name = "Alice"
now = datetime(2026, 3, 11)

print(_(f"Hello {name}"))
print(_(f"Today is {fmt.date(now, format='short')}"))
```

Example output:

```text
Hola Alice
Hoy es 11/3/26
```

## Public API

```python
from transparentlation import (
    _,
    collect,
    TransparentTranslator,
    clear_cache,
    get_translator,
    install,
    reload,
)
```

- `_(text)` translates the current call site with the default translator.
- `collect(text)` records a runtime string into the configured collection TOML and returns the original text.
- `install(locale_str, locale_dir="locales", collect_missing=False, collect_locales=None)` replaces the default translator and returns it.
- `get_translator()` returns the current default translator instance.
- `reload()` reloads the active locale file and clears cached call-site entries.
- `clear_cache()` clears the default translator cache without reloading files.
- `TransparentTranslator(locale_str, locale_dir="locales", collect_missing=False, collect_locales=None)` creates an explicit translator instance with its own cache.

## Runtime Collection

If you want untranslated text to be collected while the program runs, enable `collect_missing`.

```python
from transparentlation import _, collect, install

install("es", "locales", collect_missing=True, collect_locales=["en", "es", "fr"])

name = "Alice"
print(_(f"Hello {name}"))
collect("background worker started")
```

This writes missing entries directly into each configured translation table:

```toml
"Hello {name}" = "Hello {name}"
"background worker started" = "background worker started"
```

For the example above, the library writes the same placeholder entries into:
- `locales/en.toml`
- `locales/es.toml`
- `locales/fr.toml`

## How It Works

At a high level:

1. You call `_(f"...")`.
2. The library inspects the caller frame and maps it back to the AST node for that exact call site.
3. It rebuilds the source template, for example `Hello {name}`.
4. It loads the translated template from TOML.
5. It compiles the translated template as an f-string expression and caches it per translator instance.
6. Later calls from the same bytecode location reuse the cached compiled expression.

## Constraints

This is not a drop-in replacement for mature gettext tooling yet.

- The main path is designed for direct `_(f"...")` usage.
- Translation lookup is currently a flat TOML key-value map.
- Runtime collection writes flat TOML entries and currently rewrites the file content instead of preserving comments.
- Runtime collection writes directly into the language TOML files you configure in `collect_locales`.
- If translated placeholder expressions are invalid or fail at evaluation time, the library falls back to the original rendered text.
- The library currently relies on runtime frame inspection and AST recovery, so unusual execution environments may behave differently.

## Development

Run tests:

```bash
uv run pytest -q
```

## Roadmap

- AI-generated translations from source templates and rendered examples
- Locale file generation and diffing
- Better developer tooling around extraction, validation, and review
