import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from transparentlation import cli
from transparentlation.toml_io import load_string_table


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def translate_template(self, request):
        self.calls.append(request)
        prefix = {
            "es": "Hola",
            "fr": "Bonjour",
        }.get(request.target_locale, "Translated")
        if request.template == "Hello {name}":
            return f"{prefix} {{name}}"
        return f"{prefix} {request.template}"


def test_tt_translate_fills_missing_entries(monkeypatch, tmp_path):
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    (locale_dir / "en.toml").write_text(
        '"Hello {name}" = "Hello {name}"\n'
        '"Goodbye" = "Goodbye"\n',
        encoding="utf-8",
    )
    (locale_dir / "es.toml").write_text('"Goodbye" = "Adiós"\n', encoding="utf-8")
    (locale_dir / "fr.toml").write_text('"Hello {name}" = "Hello {name}"\n', encoding="utf-8")

    monkeypatch.setattr(cli, "OpenAICompatibleClient", FakeClient)

    exit_code = cli.main(
        [
            "translate",
            "--locale-dir",
            str(locale_dir),
            "--source-locale",
            "en",
            "--model",
            "demo-model",
            "--api-key",
            "demo-key",
        ]
    )

    assert exit_code == 0
    assert load_string_table(str(locale_dir / "es.toml")) == {
        "Goodbye": "Adiós",
        "Hello {name}": "Hola {name}",
    }
    assert load_string_table(str(locale_dir / "fr.toml")) == {
        "Goodbye": "Bonjour Goodbye",
        "Hello {name}": "Bonjour {name}",
    }


def test_tt_translate_dry_run_does_not_write(monkeypatch, tmp_path):
    locale_dir = tmp_path / "locales"
    locale_dir.mkdir()
    (locale_dir / "en.toml").write_text('"Hello {name}" = "Hello {name}"\n', encoding="utf-8")
    (locale_dir / "es.toml").write_text("", encoding="utf-8")

    monkeypatch.setattr(cli, "OpenAICompatibleClient", FakeClient)

    exit_code = cli.main(
        [
            "translate",
            "--locale-dir",
            str(locale_dir),
            "--source-locale",
            "en",
            "--target-locales",
            "es",
            "--model",
            "demo-model",
            "--api-key",
            "demo-key",
            "--dry-run",
        ]
    )

    assert exit_code == 0
    assert load_string_table(str(locale_dir / "es.toml")) == {}
