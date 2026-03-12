from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from babel import Locale

from .toml_io import load_string_table, write_string_table


TRANSLATION_SYSTEM_PROMPT = """You translate application localization templates.
Preserve placeholders like {name} or {fmt.date(now)} exactly.
Do not rename, remove, or invent placeholders.
Return JSON only with this shape: {"text":"translated template"}."""


@dataclass(slots=True)
class TranslationRequest:
    source_locale: str
    target_locale: str
    source_language: str
    target_language: str
    template: str


class OpenAICompatibleClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 60.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout

    def translate_template(self, request: TranslationRequest) -> str:
        payload = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": TRANSLATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Source language: {request.source_language}\n"
                        f"Target language: {request.target_language}\n"
                        f"Source locale: {request.source_locale}\n"
                        f"Target locale: {request.target_locale}\n\n"
                        "Template:\n"
                        f"{request.template}\n"
                    ),
                },
            ],
            "response_format": {"type": "json_object"},
        }
        response = self._post_json("/chat/completions", payload)
        content = self._extract_content(response)

        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Model returned invalid JSON: {content}") from exc

        text = data.get("text")
        if not isinstance(text, str) or not text:
            raise RuntimeError(f"Model response missing translated text: {content}")

        return text

    def _post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:  # pragma: no cover - network error path
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"API request failed with {exc.code}: {body}") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network error path
            raise RuntimeError(f"API request failed: {exc.reason}") from exc

    def _extract_content(self, response: dict[str, object]) -> str:
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"Unexpected API response: {response}")

        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise RuntimeError(f"Unexpected API response: {response}")

        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise RuntimeError(f"Unexpected API response: {response}")

        content = message.get("content")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    text = item.get("text")
                    if isinstance(text, str):
                        text_parts.append(text)
            if text_parts:
                return "".join(text_parts)

        raise RuntimeError(f"Unexpected API response: {response}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tt", description="Transparentlation developer tools.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    translate_parser = subparsers.add_parser(
        "translate",
        help="Translate locale TOML files through an OpenAI-compatible API.",
    )
    translate_parser.add_argument("--locale-dir", default="locales")
    translate_parser.add_argument("--source-locale", default="en")
    translate_parser.add_argument("--target-locales", nargs="*", default=None)
    translate_parser.add_argument("--source-language", default=None)
    translate_parser.add_argument("--model", default=None)
    translate_parser.add_argument("--base-url", default=None)
    translate_parser.add_argument("--api-key", default=None)
    translate_parser.add_argument("--timeout", type=float, default=60.0)
    translate_parser.add_argument("--overwrite", action="store_true")
    translate_parser.add_argument("--dry-run", action="store_true")
    translate_parser.set_defaults(handler=handle_translate_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.handler(args)


def handle_translate_command(args: argparse.Namespace) -> int:
    locale_dir = Path(args.locale_dir)
    source_locale = normalize_language(args.source_locale)
    source_path = locale_dir / f"{source_locale}.toml"
    source_entries = load_string_table(str(source_path))
    if not source_entries:
        raise SystemExit(f"Source locale file not found or empty: {source_path}")

    model = args.model or os.environ.get("TT_MODEL") or os.environ.get("OPENAI_MODEL")
    if not model:
        raise SystemExit("Missing model. Pass --model or set TT_MODEL/OPENAI_MODEL.")

    api_key = args.api_key or os.environ.get("TT_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing API key. Pass --api-key or set TT_API_KEY/OPENAI_API_KEY.")

    base_url = args.base_url or os.environ.get("TT_BASE_URL") or os.environ.get("OPENAI_BASE_URL")
    if not base_url:
        base_url = "https://api.openai.com/v1"

    client = OpenAICompatibleClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
        timeout=args.timeout,
    )

    source_language = args.source_language or locale_display_name(source_locale)
    target_locales = resolve_target_locales(locale_dir, source_locale, args.target_locales)
    if not target_locales:
        raise SystemExit("No target locale TOML files found.")

    total_translated = 0
    for target_locale in target_locales:
        translated_count = translate_locale_file(
            client=client,
            locale_dir=locale_dir,
            source_locale=source_locale,
            source_language=source_language,
            target_locale=target_locale,
            source_entries=source_entries,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
        total_translated += translated_count

    print(f"Updated {len(target_locales)} locale file(s), translated {total_translated} entry/entries.")
    return 0


def translate_locale_file(
    *,
    client: OpenAICompatibleClient,
    locale_dir: Path,
    source_locale: str,
    source_language: str,
    target_locale: str,
    source_entries: dict[str, str],
    overwrite: bool,
    dry_run: bool,
) -> int:
    target_path = locale_dir / f"{target_locale}.toml"
    target_entries = load_string_table(str(target_path))
    target_language = locale_display_name(target_locale)

    translated_count = 0
    for key, source_text in source_entries.items():
        current_text = target_entries.get(key)
        if not should_translate_entry(key, source_text, current_text, overwrite):
            continue

        translated_text = client.translate_template(
            TranslationRequest(
                source_locale=source_locale,
                target_locale=target_locale,
                source_language=source_language,
                target_language=target_language,
                template=source_text,
            )
        )
        target_entries[key] = translated_text
        translated_count += 1

    if translated_count and not dry_run:
        write_string_table(str(target_path), target_entries)

    return translated_count


def should_translate_entry(
    key: str,
    source_text: str,
    current_text: str | None,
    overwrite: bool,
) -> bool:
    if overwrite:
        return True

    if current_text is None:
        return True

    return current_text == key or current_text == source_text


def resolve_target_locales(
    locale_dir: Path,
    source_locale: str,
    explicit_targets: list[str] | None,
) -> list[str]:
    if explicit_targets:
        return [normalize_language(locale) for locale in explicit_targets if normalize_language(locale) != source_locale]

    discovered = []
    for path in sorted(locale_dir.glob("*.toml")):
        locale_name = normalize_language(path.stem)
        if locale_name != source_locale:
            discovered.append(locale_name)

    return discovered


def normalize_language(locale_name: str) -> str:
    return Locale.parse(locale_name).language


def locale_display_name(locale_name: str) -> str:
    locale = Locale.parse(locale_name)
    return locale.get_display_name("en").title()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
