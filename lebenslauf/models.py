from __future__ import annotations

from typing import Annotated, Optional
from pathlib import Path

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    ValidationInfo
)


NonEmptyStr = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Contacts(StrictModel):
    phone: str | None = None
    mail: str | None = None
    telegram: str | None = None
    linkedin: str | None = None
    github: str | None = None
    gitlab: str | None = None


class Person(StrictModel):
    name: NonEmptyStr
    role: NonEmptyStr
    contacts: Contacts


class Duration(StrictModel):
    start: NonEmptyStr
    end: NonEmptyStr


class Experience(StrictModel):
    company: NonEmptyStr
    role: NonEmptyStr
    duration: Duration
    responsibilities: list[NonEmptyStr]


class Certificate(StrictModel):
    name: NonEmptyStr
    issuer: NonEmptyStr


class Language(StrictModel):
    name: NonEmptyStr
    level: NonEmptyStr


class Specialization(StrictModel):
    type: NonEmptyStr
    name: NonEmptyStr


class Education(StrictModel):
    academy: NonEmptyStr
    specialization: Specialization
    duration: Duration


class Resume(StrictModel):
    person: Person
    experience: list[Experience] = Field(default_factory=list)
    skills: list[NonEmptyStr] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)


class Manifest(StrictModel):
    meta: Path
    html: Path
    css: Path
    resources: Optional[list[Path]] = None

    @field_validator("*", mode="before")
    @classmethod
    def _validate_fields(cls, v, info: ValidationInfo):
        assert info.context is not None and "base_dir" in info.context
        base_dir = Path(info.context["base_dir"])

        if isinstance(v, list):
            lst = []
            for p in v:
                p = Path(p)
                if not p.is_absolute():
                    p = base_dir / p
                    if not p.is_file():
                        raise ValueError(
                            f"file {p} does not exist or is not a file"
                        )
                lst.append(p)
            return lst

        path = Path(v)
        if not path.is_absolute():
            path = base_dir / path
        if not path.is_file():
            raise ValueError(f"file {path} does not exist or is not a file")
        return path
