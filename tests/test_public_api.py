import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import autolang.translator as translator_module
from autolang import TransparentTranslator, install


def test_install_returns_translator_instance(tmp_path):
    (tmp_path / "es.toml").write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")

    translator = install(str(tmp_path), "es")

    assert isinstance(translator, TransparentTranslator)


def test_install_result_can_be_bound_to_module_level_tt(tmp_path):
    (tmp_path / "es.toml").write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")
    translator = install(str(tmp_path), "es")
    tt = translator.translate
    name = "Alice"

    assert tt(f"Hello {name}") == "Hola Alice"


def test_bound_tt_supports_f_string_conversion_and_format_spec(tmp_path):
    (tmp_path / "es.toml").write_text(
        '"Price: {price:.2f}" = "Precio: {price:.2f}"\n'
        '"Debug: {obj!r}" = "Depurar: {obj!r}"\n',
        encoding="utf-8",
    )
    translator = install(str(tmp_path), "es")
    tt = translator.translate
    price = 12.345

    class Demo:
        def __repr__(self) -> str:
            return "<demo>"

    obj = Demo()

    assert tt(f"Price: {price:.2f}") == "Precio: 12.35"
    assert tt(f"Debug: {obj!r}") == "Depurar: <demo>"


def test_install_uses_system_locale_when_locale_str_is_omitted(
    tmp_path, monkeypatch
):
    (tmp_path / "es.toml").write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")
    monkeypatch.setattr(
        translator_module.locale,
        "getlocale",
        lambda: ("es_ES", "UTF-8"),
        raising=False,
    )
    name = "Alice"

    translator = install(str(tmp_path))

    assert translator.translate(f"Hello {name}") == "Hola Alice"


def test_install_accepts_hyphenated_system_locale(tmp_path, monkeypatch):
    (tmp_path / "zh.toml").write_text('"Hello {name}" = "你好 {name}"\n', encoding="utf-8")
    monkeypatch.setattr(
        translator_module.locale,
        "getlocale",
        lambda: ("zh-Hans-CN", "UTF-8"),
        raising=False,
    )
    name = "Alice"

    translator = install(str(tmp_path))

    assert translator.translate(f"Hello {name}") == "你好 Alice"


def test_install_accepts_windows_display_name_locale(tmp_path, monkeypatch):
    (tmp_path / "zh.toml").write_text('"Hello {name}" = "你好 {name}"\n', encoding="utf-8")
    monkeypatch.setattr(
        translator_module.locale,
        "getlocale",
        lambda: ("Chinese (Simplified)_China", "cp936"),
        raising=False,
    )
    name = "Alice"

    translator = install(str(tmp_path))

    assert translator.translate(f"Hello {name}") == "你好 Alice"


def test_install_falls_back_to_en_when_system_locale_is_unusable(
    tmp_path, monkeypatch
):
    (tmp_path / "en.toml").write_text('"Hello {name}" = "Hello there {name}"\n', encoding="utf-8")
    monkeypatch.setattr(
        translator_module.locale,
        "getlocale",
        lambda: ("C", "UTF-8"),
        raising=False,
    )
    monkeypatch.setenv("LC_ALL", "C.UTF-8")
    monkeypatch.setenv("LANG", "C.UTF-8")
    monkeypatch.delenv("LC_MESSAGES", raising=False)
    monkeypatch.delenv("LANGUAGE", raising=False)
    name = "Alice"

    translator = install(str(tmp_path))

    assert translator.translate(f"Hello {name}") == "Hello there Alice"
