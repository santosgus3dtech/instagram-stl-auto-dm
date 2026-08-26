from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from monitor.follow_audit import FollowAuditError, import_latest_from_inbox


ACCOUNTS_CENTER_URL = "https://accountscenter.instagram.com/info_and_permissions/dyi/"
LOGIN_MARKERS = (
    "login",
    "/accounts/login",
    "entrar",
    "log in",
)
SECURITY_MARKERS = (
    "checkpoint",
    "two-factor",
    "two_factor",
    "security",
    "verificacao",
    "verificação",
    "confirm",
    "confirme",
)


class AccountsCenterExportError(RuntimeError):
    pass


def env_path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser().resolve()


def now_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_status(
    status_path: Path,
    *,
    state: str,
    message: str,
    screenshot: Path | None = None,
    extra: dict | None = None,
) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "state": state,
        "message": message,
        "screenshot": str(screenshot) if screenshot else None,
        **(extra or {}),
    }
    status_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")


def screenshot(driver: WebDriver, screenshot_dir: Path, name: str) -> Path:
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    path = screenshot_dir / f"{now_slug()}-{name}.png"
    driver.save_screenshot(str(path))
    return path


def make_driver(
    *,
    profile_dir: Path,
    download_dir: Path,
    headless: bool,
    browser_binary: str | None,
    driver_path: str | None,
) -> WebDriver:
    profile_dir.mkdir(parents=True, exist_ok=True)
    download_dir.mkdir(parents=True, exist_ok=True)

    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--window-size=1365,950")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--lang=pt-BR")
    if headless:
        options.add_argument("--headless=new")
    if browser_binary:
        options.binary_location = browser_binary
    options.add_experimental_option(
        "prefs",
        {
            "download.default_directory": str(download_dir),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "intl.accept_languages": "pt-BR,pt,en-US,en",
            "safebrowsing.enabled": True,
        },
    )

    service = Service(executable_path=driver_path) if driver_path else Service()
    return webdriver.Chrome(service=service, options=options)


def normalized_page_text(driver: WebDriver) -> str:
    return " ".join((driver.page_source or "").casefold().split())


def detect_blocking_state(driver: WebDriver) -> str | None:
    url = (driver.current_url or "").casefold()
    text = normalized_page_text(driver)
    if any(marker in url or marker in text for marker in LOGIN_MARKERS):
        return "login_required"
    if any(marker in url or marker in text for marker in SECURITY_MARKERS):
        return "security_check_required"
    return None


def visible_clickables(driver: WebDriver) -> list[WebElement]:
    elements = driver.find_elements(
        By.XPATH,
        "//*[self::button or self::a or self::label or @role='button' or @role='checkbox' or @tabindex]",
    )
    return [element for element in elements if element.is_displayed()]


def text_of(element: WebElement) -> str:
    return " ".join((element.text or element.get_attribute("aria-label") or "").split())


def find_by_text(driver: WebDriver, labels: Iterable[str]) -> WebElement | None:
    normalized_labels = [label.casefold() for label in labels]
    candidates: list[tuple[int, WebElement]] = []
    for element in visible_clickables(driver):
        text = text_of(element)
        normalized_text = text.casefold()
        if not normalized_text:
            continue
        for label in normalized_labels:
            if label in normalized_text:
                candidates.append((len(normalized_text), element))
                break
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def click_any(
    driver: WebDriver,
    labels: Iterable[str],
    *,
    timeout_seconds: float = 15,
    required: bool = True,
) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        element = find_by_text(driver, labels)
        if element is not None:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.4)
            driver.execute_script("arguments[0].click();", element)
            time.sleep(1.2)
            return True
        time.sleep(0.5)
    if required:
        raise AccountsCenterExportError(f"Nao encontrei na tela: {', '.join(labels)}")
    return False


def wait_loaded(driver: WebDriver, timeout_seconds: float = 30) -> None:
    WebDriverWait(driver, timeout_seconds).until(
        lambda item: item.execute_script("return document.readyState") == "complete"
    )
    time.sleep(2)


def choose_profile(driver: WebDriver, profile_label: str | None) -> None:
    if not profile_label:
        return
    click_any(driver, [profile_label], timeout_seconds=8, required=False)


def request_follow_export(driver: WebDriver, *, profile_label: str | None) -> None:
    click_any(
        driver,
        ["Baixar ou transferir informacoes", "Baixar ou transferir informações", "Download or transfer information"],
        timeout_seconds=8,
        required=False,
    )
    choose_profile(driver, profile_label)
    click_any(driver, ["Avancar", "Avançar", "Next"], timeout_seconds=8, required=False)

    click_any(
        driver,
        ["Algumas das suas informacoes", "Algumas das suas informações", "Some of your information"],
        timeout_seconds=20,
    )
    click_any(
        driver,
        ["Seguidores e seguindo", "Followers and following"],
        timeout_seconds=20,
    )
    click_any(driver, ["Avancar", "Avançar", "Next"], timeout_seconds=20)

    click_any(
        driver,
        ["Baixar no dispositivo", "Download to device"],
        timeout_seconds=20,
        required=False,
    )
    click_any(driver, ["Avancar", "Avançar", "Next"], timeout_seconds=12, required=False)

    click_any(driver, ["Formato", "Format"], timeout_seconds=8, required=False)
    click_any(driver, ["JSON"], timeout_seconds=8, required=False)
    click_any(driver, ["Salvar", "Save"], timeout_seconds=8, required=False)

    click_any(driver, ["Intervalo de datas", "Date range"], timeout_seconds=8, required=False)
    click_any(driver, ["Todo o periodo", "Todo o período", "All time"], timeout_seconds=8, required=False)
    click_any(driver, ["Salvar", "Save"], timeout_seconds=8, required=False)

    click_any(
        driver,
        ["Criar arquivos", "Create files", "Criar arquivo", "Create file"],
        timeout_seconds=20,
    )


def run(args: argparse.Namespace) -> int:
    data_dir = args.audit_dir
    status_path = data_dir / "selenium_status.json"
    screenshot_dir = data_dir / "screenshots"
    write_status(status_path, state="running", message="Abrindo Central de Contas.")

    driver: WebDriver | None = None
    try:
        driver = make_driver(
            profile_dir=args.profile_dir,
            download_dir=data_dir / "inbox",
            headless=args.headless,
            browser_binary=args.browser_binary,
            driver_path=args.driver_path,
        )
        driver.get(args.url)
        wait_loaded(driver)

        blocking_state = detect_blocking_state(driver)
        if blocking_state:
            shot = screenshot(driver, screenshot_dir, blocking_state)
            write_status(
                status_path,
                state=blocking_state,
                message="Precisa de acao manual no navegador antes de automatizar.",
                screenshot=shot,
                extra={"url": driver.current_url},
            )
            return 2

        if args.mode == "check-session":
            shot = screenshot(driver, screenshot_dir, "session-ok")
            write_status(
                status_path,
                state="session_ok",
                message="Sessao carregada sem tela de login aparente.",
                screenshot=shot,
                extra={"url": driver.current_url},
            )
            return 0

        request_follow_export(driver, profile_label=args.profile_label)
        shot = screenshot(driver, screenshot_dir, "request-submitted")
        write_status(
            status_path,
            state="request_submitted",
            message="Pedido de exportacao enviado. A Meta pode demorar para liberar o ZIP.",
            screenshot=shot,
            extra={"url": driver.current_url},
        )
        return 0
    except (AccountsCenterExportError, TimeoutException, WebDriverException) as exc:
        shot = screenshot(driver, screenshot_dir, "failed") if driver else None
        write_status(
            status_path,
            state="failed",
            message=str(exc),
            screenshot=shot,
        )
        return 1
    finally:
        if driver is not None:
            driver.quit()
        try:
            imported = import_latest_from_inbox(data_dir)
            if imported.get("ready"):
                write_status(
                    status_path,
                    state="imported_latest_zip",
                    message="ZIP mais recente importado.",
                    extra={"generated_at": imported.get("generated_at")},
                )
        except FollowAuditError:
            pass


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Solicita exportacao oficial do Instagram via Central de Contas.")
    parser.add_argument("--mode", choices=["check-session", "request-export"], default="check-session")
    parser.add_argument("--url", default=os.getenv("ACCOUNTS_CENTER_EXPORT_URL", ACCOUNTS_CENTER_URL))
    parser.add_argument("--profile-label", default=os.getenv("ACCOUNTS_CENTER_PROFILE_LABEL"))
    parser.add_argument("--profile-dir", type=Path, default=env_path("SELENIUM_PROFILE_DIR", "data/selenium/meta_accounts_center_profile"))
    parser.add_argument("--audit-dir", type=Path, default=env_path("FOLLOW_AUDIT_DIR", "data/follow_audit"))
    parser.add_argument("--browser-binary", default=os.getenv("SELENIUM_BROWSER_BINARY"))
    parser.add_argument("--driver-path", default=os.getenv("SELENIUM_DRIVER_PATH"))
    parser.add_argument("--headless", action="store_true", default=os.getenv("SELENIUM_HEADLESS", "false").casefold() in {"1", "true", "yes", "on"})
    return parser.parse_args(argv)


if __name__ == "__main__":
    raise SystemExit(run(parse_args(sys.argv[1:])))
