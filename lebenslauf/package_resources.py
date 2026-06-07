from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Iterator


class PackageResources:
    def __init__(self, anchor: str):
        self.anchor = anchor

    def read_text(self, *parts: str, encoding: str = "utf-8") -> str:
        return self._resource(*parts).read_text(encoding=encoding)

    @contextmanager
    def as_path(self, *parts: str) -> Iterator[Path]:
        resource = self._resource(*parts)
        with resources.as_file(resource) as path:
            yield path

    def _resource(self, *parts: str):
        return resources.files(self.anchor).joinpath(*parts)
