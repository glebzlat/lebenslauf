from __future__ import annotations

import argparse
import shutil
import sys
import os
import importlib
from pathlib import Path
from typing import Any
from select import select

import pydantic
import yaml

from selenium.webdriver import Chrome
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.command import Command
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException
)

from lebenslauf import models
from lebenslauf.template import Template, TemplateError, resolve_template
from lebenslauf.exceptions import LebenslaufError
from lebenslauf.resource_manager import ResourceManager
from lebenslauf.rendering import print_html, render_html, render_page
from lebenslauf.browser import BrowserSession


DEFAULT_TEMPLATE = "laconic"


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    anchor = "lebenslauf"

    base_template_source = (
        importlib.resources.files(anchor)
        .joinpath("resources", "template.html")
        .read_text(encoding="utf-8")
    )

    pagedjs_ref = (
        importlib.resources
        .files(anchor)
        .joinpath("resources", "vendor", "paged.polyfill.min.js")
    )

    try:
        template = resolve_template(args.template)

        with (
            ResourceManager(keep_html=args.keep_html) as mgr,
            BrowserSession(args.browser, headless=not args.repl) as driver
        ):
            with importlib.resources.as_file(pagedjs_ref) as pagedjs_path:
                shutil.copy2(pagedjs_path, mgr.directory)

            process_template(
                base_template_source=base_template_source,
                cv=args.cv_file,
                template=template,
                file=mgr
            )
            render_page(driver, mgr, args.timeout)

            if args.repl:
                allowed_continue = repl(
                    base_template_source,
                    args.cv_file,
                    template,
                    driver,
                    mgr,
                    args.timeout
                )
                if not allowed_continue:
                    return 0

            pdf_bytes = print_html(driver)
            args.output.write_bytes(pdf_bytes)

    except (LebenslaufError, TemplateError) as exc:
        pretty_print_error(exc)
        return 1

    return 0


def pretty_print_error(exc: Exception):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    exc_context = ""
    if exc_tb:
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        exc_context = f"{fname}:{exc_tb.tb_lineno}: "
    print(f"{exc_context}{exc}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render a YAML resume through a Jinja HTML fragment and "
                    "print it to PDF.",
    )
    parser.add_argument(
        "cv_file",
        type=Path,
        help="YAML CV description."
    )
    parser.add_argument(
        "-t",
        "--template",
        default=DEFAULT_TEMPLATE,
        help="Template name or path."
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path("resume.pdf"),
        help="PDF output path. Defaults to resume.pdf.",
    )
    parser.add_argument(
        "-b",
        "--browser",
        help="Chromium-based browser executable name or absolute path.",
    )
    parser.add_argument(
        "--keep-html",
        type=Path,
        help="Write the rendered intermediate HTML along with resources into "
        "this directory.",
    )
    parser.add_argument(
        "-r",
        "--repl",
        action="store_true",
        help="Enter interactive mode."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for browser layout before printing.",
    )
    return parser


def process_template(
    base_template_source: str,
    cv: Path,
    template: Template,
    file: ResourceManager
):
    cv_data = load_resume(cv)
    try:
        with open(template.css, "r", encoding="utf-8") as fin:
            css_data = fin.read()
        with open(template.html, "r", encoding="utf-8") as fin:
            html_data = fin.read()
        html = render_html(base_template_source, html_data, css_data, cv_data)
        file.write(html)
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise LebenslaufError(
            f"file {exc.filename} does not exist or is not a file"
        )


def load_resume(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise LebenslaufError(f"YAML file does not exist: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise LebenslaufError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise LebenslaufError("YAML root must be a dictionary.")

    try:
        resume = models.Resume.model_validate(raw)
    except pydantic.ValidationError as exc:
        raise LebenslaufError(
            f"invalid resume YAML:\n{format_errors(exc)}"
        ) from exc

    return resume.model_dump()


def format_errors(exc: Any) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        message = error["msg"]
        lines.append(f"- {location}: {message}")
    return "\n".join(lines)


def repl(
    base_template_source: str,
    cv_path: Path,
    template: Template,
    driver: Chrome,
    file: ResourceManager,
    timeout: float
) -> bool:
    mtimes: dict[Path, float] = {
        cv_path: 0,
        template.html: 0,
        template.css: 0,
        template.meta: 0,
        **{r: 0 for r in template.resources}
    }

    if not sys.stdin.isatty():
        raise LebenslaufError("stdin must be an interactive terminal")

    print("Enter anything to exit REPL")
    while True:
        for path, mtime in mtimes.items():
            if not path.exists():
                raise LebenslaufError(f"file {path} does not exist")

            stat = os.stat(path)
            if stat.st_mtime > mtime:
                if mtime != 0:
                    print(f"File changed: {path}")
                try:
                    process_template(
                        base_template_source,
                        cv_path,
                        template,
                        file
                    )
                    driver.refresh()
                except (LebenslaufError, TemplateError) as exc:
                    pretty_print_error(exc)
            mtimes[path] = stat.st_mtime

        try:
            driver.execute(Command.GET_CURRENT_URL)
        except (
            InvalidSessionIdException,
            NoSuchWindowException,
            WebDriverException
        ):
            print("Browser was closed, exiting...")
            return False

        ready = select([sys.stdin], [], [], 0.5)
        if ready[0]:
            sys.stdin.readline()
            return True
