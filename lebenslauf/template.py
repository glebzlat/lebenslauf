from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any

import yaml


class TemplateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Template:

    html: Path
    css: Path
    resources: list[Path] = field(default_factory=list)

    @staticmethod
    def from_dir(directory: Path) -> Template:
        meta = Template.get_meta(directory)

        if not isinstance(meta, dict):
            raise TemplateError("meta must be a dict")

        html_path = Template.get_path(meta, "html", directory)
        css_path = Template.get_path(meta, "css", directory)

        resources = Template.get_resources(meta, directory)

        return Template(
            html=html_path,
            css=css_path,
            resources=resources
        )

    @staticmethod
    def get_meta(directory: Path) -> Any:
        path = directory / "meta.yaml"
        if not path.is_file():
            raise TemplateError(f"{path} does not exist or is not a file")

        with open(path, "r", encoding="utf-8") as fin:
            return yaml.safe_load(fin)

    @staticmethod
    def get_path(meta: dict, key: str, root: Path) -> Path:
        value = meta.get(key)
        if value is None:
            raise TemplateError(f"key {key} not found in meta")

        path = root / value
        if not path.is_file():
            raise TemplateError(
                f"{key}: {value} does not exist or is not a file")

        return path

    @staticmethod
    def get_resources(meta: dict, root: Path) -> Optional[list[Path]]:
        resources_section = meta.get("resources")
        if resources_section is None:
            return

        if not isinstance(resources_section, list):
            raise TemplateError("resources must be a list")

        resources = []
        for rc in resources_section:
            path = root / rc
            if not path.is_file():
                raise TemplateError(
                    f"resources: {rc} does not exist or is not a file"
                )
            resources.append(path)

        return resources
