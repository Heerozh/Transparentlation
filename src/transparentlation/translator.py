from __future__ import annotations

import ast
import inspect
import json
import os
from dataclasses import dataclass
from types import CodeType, FrameType
from typing import Any

import executing
from babel import Locale
from babel.support import Format

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib


@dataclass(frozen=True, slots=True)
class CacheEntry:
    template: str
    variables: tuple[str, ...]
    compiled_code: Any | None


CacheKey = tuple[str, int, str, int]


def _make_cache_key(frame: FrameType) -> CacheKey:
    code: CodeType = frame.f_code
    qualified_name = getattr(code, "co_qualname", code.co_name)
    return (code.co_filename, code.co_firstlineno, qualified_name, frame.f_lasti)


def _normalize_locale_names(
    locale_str: str, collect_locales: list[str] | tuple[str, ...] | None
) -> tuple[str, ...]:
    raw_locales = collect_locales or [locale_str]
    normalized: list[str] = []

    for value in raw_locales:
        language = Locale.parse(value).language
        if language not in normalized:
            normalized.append(language)

    return tuple(normalized)


class TransparentTranslator:
    def __init__(
        self,
        locale_str: str = "en",
        locale_dir: str = "locales",
        *,
        collect_missing: bool = False,
        collect_locales: list[str] | tuple[str, ...] | None = None,
    ):
        self.locale = Locale.parse(locale_str)
        self.format = Format(self.locale)
        self.locale_dir = locale_dir
        self.collect_missing = collect_missing
        self.collect_locales = _normalize_locale_names(locale_str, collect_locales)
        self.translations: dict[str, str] = {}
        self._cache: dict[CacheKey, CacheEntry] = {}
        self.reload()

    def reload(self) -> None:
        """Reload translations for the current locale and invalidate cached call sites."""
        self.translations = self._load_translations()
        self.clear_cache()

    def clear_cache(self) -> None:
        self._cache.clear()

    def get_translation(self, source_template: str) -> str:
        translated = self.translations.get(source_template)
        if isinstance(translated, str):
            return translated

        self.collect(source_template)
        return source_template

    def collect(self, text: str) -> str:
        """Persist a runtime string into the configured locale TOML files when enabled."""
        if not self.collect_missing or not text:
            return text

        for locale_name in self.collect_locales:
            toml_path = self._locale_file_path(locale_name)
            collected = self._read_translation_file(toml_path)
            if text not in collected:
                collected[text] = text
                self._write_translation_file(toml_path, collected)

        if self.locale.language in self.collect_locales:
            self.translations[text] = self.translations.get(text, text)

        return text

    def translate(self, text: str) -> str:
        frame = inspect.currentframe()
        caller = frame.f_back if frame is not None else None
        if caller is None:
            return text

        try:
            return self._translate_from_frame(text, caller)
        finally:
            del caller
            del frame

    def _load_translations(self) -> dict[str, str]:
        return self._read_translation_file(self._locale_file_path(self.locale.language))

    def _locale_file_path(self, locale_name: str) -> str:
        return os.path.join(self.locale_dir, f"{locale_name}.toml")

    def _read_translation_file(self, toml_path: str) -> dict[str, str]:
        if not os.path.exists(toml_path):
            return {}

        try:
            with open(toml_path, "rb") as file:
                data = tomllib.load(file)
        except OSError:
            return {}
        except tomllib.TOMLDecodeError:
            return {}

        if not isinstance(data, dict):
            return {}

        return {key: value for key, value in data.items() if isinstance(key, str)}

    def _write_translation_file(self, toml_path: str, entries: dict[str, str]) -> None:
        directory = os.path.dirname(toml_path)
        if directory:
            os.makedirs(directory, exist_ok=True)

        lines = [
            f"{json.dumps(key, ensure_ascii=False)} = {json.dumps(value, ensure_ascii=False)}"
            for key, value in sorted(entries.items())
            if isinstance(key, str) and isinstance(value, str)
        ]

        with open(toml_path, "w", encoding="utf-8", newline="\n") as file:
            if lines:
                file.write("\n".join(lines))
                file.write("\n")

    def _translate_from_frame(self, text: str, frame: FrameType) -> str:
        cache_key = _make_cache_key(frame)
        entry = self._cache.get(cache_key)

        if entry is None:
            entry = self._cache.get(cache_key)
            if entry is None:
                entry = self._build_cache_entry(frame, text)
                if entry is None:
                    return text
                self._cache[cache_key] = entry

        return self._evaluate(entry.compiled_code, frame, text)

    def _build_cache_entry(self, frame: FrameType, fallback_text: str) -> CacheEntry | None:
        execution = executing.Source.executing(frame)
        node = execution.node
        template, variables = self._parse_ast_node(node)

        if template is None:
            self.collect(fallback_text)
            return None

        translated = self.get_translation(template)
        compiled_code = self._compile_foreign_string(translated)
        return CacheEntry(template=template, variables=variables, compiled_code=compiled_code)

    def _parse_ast_node(self, node: ast.AST | None) -> tuple[str | None, tuple[str, ...]]:
        if not isinstance(node, ast.Call) or not node.args:
            return None, ()

        arg = node.args[0]
        if isinstance(arg, ast.Constant):
            return str(arg.value), ()

        if not isinstance(arg, ast.JoinedStr):
            return None, ()

        parts: list[str] = []
        variables: list[str] = []

        for value in arg.values:
            if isinstance(value, ast.Constant):
                parts.append(str(value.value))
                continue

            if isinstance(value, ast.FormattedValue):
                expression = ast.unparse(value.value)
                parts.append(f"{{{expression}}}")
                variables.append(expression)

        return "".join(parts), tuple(variables)

    def _compile_foreign_string(self, translated: str) -> Any | None:
        try:
            return compile(f"f{translated!r}", "<transparentlation>", "eval")
        except Exception:
            return None

    def _evaluate(self, compiled_code: Any | None, frame: FrameType, fallback: str) -> str:
        if compiled_code is None:
            return fallback

        locals_proxy = frame.f_locals.copy()
        locals_proxy["fmt"] = self.format

        try:
            return eval(compiled_code, frame.f_globals, locals_proxy)
        except Exception:
            return fallback


_global_translator = TransparentTranslator("en")


def install(
    locale_str: str,
    locale_dir: str = "locales",
    *,
    collect_missing: bool = False,
    collect_locales: list[str] | tuple[str, ...] | None = None,
) -> TransparentTranslator:
    """Replace the default translator used by the module-level `_()` helper."""
    global _global_translator
    _global_translator = TransparentTranslator(
        locale_str,
        locale_dir,
        collect_missing=collect_missing,
        collect_locales=collect_locales,
    )
    return _global_translator


def get_translator() -> TransparentTranslator:
    return _global_translator


def reload() -> None:
    _global_translator.reload()


def clear_cache() -> None:
    _global_translator.clear_cache()


def collect(text: str) -> str:
    """Collect a runtime string into the configured TOML file when enabled."""
    return _global_translator.collect(text)


def _(text: str) -> str:
    """Translate a string while preserving f-string ergonomics at the call site."""
    frame = inspect.currentframe()
    caller = frame.f_back if frame is not None else None
    if caller is None:
        return text

    try:
        return _global_translator._translate_from_frame(text, caller)
    finally:
        del caller
        del frame
