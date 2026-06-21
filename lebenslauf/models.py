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
from pydantic_extra_types.language_code import LanguageAlpha2


NonEmptyStr = Annotated[str, Field(min_length=1)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Contacts(StrictModel):
    phone: str | None = None
    email: str | None = None
    telegram: str | None = None
    linkedin: str | None = None
    github: str | None = None
    gitlab: str | None = None
    website: str | None = None


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
    duration: Optional[Duration]
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
    duration: Optional[Duration]


class Meta(StrictModel):
    language: Optional[LanguageAlpha2] = LanguageAlpha2("en")


class Resume(StrictModel):
    person: Person
    experience: list[Experience] = Field(default_factory=list)
    skills: list[NonEmptyStr] = Field(default_factory=list)
    certificates: list[Certificate] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)

    # Meta is present and has default values even when the user
    # does not specify it.
    meta: Meta = Field(default_factory=Meta)


class Resources(StrictModel):
    images: Optional[dict[str, Path]] = None
    fonts: Optional[dict[str, Path]] = None


class TemplateLanguages(StrictModel):
    original: LanguageAlpha2
    translations: Optional[dict[LanguageAlpha2, Path]] = None


class Manifest(StrictModel):
    meta: Path
    html: Path
    css: Path
    resources: Optional[Resources] = None
    languages: TemplateLanguages
