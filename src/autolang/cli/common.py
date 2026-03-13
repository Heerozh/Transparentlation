from __future__ import annotations

from pathlib import Path

from babel import Locale

from ..toml_io import load_string_table

SKIPPED_SOURCE_DIR_NAMES = {
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
NO_TRANSLATION = "NO_TRANSLATION"


def load_shared_cues(locale_dir: Path) -> dict[str, str]:
    cue_dir = locale_dir.parent / f".{locale_dir.name}_cue"
    merged_cues: dict[str, str] = {}
    for cue_path in sorted(cue_dir.glob("*.toml")):
        if not cue_path.is_file():
            continue
        for key, value in load_string_table(str(cue_path)).items():
            merged_cues.setdefault(key, value)
    return merged_cues


def build_source_cue_path(locale_dir: Path, locale_name: str) -> Path:
    cue_dir = locale_dir.parent / f".{locale_dir.name}_cue"
    return cue_dir / f"{locale_name}.toml"


def list_locale_files(locale_dir: Path) -> list[Path]:
    return sorted(path for path in locale_dir.glob("*.toml") if path.is_file())


def should_recurse_into_directory(path: str) -> bool:
    name = Path(path).name
    return not name.startswith(".") and name not in SKIPPED_SOURCE_DIR_NAMES


def normalize_language(locale_name: str) -> str:
    return Locale.parse(locale_name).language


def locale_display_name(locale_name: str) -> str:
    locale = Locale.parse(locale_name)
    return locale.get_display_name("en").title()
