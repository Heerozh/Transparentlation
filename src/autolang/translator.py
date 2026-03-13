from __future__ import annotations

import ast
import inspect
import os
from dataclasses import dataclass
from types import CodeType, FrameType
from typing import Any

import executing
from babel import Locale
from babel.support import Format

from .source_templates import extract_template_from_call
from .toml_io import load_string_table


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


class TransparentTranslator:
    def __init__(
        self,
        locale_str: str = "en",
        locale_dir: str = "locales",
    ):
        self.locale = Locale.parse(locale_str)
        self.format = Format(self.locale)
        self.locale_dir = locale_dir
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
        return source_template

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
        return load_string_table(self._locale_file_path(self.locale.language))

    def _locale_file_path(self, locale_name: str) -> str:
        return os.path.join(self.locale_dir, f"{locale_name}.toml")

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
            return None

        translated = self.get_translation(template)
        compiled_code = self._compile_foreign_string(translated)
        return CacheEntry(template=template, variables=variables, compiled_code=compiled_code)

    def _parse_ast_node(self, node: ast.AST | None) -> tuple[str | None, tuple[str, ...]]:
        return extract_template_from_call(node)

    def _compile_foreign_string(self, translated: str) -> Any | None:
        try:
            return compile(f"f{translated!r}", "<autolang>", "eval")
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


def install(
    locale_str: str,
    locale_dir: str = "locales",
) -> TransparentTranslator:
    """Create a translator instance without mutating the module-level default translator."""
    return TransparentTranslator(locale_str, locale_dir)
