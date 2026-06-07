from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

import yaml
import pydantic

from lebenslauf import models
from lebenslauf.exceptions import LebenslaufError


CONTACT_REWRITE_STRINGS = {
    "phone": {
        ""
        "*": r"tel:\0"
    },
    "email": {
        "*": r"mailto:\0"
    },
    "telegram": {
        "@(.*)": r"https://t.me/\1",
        "*": r"\0"
    },
    "linkedin": {
        "*": r"\0"
    },
    "github": {
        "@(.*)": r"https://github.com/\1",
        "*": r"\0"
    },
    "gitlab": {
        "@(.*)": r"https://github.com/\1",
        "*": r"\0"
    },
}


def load_resume(path: Path) -> models.Resume:
    if not path.exists():
        raise LebenslaufError(f"YAML file does not exist: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LebenslaufError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise LebenslaufError("YAML root must be a dictionary.")

    try:
        resume = models.Resume.model_validate(raw)
    except pydantic.ValidationError as exc:
        raise LebenslaufError(
            f"invalid resume YAML:\n{format_errors(exc)}"
        ) from exc

    return resume


def process_resume(
    cv: models.Resume,
    manifest: models.Manifest
) -> dict[str, Any]:
    data = cv.model_dump(mode="python")

    images = manifest.resources.images if manifest.resources else None
    raw_contacts = data["person"]["contacts"]
    contacts: list[dict[str, Any]] = []

    for contact_type, contact_text in raw_contacts.items():
        if not contact_text:
            continue

        contact: dict[str, Any] = {
            "title": contact_type,
            "text": contact_text,
            "href": _infer_contact_href(contact_type, contact_text),
            "icon": images.get(contact_type) if images else None
        }
        contacts.append(contact)

    data["person"]["contacts"] = contacts
    return data


def _infer_contact_href(contact_type: str, text: str) -> Optional[str]:
    text = text.replace(" ", "")
    rules = CONTACT_REWRITE_STRINGS.get(contact_type)
    if rules is None:
        return None

    for pattern, replacement in rules.items():
        if pattern == "*":
            return _rewrite_contact_text(text, replacement)

        match = re.fullmatch(pattern, text)
        if match is not None:
            return _rewrite_contact_text(text, replacement, match)

    return None


def _rewrite_contact_text(
    text: str,
    replacement: str,
    match: Optional[re.Match[str]] = None
) -> str:
    value = replacement.replace(r"\0", text)
    if match is None:
        return value

    for index in range(len(match.groups()), 0, -1):
        value = value.replace(fr"\{index}", match.group(index))
    return value


def format_errors(exc: Any) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        message = error["msg"]
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)
