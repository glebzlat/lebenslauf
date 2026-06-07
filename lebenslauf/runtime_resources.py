from __future__ import annotations

import os
import shutil
from contextlib import ExitStack
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Optional, TextIO

from .exceptions import LebenslaufError
from .package_resources import PackageResources
from .template import Template


class ResourceManager:
    def __init__(
        self,
        template_name: str,
        *,
        keep_html: Optional[Path],
        package_resources: PackageResources
    ):
        self.template_name = template_name
        self.keep_html = keep_html
        self.package_resources = package_resources
        self._base_template_source: str | None = None
        self._file_path: Path | None = None
        self._file: TextIO | None = None
        self._template: Template | None = None
        self._template_dir: Path | None = None
        self._tmpdir: TemporaryDirectory | None = None
        self._stack: ExitStack | None = None

    def write(self, text: str) -> None:
        assert self._file is not None
        self._file.seek(0)
        self._file.truncate()
        self._file.write(text)
        self._file.flush()
        os.fsync(self._file.fileno())

    def read(self) -> str:
        assert self._file is not None
        self._file.seek(0)
        return self._file.read()

    @property
    def path(self) -> Path:
        assert self._file_path is not None
        return self._file_path

    @property
    def directory(self) -> Path:
        if self.keep_html:
            return self.keep_html
        assert self._tmpdir is not None
        return Path(self._tmpdir.name)

    @property
    def watch_paths(self) -> tuple[Path, ...]:
        return self.template.watch_paths

    @property
    def base_template_source(self) -> str:
        assert self._base_template_source is not None
        return self._base_template_source

    @property
    def template(self) -> Template:
        assert self._template is not None
        return self._template

    def reload_template(self) -> None:
        assert self._template_dir is not None
        self._template = Template.from_dir(self._template_dir)
        self.sync_support_files()

    def sync_support_files(self) -> None:
        assert self._template is not None
        self._copy_pagedjs_bundle()
        self._copy_template_resources()

    def __enter__(self) -> ResourceManager:
        self._stack = ExitStack()
        try:
            self._init_workspace()
            self._base_template_source = self.package_resources.read_text(
                "resources",
                "template.html",
            )
            self._template_dir = self._resolve_template_dir()
            self._template = Template.from_dir(self._template_dir)
            self.sync_support_files()
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None
        if self._stack is not None:
            self._stack.close()
            self._stack = None
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
            self._tmpdir = None

    def _init_workspace(self) -> None:
        if self.keep_html:
            self.keep_html.mkdir(exist_ok=True, parents=True)
            self._file_path = self.keep_html / "index.html"
        else:
            self._tmpdir = TemporaryDirectory(prefix="lebenslauf-")
            self._file_path = Path(self._tmpdir.name) / "index.html"

        self._file = open(self._file_path, "w+", encoding="utf-8")

    def _resolve_template_dir(self) -> Path:
        template_path = Path(self.template_name).expanduser()
        if template_path.is_dir():
            return template_path

        assert self._stack is not None
        packaged_dir = self._stack.enter_context(
            self.package_resources.as_path(
                "resources",
                "templates",
                self.template_name,
            )
        )
        if not packaged_dir.is_dir():
            raise LebenslaufError(f"template {self.template_name} not found")
        return packaged_dir

    def _copy_pagedjs_bundle(self) -> None:
        with self.package_resources.as_path(
            "resources",
            "vendor",
            "paged.polyfill.min.js",
        ) as pagedjs_path:
            shutil.copy2(pagedjs_path, self.directory / pagedjs_path.name)

    def _copy_template_resources(self) -> None:
        for resource in self.template.resource_files:
            target = self.directory / resource.relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resource.source, target)
