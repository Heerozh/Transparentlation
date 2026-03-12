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
    install(
        "es",
        str(tmp_path),
        collect_missing=True,
        collect_locales=["en", "es"],
    )

    assert collect("runtime log line") == "runtime log line"
    assert (tmp_path / "en.toml").read_text(encoding="utf-8") == (
        '"runtime log line" = "runtime log line"\n'
    )
    assert (tmp_path / "es.toml").read_text(encoding="utf-8") == (
        '"runtime log line" = "runtime log line"\n'
    )
