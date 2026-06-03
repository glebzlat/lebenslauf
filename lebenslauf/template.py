from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path

import yaml

from lebenslauf import models
from .exceptions import LebenslaufError


MANIFEST_FILENAME = "manifest.yaml"


class TemplateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Template:

    manifest: models.Manifest

    @staticmethod
    def from_dir(directory: Path) -> Template:
        path = directory / MANIFEST_FILENAME
        if not path.is_file():
            raise TemplateError(f"{path} does not exist or is not a file")
        with open(path, "r", encoding="utf-8") as fin:
            data = yaml.safe_load(fin)

        manifest = models.Manifest.model_validate(
            data,
            context={"base_dir": directory}
        )
        return Template(manifest)

    @property
    def html(self) -> Path:
        return self.manifest.html

    @property
    def css(self) -> Path:
        return self.manifest.css

    @property
    def resources(self) -> tuple[Path, ...]:
        return tuple(self.resources)


def resolve_template(template: str) -> Template:
    template_path = Path(template)
    if template_path.is_dir():
        return Template.from_dir(template_path)

    try:
        template_path = (
            importlib.resources.files("lebenslauf")
            .joinpath("resources", "templates", template)
        )
        is_dir = template_path.is_dir()
    except Exception:
        is_dir = False

    if not is_dir:
        raise LebenslaufError(f"template {template} not found")

    return Template.from_dir(template_path)
