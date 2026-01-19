"""
GitHub Account Generator using temporary email services.

Flow (unchanged):
1) Generate credentials
2) Get temp email
3) Launch browser
4) Open signup + accept cookies
5) Fill email/password/username
6) Submit
7) Wait for captcha to resolve (fail if visual puzzle)
8) Wait for verification form
9) Pull verification code from email
10) Fill code + submit
11) Wait for account creation
12) Setup 2FA (optional)
"""

import json
import os
import random
import re
import string
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, Optional, Callable

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from config import (
    ARGS,
    CHROME_PATH,
    FIRST_NAMES,
    HEADLESS,
    LAST_NAMES,
    LOCALE,
    OUTPUT_DIR,
    USER_AGENT,
    VIEWPORT,
    TOR_CONTROL_PORT,
    TOR_PORT,
)
from TempMailServices.EmailOnDeck import EmailOnDeck
from utils import format_error, get_2fa_code, logger, renew_tor

load_dotenv()

# ==============================================================================
# GitHub Signup Constants
# ==============================================================================
GITHUB_SIGNUP_URL = "https://github.com/signup"
GITHUB_EMAIL_SELECTOR = "#email"
GITHUB_PASSWORD_SELECTOR = "#password"
GITHUB_USERNAME_SELECTOR = "#login"
GITHUB_SUBMIT_BUTTON_SELECTOR = "#signup-form > form > div:nth-child(7) > button"
GITHUB_COOKIES_BUTTON_SELECTOR = "#wcpConsentBannerCtrl > div > button:nth-child(1)"
GITHUB_VERIFICATION_FORM_SELECTOR = (
    "body > div > div > div > main > div > div > div > react-partial > "
    "div > div > div:nth-child(1) > form"
)
GITHUB_VERIFICATION_SUBMIT_SELECTOR = (
    "body > div > div > div > main > div > div > div > react-partial > "
    "div > div > div:nth-child(1) > form > div:nth-child(4) > button"
)
GITHUB_CAPTCHA_IFRAME_SELECTOR = (
    "#captcha-container-nux > div > div > div:nth-child(3) > iframe"
)

USERNAME_PREFIX = "dev1"
MAX_CAPTCHA_WAIT_ITERATIONS = 25


@dataclass
class AccountData:
    email_address: Optional[str] = None
    email_token: Optional[str] = None
    password: Optional[str] = None
    username: Optional[str] = None
    created_at: Optional[str] = None
    status: str = "pending"


class GithubTMailorGenerator:
    def __init__(self, use_tor: bool = False):
        self.use_tor = use_tor

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.email_service = None

        self.account_data = AccountData()
        self.ip: Optional[str] = None
        self.verification_code: Optional[str] = None
        self.secret: Optional[str] = None
        self.recovery_codes: list[str] = []

        self.screenshot_counter = 1

        logger(f"TOR Port: {TOR_PORT}", level=1)
        logger(f"TOR Control Port: {TOR_CONTROL_PORT}", level=1)

        self._init_output_dirs()

        if self.use_tor:
            logger("Using TOR network for emails...", level=1)
            _, self.ip = renew_tor(level=1)

    # --------------------------------------------------------------------------
    # Init / dirs
    # --------------------------------------------------------------------------
    def _init_output_dirs(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.screenshots_dir = os.path.join(OUTPUT_DIR, f"github_screenshots_{timestamp}")
        self.html_reports_dir = os.path.join(OUTPUT_DIR, f"github_html_reports_{timestamp}")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.html_reports_dir, exist_ok=True)

    # --------------------------------------------------------------------------
    # Timing / "human" helpers
    # --------------------------------------------------------------------------
    def human_delay(self, min_ms: int = 500, max_ms: int = 1500) -> None:
        time.sleep(random.uniform(min_ms, max_ms) / 1000)

    def natural_delay(self, min_s: float = 1, max_s: float = 3) -> None:
        time.sleep(random.uniform(min_s, max_s))

    def _wait_for_network_idle(self, timeout_ms: int = 5000) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # Playwright action helpers (small + reusable)
    # --------------------------------------------------------------------------
    def _safe(self, action: Callable[[], Any], label: str, level: int = 0, screenshot_on_fail: bool = True) -> Any:
        try:
            return action()
        except Exception as e:
            logger(f"✗ {label}: {format_error(e)}", level=level)
            if screenshot_on_fail:
                self._save_screenshot(level=level + 1)
            raise

    def human_type(self, selector: str, text: str, min_delay_ms: int = 50, max_delay_ms: int = 200) -> None:
        try:
            delay = random.randint(min_delay_ms, max_delay_ms)
            self.page.type(selector, text, delay=delay, timeout=60000)
        except Exception as e:
            logger(f"⚠ Human type fallback for {selector}: {e}")
            self.page.fill(selector, text)

    def human_click(self, selector: str) -> bool:
        try:
            self.page.hover(selector)
            self.human_delay(300, 700)
            self.page.click(selector, timeout=60000)
            return True
        except Exception as e:
            logger(f"⚠ Human click failed, retrying force click: {e}")
            try:
                self.page.click(selector, force=True)
                return True
            except Exception as e2:
                logger(f"✗ Click completely failed: {e2}")
                return False

    def _wait_visible(self, selector: str, timeout_ms: int = 30000) -> bool:
        try:
            self.page.wait_for_selector(selector, state="visible", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def _wait_attached(self, selector: str, timeout_ms: int = 30000) -> bool:
        try:
            self.page.wait_for_selector(selector, state="attached", timeout=timeout_ms)
            return True
        except Exception:
            return False

    def _retry(self, func: Callable[[], bool], retries: int, delay_range: tuple[float, float], level: int = 0) -> bool:
        for _ in range(retries):
            if func():
                return True
            self.natural_delay(*delay_range)
        return False

    def _wait_and_fill(self, selector: str, value: str, field_name: str, level: int = 0) -> bool:
        logger(f"[######] Filling {field_name}...", level=level)
        try:
            if not self._wait_visible(selector, timeout_ms=30000):
                raise TimeoutError(f"{field_name} not visible: {selector}")
            self.page.click(selector)
            self.human_type(selector, value)
            self.page.keyboard.press("Tab")
            logger(f"✓ {field_name} filled", level=level + 1)
            self._wait_for_network_idle()
            return True
        except Exception as e:
            logger(f"✗ Failed to fill {field_name}: {e}", level=level + 1)
            self._save_screenshot(level=level + 1)
            return False

    # --------------------------------------------------------------------------
    # Data generation
    # --------------------------------------------------------------------------
    def _generate_account_info(self, level: int = 0) -> Optional[Dict[str, Any]]:
        logger("[######] Generating account info...", level=level)
        try:
            password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "".join(random.choice(password_chars) for _ in range(15))

            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            username = f"{first_name}{last_name}-{USERNAME_PREFIX}".lower()

            self.account_data = AccountData(
                password=password,
                username=username,
                created_at=datetime.now().isoformat(),
                status="pending",
            )

            logger(f"✓ Generated account info: {username} | {password}", level=level + 1)
            return asdict(self.account_data)
        except Exception as e:
            logger(f"✗ Failed to generate account info: {format_error(e)}", level=level + 1)
            return None

    def _get_email_address(self, level: int = 0) -> Optional[str]:
        logger("[######] Getting email address...", level=level)
        try:
            self.email_service = EmailOnDeck()
            result = self.email_service.generate_email()

            if not result or not result.get("email"):
                logger("✗ Failed to generate email address", level=level + 1)
                return None

            self.account_data.email_address = result["email"]
            self.account_data.email_token = result.get("token", "N/A")
            logger(f"✓ Email obtained: {self.account_data.email_address}", level=level + 1)
            return self.account_data.email_address
        except Exception as e:
            logger(f"✗ Failed to get email address: {format_error(e)}", level=level + 1)
            return None

    # --------------------------------------------------------------------------
    # Browser
    # --------------------------------------------------------------------------
    def _launch_browser(self, level: int = 0) -> bool:
        logger("[######] Launching browser...", level=level)
        try:
            launch_kwargs = {"headless": HEADLESS, "args": ARGS}

            if self.use_tor:
                tor_proxy = f"socks5://127.0.0.1:{TOR_PORT}"
                launch_kwargs["proxy"] = {"server": tor_proxy}
                logger(f"Using Tor proxy: {tor_proxy}", level=level + 1)

            if os.path.exists(CHROME_PATH):
                launch_kwargs["executable_path"] = CHROME_PATH
                logger(f"Using Browser: {CHROME_PATH}", level=level + 1)
            else:
                logger(f"⚠ Browser not found at {CHROME_PATH}, using default Chromium", level=level + 1)

            self.browser = self.playwright.chromium.launch(**launch_kwargs)
            self.context = self.browser.new_context(viewport=VIEWPORT, locale=LOCALE, user_agent=USER_AGENT)
            self.context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            self.page = self.context.new_page()

            logger("✓ Browser launched successfully", level=level + 1)
            return True
        except Exception as e:
            logger(f"✗ Error launching browser: {format_error(e)}", level=level + 1)
            return False

    # --------------------------------------------------------------------------
    # Signup steps (broken down)
    # --------------------------------------------------------------------------
    def _open_signup(self, level: int = 0) -> None:
        logger("[######] Opening GitHub signup...", level=level)
        self.page.goto(GITHUB_SIGNUP_URL, timeout=60000)
        self._wait_for_network_idle()

    def _accept_cookies_if_present(self, level: int = 0) -> None:
        try:
            self.page.wait_for_selector(GITHUB_COOKIES_BUTTON_SELECTOR, timeout=30000)
            self.page.click(GITHUB_COOKIES_BUTTON_SELECTOR)
            logger("✓ Accepted cookies", level=level + 1)
        except Exception:
            logger("✗ Cookie banner not found or already accepted", level=level + 1)

    def _fill_signup_form(self, level: int = 0) -> bool:
        self.natural_delay()

        if not self._wait_and_fill(GITHUB_EMAIL_SELECTOR, self.account_data.email_address, "Email", level=level):
            return False

        self.natural_delay()
        if not self.page.is_visible(GITHUB_PASSWORD_SELECTOR):
            logger("Password field not yet visible, pressing Enter...", level=level)
            self.page.press(GITHUB_EMAIL_SELECTOR, "Enter")

        if not self._wait_and_fill(GITHUB_PASSWORD_SELECTOR, self.account_data.password, "Password", level=level):
            return False

        self.natural_delay()
        if not self.page.is_visible(GITHUB_USERNAME_SELECTOR):
            logger("Username field not yet visible, pressing Enter...", level=level)
            self.page.press(GITHUB_PASSWORD_SELECTOR, "Enter")

        if not self._wait_and_fill(GITHUB_USERNAME_SELECTOR, self.account_data.username, "Username", level=level):
            return False

        self.natural_delay(5, 10)
        return True

    def _submit_signup(self, level: int = 0) -> None:
        logger("[######] Clicking Submit...", level=level)

        if not self.page.is_visible(GITHUB_SUBMIT_BUTTON_SELECTOR):
            self.page.press(GITHUB_USERNAME_SELECTOR, "Enter")

        self.page.wait_for_selector(GITHUB_SUBMIT_BUTTON_SELECTOR, state="visible", timeout=10000)
        self.natural_delay()
        self.human_click(GITHUB_SUBMIT_BUTTON_SELECTOR)
        logger("✓ Submit clicked", level=level + 1)
        self.natural_delay(2, 5)

    # --------------------------------------------------------------------------
    # Captcha / verification
    # --------------------------------------------------------------------------
    def _check_captcha_iframe_exists(self, level: int = 0) -> bool:
        exists = self._wait_attached(GITHUB_CAPTCHA_IFRAME_SELECTOR, timeout_ms=30000)
        logger(("✓ Captcha iframe exists" if exists else "✗ Captcha iframe not found"), level=level)
        return exists

    def _check_puzzle_displayed(self, level: int = 0) -> bool:
        try:
            logger("Checking for puzzle in iframe...", level=level)
            self.page.wait_for_selector(GITHUB_CAPTCHA_IFRAME_SELECTOR, state="attached", timeout=30000)
            iframe1 = self.page.frame_locator(GITHUB_CAPTCHA_IFRAME_SELECTOR)

            iframe2_selector = "#funcaptcha > div > iframe"
            iframe1.locator(iframe2_selector).wait_for(state="attached", timeout=30000)
            iframe2 = iframe1.frame_locator(iframe2_selector)

            iframe3_selector = "#game-core-frame"
            iframe2.locator(iframe3_selector).wait_for(state="attached", timeout=30000)
            iframe3 = iframe2.frame_locator(iframe3_selector)

            puzzle_btn_selector = "#root > div > div > button[aria-label='Visual puzzle']"
            if iframe3.locator(puzzle_btn_selector).is_visible(timeout=5000):
                logger("✓ Puzzle captcha detected", level=level)
                return True

            logger("✗ Puzzle not found", level=level)
            return False
        except Exception:
            logger("✗ Puzzle check failed", level=level)
            return False

    def _wait_for_captcha_to_clear(self, level: int = 0) -> bool:
        captcha_exists = self._check_captcha_iframe_exists(level=level)

        if not captcha_exists:
            captcha_exists = self._retry(
                lambda: self._check_captcha_iframe_exists(level=level),
                retries=3,
                delay_range=(2, 5),
                level=level,
            )

        captcha_check_count = 0
        while captcha_exists:
            captcha_check_count += 1

            if captcha_check_count > MAX_CAPTCHA_WAIT_ITERATIONS:
                logger("⚠ Max captcha wait iterations reached", level=level + 1)
                break

            logger("Captcha iframe still present, waiting...", level=level + 1)

            if captcha_check_count > 5:
                self.natural_delay()
                if self._check_puzzle_displayed(level=level):
                    logger("✗ Visual puzzle captcha detected - cannot proceed", level=level + 1)
                    return False

            self.natural_delay()
            captcha_exists = self._check_captcha_iframe_exists(level=level)

        return True

    def _check_verification_code_form_exists(self, level: int = 0) -> bool:
        exists = self._wait_attached(GITHUB_VERIFICATION_FORM_SELECTOR, timeout_ms=30000)
        logger(("✓ Verification code form exists" if exists else "✗ Verification code form not found"), level=level)
        return exists

    def _wait_for_verification_form(self, level: int = 0) -> bool:
        if self._check_verification_code_form_exists(level=level):
            return True
        return self._retry(
            lambda: self._check_verification_code_form_exists(level=level),
            retries=3,
            delay_range=(2, 5),
            level=level,
        )

    def _extract_verification_code(self, email_content: str) -> Optional[str]:
        match = re.search(r">\s*(\d{8})\s*</span>", email_content)
        return match.group(1) if match else None

    def _fetch_verification_code_from_email(self, level: int = 0) -> Optional[str]:
        code = None
        new_email = self.email_service.wait_for_email(120)
        if not new_email:
            return None

        content = self.email_service.get_email(new_email)
        if not content:
            return None

        code = self._extract_verification_code(content[self.email_service.body_key])
        if code:
            self.verification_code = code
            logger(f"Verification code: {code}", level=level)
        return code

    def _fill_verification_code(self, code: str, level: int = 0) -> None:
        for i, digit in enumerate(code):
            self.page.fill(f"#launch-code-{i}", digit)
            logger(f"Filled verification code field {i + 1}: {digit}", level=level)
            self.natural_delay()

    def _submit_verification_code(self, level: int = 0) -> None:
        try:
            self.page.wait_for_selector(GITHUB_VERIFICATION_SUBMIT_SELECTOR, state="visible", timeout=10000)
            self.page.click(GITHUB_VERIFICATION_SUBMIT_SELECTOR)
            logger("✓ Verification submitted", level=level + 1)
        except Exception:
            current_url = self.page.evaluate("window.location.href")
            logger(f"Current URL: {current_url}", level=level + 1)
            if current_url != GITHUB_SIGNUP_URL:
                logger("✓ Code auto-submitted", level=level + 1)
            else:
                raise Exception("✗ Code submission failed")

    # --------------------------------------------------------------------------
    # 2FA (logic preserved, only slightly segmented)
    # --------------------------------------------------------------------------
    def _login(self, level: int = 0) -> bool:
        logger("[######] Logging in...", level=level)
        try:
            email_selector = "input#login_field"
            login_value = self.account_data.username or self.account_data.email_address

            if not self._wait_and_fill(email_selector, login_value, "Login Field", level=level + 1):
                return False

            password_selector = "input#password"
            if not self._wait_and_fill(password_selector, self.account_data.password, "Password", level=level + 1):
                return False

            self.natural_delay()
            login_button_selector = "input[type='submit']"
            logger("Clicking Login...", level=level + 1)
            self.human_click(login_button_selector)
            self.natural_delay()
            return True
        except Exception as e:
            logger(f"✗ Login failed: {format_error(e)}", level=level + 1)
            return False

    def _wait_until_on_login_page(self, level: int = 0) -> bool:
        for attempt in range(10):
            if "github.com/login" in self.page.url:
                logger("✓ On login page", level=level)
                return True
            logger("⚠ Not on login page, waiting...", level=level)
            self.natural_delay(2, 4)
        return False

    def _wait_for_dashboard(self, level: int = 0) -> bool:
        logger("Checking redirection to dashboard...", level=level)
        for attempt in range(10):
            try:
                self.page.wait_for_url("https://github.com/dashboard", timeout=30000)
                logger("✓ Redirected to dashboard", level=level)
                return True
            except Exception:
                logger("⚠ Not on dashboard yet, waiting...", level=level)
                self.natural_delay(2, 4)
        return False

    def _simulate_human_scrolling(self) -> None:
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        self.natural_delay()
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
        self.natural_delay()
        self.page.evaluate("window.scrollTo(0, 0)")
        self.natural_delay()

    def _setup_2fa(self, level: int = 0) -> bool:
        logger("[######] Setting up 2FA...", level=level)
        try:
            if not self._wait_until_on_login_page(level=level + 1):
                return False

            if not self._login(level=level + 1):
                return False

            self.natural_delay(2, 4)

            if not self._wait_for_dashboard(level=level + 1):
                return False

            self.natural_delay()
            logger("Simulating human behavior...", level=level + 1)
            self._simulate_human_scrolling()

            logger("Opening user menu...", level=level + 1)
            try:
                user_menu_selector = "button[aria-label='Open user navigation menu'], button[aria-haspopup='menu'], button[aria-haspopup='true'], "
                self.human_click(user_menu_selector)
            except Exception:
                img_menu_selector = "div[data-testid='top-nav-right'] img, img[data-component='Avatar'], img[data-testid='github-avatar']"
                self.human_click(img_menu_selector)
            self.natural_delay()

            logger("Clicking Settings...", level=level + 1)
            try:
                settings_selector = "a[href='/settings/profile']"
                self.human_click(settings_selector)
            except Exception:
                self.page.goto("https://github.com/settings/profile")
            self.natural_delay()

            self.page.evaluate("window.scrollBy(0, 200)")
            self.natural_delay(0.5, 1)
            self.page.evaluate("window.scrollTo(0, 0)")
            self.natural_delay()

            logger("Clicking Password and authentication...", level=level + 1)
            password_and_auth_selector = "a[href='/settings/security']"
            self.human_click(password_and_auth_selector)
            self.natural_delay()

            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.natural_delay()

            logger("Clicking Enable 2FA...", level=level + 1)
            self.human_click("a[href='/settings/two_factor_authentication/setup/intro']")
            self.natural_delay()

            secret_selector = (
                "#two-factor-setup-verification-mashed-secret > scrollable-region > div > div, "
                "[data-target='two-factor-setup-verification.mashedSecret']"
            )
            self.page.wait_for_selector(secret_selector, state="visible")
            secret = self.page.text_content(secret_selector)

            if not secret:
                logger("✗ Failed to get secret", level=level + 2)
                return False

            self.secret = secret.strip()
            logger(f"✓ Secret obtained: {self.secret}", level=level + 2)

            self.natural_delay()

            code = get_2fa_code(self.secret)
            logger(f"Generated 2FA Code: {code}", level=level + 2)

            input_selector = "#two-factor-setup-verification-step > div:nth-child(1) > form > div > div > input"
            self.human_type(input_selector, code)

            logger("Pressing Tab...", level=level + 1)
            self.page.keyboard.press("Tab")
            self.natural_delay()

            continue_btn = (
                "#wizard-step-factor > div > div > div > div > div > "
                "button[data-action='click:single-page-wizard-step#onNext']"
            )
            logger("Clicking Continue...", level=level + 1)
            self.human_click(continue_btn)
            self.natural_delay()

            recovery_codes_ul = "ul[data-target='two-factor-setup-recovery-codes.codes']"
            try:
                self.page.wait_for_selector(recovery_codes_ul, timeout=10000)
                logger("✓ Recovery codes page reached", level=level + 1)
            except Exception:
                logger("⚠ Recovery codes not immediately visible", level=level + 1)

            self.natural_delay()
            codes_elements = self.page.query_selector_all(f"{recovery_codes_ul} li")
            self.recovery_codes = [el.inner_text() for el in codes_elements]
            logger(f"✓ Saved {len(self.recovery_codes)} recovery codes", level=level + 2)

            logger("Clicking Download codes...", level=level + 1)
            self.human_click("button[data-action='click:two-factor-setup-recovery-codes#onDownloadClick']")
            self.natural_delay()

            logger("Clicking 'I have saved my recovery codes'...", level=level + 1)
            self.human_click(
                "button[data-target='single-page-wizard-step.nextButton']:has-text('I have saved my recovery codes')"
            )
            self.natural_delay()

            logger("Clicking Done...", level=level + 1)
            self.human_click("button[data-target='single-page-wizard-step.nextButton']:has-text('Done')")
            self.natural_delay()

            return True
        except Exception as e:
            logger(f"✗ 2FA Setup error: {format_error(e)}", level=level + 1)
            self._save_screenshot(level=level + 1)
            return False

    # --------------------------------------------------------------------------
    # Debug / persistence
    # --------------------------------------------------------------------------
    def _save_screenshot(self, level: int = 0) -> None:
        logger("[######] Saving screenshot...", level=level)
        if not self.page:
            logger("✗ No page to save screenshot", level=level + 1)
            return

        try:
            screenshot_path = f"{self.screenshots_dir}/{self.screenshot_counter}.png"
            self.page.screenshot(path=screenshot_path)
            logger(f"✓ Screenshot saved: {screenshot_path}", level=level + 1)
            self.screenshot_counter += 1
        except Exception as e:
            logger(f"✗ Screenshot failed: {format_error(e)}", level=level + 1)

    def _save_account_data(self, level: int = 0) -> None:
        try:
            account_dump = {
                "email": self.account_data.email_address,          # fixed: was self.account_data.get('email')
                "email_token": self.account_data.email_token,
                "username": self.account_data.username,
                "password": self.account_data.password,
                "ip": self.ip,
                "verification_code": self.verification_code,
                "secret": self.secret,
                "recovery_codes": self.recovery_codes,
            }

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filepath = f"{OUTPUT_DIR}/account_{timestamp}.json"

            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(account_dump, indent=4))
                logger(f"✓ Account data saved: {filepath}", level=level + 1)
        except Exception as e:
            logger(f"✗ Failed to save account data: {format_error(e)}", level=level + 1)

    # --------------------------------------------------------------------------
    # Main flow
    # --------------------------------------------------------------------------
    def run_flow(self, level: int = 0) -> bool:
        logger("GitHub TMailor Account Generator", level=level)

        with sync_playwright() as p:
            self.playwright = p

            try:
                self._generate_account_info(level=level + 1)

                if not self._get_email_address(level=level + 1):
                    return False

                if not self._launch_browser(level=level + 1):
                    return False

                self._open_signup(level=level + 1)
                self._accept_cookies_if_present(level=level + 1)

                if not self._fill_signup_form(level=level + 1):
                    return False

                self._submit_signup(level=level + 1)

                if not self._wait_for_captcha_to_clear(level=level + 1):
                    return False

                if not self._wait_for_verification_form(level=level + 1):
                    return False

                code = self._fetch_verification_code_from_email(level=level + 2)
                if not code:
                    logger("✗ Verification code not found in email", level=level + 2)
                    return False

                self._fill_verification_code(code, level=level + 2)
                self._submit_verification_code(level=level + 1)

                time.sleep(20)
                logger("✓ Waited for account creation", level=level + 2)

                if not self._setup_2fa(level=level + 1):
                    logger("✗ 2FA Setup failed", level=level + 1)
                else:
                    logger("✓ 2FA Setup completed", level=level + 1)

                logger("✓ Flow execution finished", level=level + 1)

                logger("Waiting for user input to close browser...", level=level + 1)
                input("Press Enter to close the browser...")

                return True

            except Exception as e:
                logger(f"✗ An error occurred: {format_error(e)}", level=level + 1)
                return False

            finally:
                self._save_screenshot(level=level + 1)
                self._save_account_data(level=level + 1)
                if self.browser:
                    self.browser.close()

    def run_flow_with_retries(self, max_retries: int = 3, level: int = 0) -> bool:
        logger("Running flow with retries...", level=level)

        for attempt in range(max_retries):
            try:
                if self.run_flow(level=level + 1):
                    return True

                if attempt < max_retries - 1:
                    logger(f"✗ Flow failed, retrying ({attempt + 1}/{max_retries})", level=level + 1)
                    renew_tor(level=level + 1)
                    time.sleep(random.uniform(5, 10))

            except Exception as e:
                if attempt < max_retries - 1:
                    logger(
                        f"✗ Flow error, retrying ({attempt + 1}/{max_retries}): {format_error(e)}",
                        level=level + 1,
                    )
                    renew_tor(level=level + 1)
                    time.sleep(random.uniform(5, 10))
                else:
                    logger(f"✗ Flow failed after {max_retries} attempts: {format_error(e)}", level=level + 1)

        return False


if __name__ == "__main__":
    generator = GithubTMailorGenerator(use_tor=True)
    generator.run_flow_with_retries(max_retries=1000)