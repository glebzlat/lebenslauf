from __future__ import annotations

import json
import sys
from pathlib import Path

from babel.messages.extract import extract_from_dir


def extract_strings(template_dir: Path) -> dict[str, str]:
    translations: dict[str, str] = {}

    for filename, lineno, message, comments, context in extract_from_dir(
        dirname=template_dir,
        method_map=[("**.html", "jinja2")],
        strip_comment_tags=False,
        comment_tags=(),
    ):
        if isinstance(message, (tuple, list)):
            # (singular, plural) messages
            for msg in message:
                translations[msg.strip()] = ""
        else:
            translations[message.strip()] = ""

    return translations


def main(template_dir: Path, output: Path) -> None:
    extracted = extract_strings(template_dir)

    # Preserve any translations the user already wrote
    if output.exists():
        with open(output, "r", encoding="utf-8") as fin:
            existing = json.load(fin)
        for k, v in existing.items():
            if v:
                extracted[k] = v

    with open(output, "w", encoding="utf-8") as fout:
        json.dump(
            extracted,
            fout,
            ensure_ascii=False,
            indent=2
        )
    print(f"{output}: {len(extracted)} strings")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
