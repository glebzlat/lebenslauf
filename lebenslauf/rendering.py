from __future__ import annotations

import base64
import time
from typing import Any

import jinja2

from selenium.webdriver import Chrome
from selenium.webdriver.common.print_page_options import PrintOptions
from selenium.common.exceptions import WebDriverException, JavascriptException
from selenium.webdriver.support.wait import WebDriverWait

from .runtime_resources import ResourceManager
from .exceptions import LebenslaufError
from .template import Template
from .translations import JsonTranslations


def _make_env(translations: JsonTranslations) -> jinja2.Environment:
    env = jinja2.Environment(
        extensions=["jinja2.ext.i18n"],
        autoescape=jinja2.select_autoescape(("html", "xml")),
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.install_gettext_translations(translations)
    return env


def _resolve_translations(
    template: Template,
    language: str | None
) -> JsonTranslations:
    """Pick the right translation file for the requested language.

    - language is None   -> empty catalog (returns msgids as-is)
    - language is the original language -> empty catalog (nothing to translate)
    - language is not supported -> empty catalog (unable to translate)
    - otherwise -> load the file registered in manifest.yaml
    """
    if (
        language is None or
        language not in template.supported_languages
    ):
        # Case when the language is the original language is handled by
        # supported_languages.
        return JsonTranslations.load_translations(None)
    return JsonTranslations.load_translations(
        template.get_translation(language)
    )


def render_html(
    base_template_source: str,
    base_template_filename: str,
    template_source: str,
    template_filename: str,
    style: str,
    data: dict[str, Any],
    template: Template,
    language: str | None = None
) -> str:
    translations = _resolve_translations(template, language)

    user_env = _make_env(translations)
    user_template = user_env.from_string(template_source)
    user_template.filename = template_filename

    base_template = jinja2.Environment(
        autoescape=False,
        undefined=jinja2.StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    ).from_string(base_template_source)
    base_template.filename = base_template_filename

    user_html = user_template.render(**data, resume=data)
    return base_template.render(
        **data,
        resume=data,
        style=style,
        content=user_html
    )


def render_page(driver: Chrome, file: ResourceManager, timeout: float):
    driver.get(file.path.resolve().as_uri())
    _wait_for_layout(driver, timeout)


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
        raise LebenslaufError(f"browser print failed: {exc.msg}") from exc


def _wait_for_layout(driver: Any, timeout: float) -> None:

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
