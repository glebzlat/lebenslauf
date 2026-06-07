from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from lebenslauf import models


MANIFEST_FILENAME = "manifest.yaml"


class TemplateError(RuntimeError):
    pass


@dataclass(frozen=True)
class TemplateResource:
    source: Path
    relative_path: Path


@dataclass(frozen=True)
class Template:
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
            context={"base_dir": directory}
        )
        return Template(base_dir=directory, manifest=manifest)

    @property
    def html(self) -> Path:
        return self.manifest.html

    @property
    def css(self) -> Path:
        return self.manifest.css

    @property
    def resource_paths(self) -> tuple[Path, ...]:
        return tuple(resource.source for resource in self.resource_files)

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
        return tuple(paths)

    @property
    def meta(self) -> Path:
        return self.manifest.meta

    @property
    def watch_paths(self) -> tuple[Path, ...]:
        return (self.meta, self.html, self.css, *self.resource_paths)

    def _to_resource(self, source: Path) -> TemplateResource:
        try:
            relative_path = source.relative_to(self.base_dir)
        except ValueError:
            relative_path = Path(source.name)
        return TemplateResource(source=source, relative_path=relative_path)
