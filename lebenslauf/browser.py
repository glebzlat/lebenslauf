from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Optional

from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import (
    InvalidSessionIdException,
    NoSuchWindowException,
    WebDriverException
)

from .exceptions import LebenslaufError


@dataclass(frozen=True)
class Browser:

    DETECTED_BROWSERS: ClassVar[dict[str, tuple[str, ...]]] = {
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

            raise LebenslaufError(
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
        raise LebenslaufError(
            f"no browser detected. Install one of: {names}; or pass --browser."
        )


class BrowserSession:
    def __init__(self, browser_arg: str | None, *, headless: bool):
        self.browser_arg = browser_arg
        self.headless = headless
        self.driver: Optional[Chrome] = None

    def __enter__(self) -> Chrome:
        browser = Browser.resolve(self.browser_arg)

        options = Options()
        options.binary_location = browser.binary
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")

        if self.headless:
            options.add_argument("--headless=new")

        self.driver = Chrome(options=options)

        return self.driver

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.driver is not None:
            try:
                self.driver.quit()
            except (
                InvalidSessionIdException,
                NoSuchWindowException,
                WebDriverException
            ):
                pass
            finally:
                self.driver = None
