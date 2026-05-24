from __future__ import annotations

import argparse
import base64
import shutil
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2
import pydantic
import yaml

import lebenslauf.models as models

from selenium.webdriver import Chrome
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.common.exceptions import JavascriptException
from selenium.webdriver.support.ui import WebDriverWait


class ResumeError(Exception):
    """Raised when the resume cannot be rendered or printed."""


@dataclass(frozen=True)
class Browser:
    label: str
    binary: str


DETECTED_BROWSERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Chromium", ("chromium", "chromium-browser")),
    ("Brave", ("brave-browser", "brave", "com.brave.Browser")),
    ("Chrome", ("google-chrome", "google-chrome-stable", "chrome")),
)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        render_pdf(
            yaml_path=args.yaml_file,
            template_path=args.template_file,
            output_path=args.output,
            browser_arg=args.browser,
            keep_html=args.keep_html,
            show_browser=args.show_browser,
            timeout=args.timeout,
        )
    except ResumeError as exc:
        print(exc, file=sys.stderr)
        return 1

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resume-formatter",
        description="Render a YAML resume through a Jinja HTML fragment and "
                    "print it to PDF.",
    )
    parser.add_argument(
        "yaml_file",
        type=Path,
        help="YAML resume description."
    )
    parser.add_argument(
        "template_file",
        type=Path,
        help="User-supplied Jinja HTML fragment."
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
        "--show-browser",
        action="store_true",
        help="Run the browser visibly instead of headless.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for browser layout before printing.",
    )
    return parser


def render_pdf(
    yaml_path: Path,
    template_path: Path,
    output_path: Path,
    browser_arg: str | None,
    keep_html: Path | None,
    show_browser: bool,
    timeout: float,
) -> None:
    data = load_resume(yaml_path)
    html = render_html(template_path, data)
    browser = resolve_browser(browser_arg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if keep_html is not None:
        keep_html.parent.mkdir(parents=True, exist_ok=True)
        keep_html.write_text(html, encoding="utf-8")
        html_path = keep_html
        cleanup_dir = None
    else:
        cleanup_dir = tempfile.TemporaryDirectory(prefix="resume-formatter-")
        html_path = Path(cleanup_dir.name) / "resume.html"
        html_path.write_text(html, encoding="utf-8")

    try:
        pdf_bytes = print_html(html_path, browser, show_browser, timeout)
        output_path.write_bytes(pdf_bytes)
    finally:
        if cleanup_dir is not None:
            cleanup_dir.cleanup()


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


def render_html(template_path: Path, data: dict[str, Any]) -> str:
    if not template_path.exists():
        raise ResumeError(f"template file does not exist: {template_path}")

    env = create_jinja_env(template_path.parent)
    user_template = env.get_template(template_path.name)
    user_html = user_template.render(**data, resume=data)

    system_template_path = Path(__file__).with_name("template.html")
    env = create_jinja_env(system_template_path.parent)
    system_template = env.get_template(system_template_path.name)

    return system_template.render(**data, resume=data, content=user_html)


def create_jinja_env(template: Path) -> jinja2.Environment:
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(template)),
        autoescape=jinja2.select_autoescape(("html", "xml")),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )


def resolve_browser(browser_arg: str | None) -> Browser:
    if browser_arg:
        browser_path = Path(browser_arg).expanduser()
        if browser_path.exists():
            return Browser(label=browser_path.name, binary=str(browser_path))

        found = shutil.which(browser_arg)
        if found:
            return Browser(label=browser_arg, binary=found)

        raise ResumeError(f"browser was specified but not found: {browser_arg}")

    for label, commands in DETECTED_BROWSERS:
        for command in commands:
            found = shutil.which(command)
            if found:
                return Browser(label=label, binary=found)

    names = ", ".join(label for label, _ in DETECTED_BROWSERS)
    raise ResumeError(
        f"no browser detected. Install one of: {names}; or pass --browser."
    )


def print_html(
    path: Path,
    browser: Browser,
    show_browser: bool,
    timeout: float
) -> bytes:
    options = Options()
    options.binary_location = browser.binary
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--no-sandbox")
    if not show_browser:
        options.add_argument("--headless=new")

    driver = None
    try:
        driver = Chrome(options=options)
        driver.get(path.resolve().as_uri())
        wait_for_layout(driver, timeout)
        if show_browser:
            input("enter any key to continue")

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
    except TimeoutException as exc:
        raise ResumeError(
            "browser layout timed out before the page was ready."
        ) from exc
    except WebDriverException as exc:
        raise ResumeError(
            f"browser print failed using {browser.label}: {exc.msg}"
        ) from exc
    finally:
        if driver is not None:
            driver.quit()


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
