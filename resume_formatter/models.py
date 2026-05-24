from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


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
