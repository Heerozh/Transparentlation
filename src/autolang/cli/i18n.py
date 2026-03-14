from __future__ import annotations

from ..translator import install

cli_translator = install()
tt = cli_translator.translate

__all__ = ["cli_translator", "tt"]
