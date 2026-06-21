from __future__ import annotations

import json
from pathlib import Path
from typing import Callable, Any
from functools import wraps


def strip_whitespace(fn: Callable) -> Callable:

    @wraps(fn)
    def _wrapper(*args: Any, **kwargs: Any) -> Any:
        stripped_args = (
            arg.strip() if isinstance(arg, str) else arg
            for arg in args
        )
        kwargs = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in kwargs.items()
        }
        return fn(*stripped_args, **kwargs)

    return _wrapper


class JsonTranslations:
    """gettext-compatible object backed by a single JSON file."""

    # Jinja2 reads these:
    domain = "messages"
    newstyle = True   # enables pgettext/npgettext directly

    @staticmethod
    def load_translations(path: Path | None) -> JsonTranslations:
        """Load a translation file, or an empty catalog if `path` is None."""
        if path is None:
            return JsonTranslations()
        with open(path, "r", encoding="utf-8") as fin:
            return JsonTranslations(json.load(fin))

    def __init__(self, messages: dict[str, str] | None = None) -> None:
        self._messages: dict[str, str] = dict(messages or {})

    @strip_whitespace
    def gettext(self, message: str) -> str:
        return self._messages.get(message, message)

    @strip_whitespace
    def ngettext(self, singular: str, plural: str, n: int) -> str:
        template = singular if n == 1 else plural
        return self._messages.get(template, template)

    @strip_whitespace
    def pgettext(self, context: str, message: str) -> str:
        key = f"{context}\x04{message}"   # gettext context separator
        return self._messages.get(key, message)

    @strip_whitespace
    def npgettext(self, context: str, singular: str, plural: str, n: int) -> str:
        key = f"{context}\x04{(singular if n == 1 else plural)}"
        return self._messages.get(key, singular if n == 1 else plural)

