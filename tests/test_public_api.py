import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from autolang import TransparentTranslator, install


def test_install_returns_translator_instance(tmp_path):
    (tmp_path / "es.toml").write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")

    translator = install("es", str(tmp_path))

    assert isinstance(translator, TransparentTranslator)


def test_install_result_can_be_bound_to_module_level_tt(tmp_path):
    (tmp_path / "es.toml").write_text('"Hello {name}" = "Hola {name}"\n', encoding="utf-8")
    translator = install("es", str(tmp_path))
    tt = translator.translate
    name = "Alice"

    assert tt(f"Hello {name}") == "Hola Alice"


def test_bound_tt_supports_f_string_conversion_and_format_spec(tmp_path):
    (tmp_path / "es.toml").write_text(
        '"Price: {price:.2f}" = "Precio: {price:.2f}"\n'
        '"Debug: {obj!r}" = "Depurar: {obj!r}"\n',
        encoding="utf-8",
    )
    translator = install("es", str(tmp_path))
    tt = translator.translate
    price = 12.345

    class Demo:
        def __repr__(self) -> str:
            return "<demo>"

    obj = Demo()

    assert tt(f"Price: {price:.2f}") == "Precio: 12.35"
    assert tt(f"Debug: {obj!r}") == "Depurar: <demo>"
