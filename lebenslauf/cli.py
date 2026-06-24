from __future__ import annotations

import argparse
import sys
import os
from pathlib import Path
from select import select

from jinja2.exceptions import TemplateError as JinjaTemplateError

from selenium.webdriver import Chrome
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.command import Command
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException
)

from .template import Template, TemplateError
from .exceptions import LebenslaufError
from .package_resources import PackageResources
from .runtime_resources import ResourceManager
from .rendering import print_html, render_html, render_page
from .browser import BrowserSession
from .cv import load_resume, process_resume
from .constants import DEFAULT_TEMPLATE


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with (
            ResourceManager(
                args.template,
                keep_html=args.keep_html,
                package_resources=PackageResources("lebenslauf"),
            ) as mgr,
            BrowserSession(args.browser, headless=not args.repl) as driver
        ):
            process_template(
                base_template_source=mgr.base_template_source,
                cv_file=args.cv_file,
                template=mgr.template,
                file=mgr
            )
            render_page(driver, mgr, args.timeout)

            if args.repl:
                allowed_continue = repl(
                    mgr.base_template_source,
                    args.cv_file,
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

    except JinjaTemplateError as exc:
        pretty_print_jinja2_error(exc)
        return 1

    return 0


def pretty_print_error(exc: Exception):
    exc_type, exc_obj, exc_tb = sys.exc_info()
    exc_context = ""
    if exc_tb:
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        exc_context = f"{fname}:{exc_tb.tb_lineno}: "
    print(f"{exc_context}{exc}", file=sys.stderr)


def pretty_print_jinja2_error(exc: JinjaTemplateError):
    filename = None
    lineno = None

    if hasattr(exc, "filename") and getattr(exc, "filename") is not None:
        filename = str(getattr(exc, "filename"))
    if hasattr(exc, "lineno") and getattr(exc, "lineno") is not None:
        lineno = int(getattr(exc, "lineno"))

    tb = exc.__traceback__
    while tb is not None:
        frame_filename = tb.tb_frame.f_code.co_filename
        if frame_filename and frame_filename != "<template>":
            if not frame_filename.endswith(".py"):
                filename = frame_filename
                lineno = tb.tb_lineno
        tb = tb.tb_next

    if filename is not None and lineno is not None:
        print(f"{filename}:{lineno}: {exc}", file=sys.stderr)
        return
    if filename is not None:
        print(f"{filename}: {exc}", file=sys.stderr)
        return
    print(str(exc), file=sys.stderr)


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
    cv_file: Path,
    template: Template,
    file: ResourceManager
):
    cv = load_resume(cv_file)
    cv_data = process_resume(cv, template.manifest)
    language = cv_data["meta"]["language"]

    if language not in template.supported_languages:
        print(f"language {language} is not supported by the template")

    try:
        css_data = template.css.text
        html_data = template.html.text
        html = render_html(
            base_template_source,
            "lebenslauf/resources/template.html",
            html_data,
            str(template.html),
            css_data,
            cv_data,
            template,
            language
        )
        file.write(html)
    except (FileNotFoundError, IsADirectoryError) as exc:
        raise LebenslaufError(
            f"file {exc.filename} does not exist or is not a file"
        )


def repl(
    base_template_source: str,
    cv_path: Path,
    driver: Chrome,
    manager: ResourceManager,
    timeout: float
) -> bool:
    mtimes: dict[Path, float] = {cv_path: 0}

    if not sys.stdin.isatty():
        raise LebenslaufError("stdin must be an interactive terminal")

    print("Enter anything to exit REPL")
    while True:
        for path in manager.watch_paths:
            mtimes.setdefault(path, 0)

        template_reloaded = False
        for path, mtime in mtimes.items():
            if not path.exists():
                raise LebenslaufError(f"file {path} does not exist")

            stat = os.stat(path)
            if stat.st_mtime > mtime:
                if mtime != 0:
                    print(f"File changed: {path}")
                try:
                    if path == manager.template.meta and not template_reloaded:
                        manager.reload_template()
                        template_reloaded = True
                    process_template(
                        base_template_source,
                        cv_path,
                        manager.template,
                        manager
                    )
                    driver.refresh()
                except (LebenslaufError, TemplateError) as exc:
                    pretty_print_error(exc)
            mtimes[path] = stat.st_mtime

        for path in list(mtimes):
            if path != cv_path and path not in manager.watch_paths:
                del mtimes[path]

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
