from __future__ import annotations

import argparse
import base64
import shutil
import sys
import os
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Any, Optional, TextIO
from select import select

import jinja2
import pydantic
import yaml

from selenium.webdriver import Chrome
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.support.ui import WebDriverWait

from lebenslauf import models


class ResumeError(Exception):
    """Raised when the resume cannot be rendered or printed."""


@dataclass(frozen=True)
class Browser:

    DETECTED_BROWSERS: ClassVar[tuple[tuple[str, tuple[str, ...]], ...]] = {
        "Chromium": ("chromium", "chromium-browser"),
        "Brave": ("brave-browser", "brave", "com.brave.Browser"),
        "Chrome": ("google-chrome", "google-chrome-stable", "chrome")
    }

    label: str
    binary: str

    @staticmethod
    def resolve(browser_arg: str | None) -> Browser:
        if browser_arg:
            browser_path = Path(browser_arg).expanduser()
            if browser_path.exists():
                return Browser(
                    label=browser_path.name,
                    binary=str(browser_path)
                )

            found = shutil.which(browser_arg)
            if found:
                return Browser(label=browser_arg, binary=found)

            raise ResumeError(
                f"browser was specified but not found: {browser_arg}"
            )

        for label, commands in Browser.DETECTED_BROWSERS.items():
            for command in commands:
                found = shutil.which(command)
                if found:
                    return Browser(label=label, binary=found)

        names = ", ".join(
            label for label, _ in Browser.DETECTED_BROWSERS.items()
        )
        raise ResumeError(
            f"no browser detected. Install one of: {names}; or pass --browser."
        )


class File:

    def __init__(self, keep_html: Optional[Path] = None):
        self.keep_html = keep_html
        self.file_path = None
        self.file = None
        self.tmpdir = None

    def write(self, text: str) -> None:
        self.file.seek(0)
        self.file.truncate()
        self.file.write(text)
        self.file.flush()
        os.fsync(self.file.fileno())

    def read(self) -> str:
        self.file.seek(0)
        return self.file.read()

    @property
    def path(self) -> Path:
        return self.file_path

    def __enter__(self):
        if self.keep_html:
            self.file_path = self.keep_html
        else:
            self.tmpdir = tempfile.TemporaryDirectory(prefix="lebenslauf-")
            self.file_path = Path(self.tmpdir.name) / "index.html"

        self.file = open(self.file_path, "w+", encoding="utf-8")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.file.close()
        if self.tmpdir:
            self.tmpdir.cleanup()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        with File(args.keep_html) as file:
            process_template(
                cv=args.cv_file,
                template=args.template_file,
                style=args.style_file,
                file=file
            )
            driver = init_driver(args.browser, args.repl)
            render_page(driver, file, args.timeout)

            if args.repl:
                repl(
                    args.cv_file,
                    args.template_file,
                    args.style_file,
                    driver,
                    file,
                    args.timeout
                )

        pdf_bytes = print_html(driver)
        args.output.write_bytes(pdf_bytes)

    except ResumeError as exc:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print(f"{fname}:{exc_tb.tb_lineno}: {exc}", file=sys.stderr)
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-formatter",
        description="Render a YAML resume through a Jinja HTML fragment and "
                    "print it to PDF.",
    )
    parser.add_argument(
        "cv_file",
        type=Path,
        help="YAML resume description."
    )
    parser.add_argument(
        "template_file",
        type=Path,
        help="User-supplied Jinja HTML fragment."
    )
    parser.add_argument(
        "style_file",
        type=Path,
        help="CSS styles for user-supplied Jinja HTML fragment."
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
        help="Write the rendered intermediate HTML to this path.",
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


def init_driver(browser_arg: str, repl: bool) -> Chrome:
    browser = Browser.resolve(browser_arg)
    options = Options()
    options.binary_location = browser.binary
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    if not repl:
        options.add_argument("--headless=new")
    return Chrome(options=options)


def init_file(keep_html: Optional[Path]) -> TextIO:
    if keep_html:
        return open(keep_html, "w+", encoding="utf-8")
    return tempfile.TemporaryFile("w+", encoding="utf-8")


def process_template(cv: Path, template: Path, style: Path, file: File):
    data = load_resume(cv)
    with open(style, "r", encoding="utf-8") as fin:
        css = fin.read()
    html = render_html(template, css, data)
    file.write(html)


def load_resume(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ResumeError(f"YAML file does not exist: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ResumeError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ResumeError("YAML root must be a dictionary.")

    try:
        resume = models.Resume.model_validate(raw)
    except pydantic.ValidationError as exc:
        raise ResumeError(
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


def render_html(template_path: Path, style: str, data: dict[str, Any]) -> str:
    if not template_path.exists():
        raise ResumeError(f"template file does not exist: {template_path}")

    env = create_jinja_env(template_path.parent)
    user_template = env.get_template(template_path.name)
    user_html = user_template.render(**data, resume=data)

    system_template_path = Path(__file__).with_name("template.html")
    env = create_jinja_env(system_template_path.parent)
    system_template = env.get_template(system_template_path.name)

    return system_template.render(
        **data,
        resume=data,
        style=style,
        content=user_html
    )


def create_jinja_env(template: Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template)),
        autoescape=jinja2.select_autoescape(("html", "xml")),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def render_page(driver: Chrome, file: File, timeout: float):
    driver.get(file.path.resolve().as_uri())
    wait_for_layout(driver, timeout)


def repl(
    cv_path: Path,
    template_path: Path,
    style_path: Path,
    driver: Chrome,
    file: File,
    timeout: float
):
    mtimes: dict[Path, int] = {
        cv_path: 0,
        template_path: 0,
        style_path: 0
    }

    if not sys.stdin.isatty():
        raise ResumeError("stdin must be an interactive terminal")

    print("Enter anything to exit REPL")
    while True:
        for path, mtime in mtimes.items():
            if not path.exists():
                raise ResumeError(f"file {path} does not exist")

            stat = os.stat(path)
            if stat.st_mtime > mtime:
                if mtime != 0:
                    print(f"File changed: {path}")
                try:
                    process_template(cv_path, template_path, style_path, file)
                    driver.refresh()
                except Exception as exc:
                    print(exc, file=sys.stderr)
            mtimes[path] = stat.st_mtime

        ready = select([sys.stdin], [], [], 0.5)
        if ready[0]:
            sys.stdin.readline()
            break


def print_html(
    driver: Chrome,
) -> bytes:
    try:
        print_options = PrintOptions()
        print_options.orientation = "portrait"
        print_options.page_width = 21.0
        print_options.page_height = 29.7
        print_options.margin_top = 0
        print_options.margin_bottom = 0
        print_options.margin_left = 0
        print_options.margin_right = 0
        print_options.shrink_to_fit = False

        encoded_pdf = driver.print_page(print_options)
        return base64.b64decode(encoded_pdf)
    except WebDriverException as exc:
        raise ResumeError(f"browser print failed: {exc.msg}") from exc


def wait_for_layout(driver: Any, timeout: float) -> None:

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            driver.execute_script(
                "if (window.resumeFormatterLayout) {"
                "    window.resumeFormatterLayout();"
                "}"
            )
            ready = driver.execute_script(
                "return document.readyState === 'complete' && ("
                "    !window.resumeFormatterReady ||"
                "    window.resumeFormatterReady === true"
                ");"
            )
        except JavascriptException:
            ready = False

        if ready:
            return

        time.sleep(0.1)

    WebDriverWait(driver, 0.1).until(lambda _: False)
