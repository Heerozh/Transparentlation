import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from transparentlation import _, clear_cache, collect, get_translator, install, reload


def test_install_returns_default_translator(tmp_path):
    (tmp_path / "es.toml").write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")

    translator = install("es", str(tmp_path))

    assert translator is get_translator()


def test_module_reload_refreshes_default_translator(tmp_path):
    locale_file = tmp_path / "es.toml"
    locale_file.write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")

    install("es", str(tmp_path))
    name = "Alice"

    def wrapped_call():
        return _(f"Hello {name}")

    assert wrapped_call() == "Hola Alice"

    locale_file.write_text('"Hello {name}" = "Buenas {name}"\n', encoding="utf-8")
    reload()

    assert wrapped_call() == "Buenas Alice"


def test_clear_cache_keeps_current_translations(tmp_path):
    (tmp_path / "es.toml").write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")

    install("es", str(tmp_path))
    name = "Alice"

    def wrapped_call():
        return _(f"Hello {name}")

    assert wrapped_call() == "Hola Alice"

    clear_cache()

    assert wrapped_call() == "Hola Alice"


def test_collect_records_runtime_text(tmp_path):
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    install(
        "es",
        str(locale_dir),
        collect_missing=True,
        collect_locales=["en", "es"],
    )

    assert collect("runtime log line") == "runtime log line"
    assert (locale_dir / "en.toml").read_text(encoding="utf-8") == (
        '"runtime log line" = "runtime log line"\n'
    )
    assert (locale_dir / "es.toml").read_text(encoding="utf-8") == (
        '"runtime log line" = "runtime log line"\n'
    )
    assert (tmp_path / ".locales_cue" / "en.toml").read_text(encoding="utf-8") == (
        '"runtime log line" = "runtime log line"\n'
    )
    assert (tmp_path / ".locales_cue" / "es.toml").read_text(encoding="utf-8") == (
        '"runtime log line" = "runtime log line"\n'
    )


def test_collect_accepts_explicit_cue(tmp_path):
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    install("es", str(locale_dir), collect_missing=True, collect_locales=["es"])

    assert collect("Hello {name}", cue="Hello Alice") == "Hello {name}"
    assert (tmp_path / ".locales_cue" / "es.toml").read_text(encoding="utf-8") == (
        '"Hello {name}" = "Hello Alice"\n'
    )
