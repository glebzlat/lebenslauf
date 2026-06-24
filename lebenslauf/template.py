from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from . import models
from .constants import MANIFEST_FILENAME


class TemplateError(RuntimeError):
    pass


class TemplateResource(Path):

    def __init__(self, base_dir: Path, resource: Path):
        super().__init__(base_dir, resource)
        self.base_dir = base_dir
        self.resource = resource

        if not self.is_file():
            raise TemplateError(
                f"{self.resource} does not exist or is not a file"
            )

    @property
    def text(self) -> str:
        with open(self, "r", encoding="utf-8") as fin:
            return fin.read()

    @property
    def relative_path(self) -> Path:
        return self.resource.relative_to(self.base_dir)

    @property
    def source(self) -> Path:
        return self.resource


@dataclass(frozen=True)
class Template:
    name: str
    base_dir: Path
    manifest: models.Manifest

    @staticmethod
    def from_dir(directory: Path) -> Template:
        path = directory / MANIFEST_FILENAME
        if not path.is_file():
            raise TemplateError(f"{path} does not exist or is not a file")
        with open(path, "r", encoding="utf-8") as fin:
            data = yaml.safe_load(fin)

        manifest = models.Manifest.model_validate(
            {"meta": MANIFEST_FILENAME, **data},
        )
        return Template(
            name=directory.name,
            base_dir=directory,
            manifest=manifest
        )

    @property
    def html(self) -> TemplateResource:
        return self._to_resource(self.manifest.html)

    @property
    def css(self) -> TemplateResource:
        return self._to_resource(self.manifest.css)

    @property
    def resource_paths(self) -> tuple[TemplateResource, ...]:
        return self.resource_files

    @property
    def resource_files(self) -> tuple[TemplateResource, ...]:
        if self.manifest.resources is None:
            return ()
        resources = self.manifest.resources
        paths: list[TemplateResource] = []
        if resources.images:
            paths.extend(
                self._to_resource(path) for path in resources.images.values()
            )
        if resources.fonts:
            paths.extend(
                self._to_resource(path) for path in resources.fonts.values()
            )
        if trans := self.translation_files:
            paths.extend(self._to_resource(path) for path in trans)
        return tuple(paths)

    @property
    def meta(self) -> TemplateResource:
        return self._to_resource(self.manifest.meta)

    @property
    def watch_paths(self) -> tuple[TemplateResource, ...]:
        return (self.meta, self.html, self.css, *self.resource_paths)

    @property
    def supported_languages(self) -> tuple[str, ...]:
        langs = [self.manifest.languages.original]
        if self.manifest.languages.translations is not None:
            langs.extend(self.manifest.languages.translations.keys())
        return tuple(langs)

    @property
    def translation_files(self) -> tuple[TemplateResource, ...]:
        translations = self.manifest.languages.translations or {}
        return tuple(self._to_resource(t) for t in translations.values())

    def get_translation(self, language: str) -> Optional[Path]:
        translations = self.manifest.languages.translations
        if translations is None:
            return None
        translation_file = translations.get(
            language)  # type: ignore[call-overload]
        if translation_file is None:
            return None
        return self._to_resource(translation_file)

    def _to_resource(self, source: Path) -> TemplateResource:
        return TemplateResource(self.base_dir, source)
