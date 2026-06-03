import os
from pathlib import Path
from typing import Optional, TextIO
from tempfile import TemporaryDirectory


class ResourceManager:

    def __init__(self, keep_html: Optional[Path] = None):
        self.keep_html = keep_html
        self.file_path: Optional[Path] = None
        self.file: Optional[TextIO] = None
        self.tmpdir: Optional[TemporaryDirectory] = None

    def write(self, text: str) -> None:
        assert self.file is not None
        self.file.seek(0)
        self.file.truncate()
        self.file.write(text)
        self.file.flush()
        os.fsync(self.file.fileno())

    def read(self) -> str:
        assert self.file is not None
        self.file.seek(0)
        return self.file.read()

    @property
    def path(self) -> Path:
        assert self.file_path is not None
        return self.file_path

    @property
    def directory(self) -> Path:
        assert self.tmpdir is not None
        return Path(self.keep_html if self.keep_html else self.tmpdir.name)

    def __enter__(self):
        if self.keep_html:
            self.keep_html.mkdir(exist_ok=True, parents=True)
            self.file_path = self.keep_html / "index.html"
        else:
            self.tmpdir = TemporaryDirectory(prefix="lebenslauf-")
            self.file_path = Path(self.tmpdir.name) / "index.html"

        self.file = open(self.file_path, "w+", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.file.close()
        if self.tmpdir:
            self.tmpdir.cleanup()
