"""
GitHub Account Generator using temporary email services with PlaywrightHelper.
"""

import json
import os
import random
import re
import string
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

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
from playwright_helper import PlaywrightHelper
from TempMailServices.EmailOnDeck import EmailOnDeck
from utils import format_error, get_2fa_code, logger, renew_tor

load_dotenv()

# ==============================================================================
# GitHub Signup Constants
# ==============================================================================
GITHUB_SIGNUP_URL = "https://github.com/signup"
GITHUB_LOGIN_URL = "https://github.com/login"
GITHUB_DASHBOARD_URL = "https://github.com/dashboard"

# Selectors
SELECTORS = {
    # Signup form
    "email": "#email",
    "password": "#password",
    "username": "#login",
    "username_error": "#login + div + div.error, #login + * + div.error, #login + * + .error, .error",
    "submit_button": "#signup-form > form > div:nth-child(7) > button",
    "cookies_button": "#wcpConsentBannerCtrl > div > button:nth-child(1)",
    
    # Verification
    "verification_form": (
        "body > div > div > div > main > div > div > div > react-partial > "
        "div > div > div:nth-child(1) > form"
    ),
    "verification_submit": (
        "body > div > div > div > main > div > div > div > react-partial > "
        "div > div > div:nth-child(1) > form > div:nth-child(4) > button"
    ),
    "verification_code_field": "#launch-code-{index}",
    
    # Captcha
    "captcha_iframe": "#captcha-container-nux > div > div > div:nth-child(3) > iframe",
    "captcha_iframe_2": "#funcaptcha > div > iframe",
    "captcha_iframe_3": "#game-core-frame",
    "puzzle_button": "#root > div > div > button[aria-label='Visual puzzle']",
    
    # Login
    "login_field": "input#login_field",
    "login_password": "input#password",
    "login_submit": "input[type='submit']",
    
    # Settings / 2FA
    "user_menu": "button[aria-label='Open user navigation menu'], button[aria-haspopup='menu']",
    "user_avatar": "div[data-testid='top-nav-right'] img, img[data-component='Avatar']",
    "settings_link": "a[href='/settings/profile']",
    "security_link": "a[href='/settings/security']",
    "enable_2fa_link": "a[href='/settings/two_factor_authentication/setup/intro']",
    "2fa_secret": (
        "#two-factor-setup-verification-mashed-secret > scrollable-region > div > div, "
        "[data-target='two-factor-setup-verification.mashedSecret']"
    ),
    "2fa_code_input": "#two-factor-setup-verification-step > div:nth-child(1) > form > div > div > input",
    "2fa_continue_button": (
        "#wizard-step-factor > div > div > div > div > div > "
        "button[data-action='click:single-page-wizard-step#onNext']"
    ),
    "recovery_codes_list": "ul[data-target='two-factor-setup-recovery-codes.codes']",
    "download_codes_button": "button[data-action='click:two-factor-setup-recovery-codes#onDownloadClick']",
    "saved_codes_button": "button[data-target='single-page-wizard-step.nextButton']:has-text('I have saved my recovery codes')",
    "done_button": "button[data-target='single-page-wizard-step.nextButton']:has-text('Done')",
}

USERNAME_PREFIX = "dev1"
MAX_CAPTCHA_WAIT_ITERATIONS = 25
MAX_RETRIES_FOR_USERNAME_UPDATE = 5


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
        self.helper: Optional[PlaywrightHelper] = None
        self.email_service = None

        self.account_data = AccountData()
        self.ip: Optional[str] = None
        self.verification_code: Optional[str] = None
        self.secret: Optional[str] = None
        self.recovery_codes: List[str] = []

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
    # Data generation
    # --------------------------------------------------------------------------
    def _generate_username(self, level: int = 0) -> str:
        logger("[######] Generating username...", level=level)
        try:
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)
            return f"{first_name}{last_name}-{USERNAME_PREFIX}".lower()
        except Exception as e:
            logger(f"✗ Failed to generate username: {format_error(e)}", level=level + 1)
            return "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    
    def _generate_account_info(self, level: int = 0) -> Optional[Dict[str, Any]]:
        logger("[######] Generating account info...", level=level)
        try:
            password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
            password = "".join(random.choice(password_chars) for _ in range(15))

            username = self._generate_username(level=level + 1)

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
            self.context = self.browser.new_context(
                viewport=VIEWPORT,
                locale=LOCALE,
                user_agent=USER_AGENT
            )
            self.context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
            self.page = self.context.new_page()

            # Initialize PlaywrightHelper
            self.helper = PlaywrightHelper(
                page=self.page,
                default_retries=3,
                default_timeout=30000,
                humanize=True,
                humanize_min_delay=0.1,
                humanize_max_delay=0.4
            )

            logger("✓ Browser launched successfully", level=level + 1)
            return True
        except Exception as e:
            logger(f"✗ Error launching browser: {format_error(e)}", level=level + 1)
            return False

    # --------------------------------------------------------------------------
    # Signup steps
    # --------------------------------------------------------------------------
    def _open_signup(self, level: int = 0) -> bool:
        logger("[######] Opening GitHub signup...", level=level)
        result = self.helper.goto(GITHUB_SIGNUP_URL, timeout=60000)
        if result:
            self.helper.wait_for_network_idle(timeout=5000)
            logger("✓ Opened GitHub signup page", level=level + 1)
        else:
            logger("✗ Failed to open GitHub signup page", level=level + 1)
        return result

    def _accept_cookies_if_present(self, level: int = 0) -> bool:
        logger("[######] Checking for cookie banner...", level=level)
        if self.helper.check_element_exists(SELECTORS["cookies_button"], retries=1, timeout=5000):
            result = self.helper.click(SELECTORS["cookies_button"])
            if result:
                logger("✓ Accepted cookies", level=level + 1)
            return result
        logger("✗ Cookie banner not found or already accepted", level=level + 1)
        return True

    def _fill_signup_form(self, level: int = 0) -> bool:
        logger("[######] Filling signup form...", level=level)

        self.helper.wait_natural_delay(1, 2)

        # Fill email
        logger("Filling email...", level=level + 1)
        if not self.helper.fill(
            SELECTORS["email"],
            self.account_data.email_address,
            humanize_typing=True,
            press_tab_after=True
        ):
            logger("✗ Failed to fill email", level=level + 1)
            return False
        logger("✓ Email filled", level=level + 1)

        self.helper.wait_natural_delay(1, 2)

        # Check if password field is visible, if not press Enter
        if not self.helper.check_element_visible(SELECTORS["password"], timeout=3000):
            logger("Password field not yet visible, pressing Enter...", level=level + 1)
            self.helper.press_key("Enter", SELECTORS["email"])
            self.helper.wait_natural_delay(1, 2)

        # Fill password
        logger("Filling password...", level=level + 1)
        if not self.helper.fill(
            SELECTORS["password"],
            self.account_data.password,
            humanize_typing=True,
            press_tab_after=True
        ):
            logger("✗ Failed to fill password", level=level + 1)
            return False
        logger("✓ Password filled", level=level + 1)

        self.helper.wait_natural_delay(1, 2)

        # Check if username field is visible, if not press Enter
        if not self.helper.check_element_visible(SELECTORS["username"], timeout=3000):
            logger("Username field not yet visible, pressing Enter...", level=level + 1)
            self.helper.press_key("Enter", SELECTORS["password"])
            self.helper.wait_natural_delay(1, 2)

        # Fill username
        logger("Filling username...", level=level + 1)
        if not self.helper.fill(
            SELECTORS["username"],
            self.account_data.username,
            humanize_typing=True,
            press_tab_after=True
        ):
            logger("✗ Failed to fill username", level=level + 1)
            return False
        logger("✓ Username filled", level=level + 1)

        self.helper.wait_natural_delay(5, 10)
        return True
    
    def _check_username_error(self, level: int = 0) -> bool:
        if self.helper.check_element_exists(SELECTORS["username_error"], timeout=3000):
            logger("✗ Username already exists", level=level + 1)
            return True
        return False
    
    def _change_username(self, level: int = 0) -> bool:
        logger("[######] Changing username...", level=level)
        
        # Generate new username
        self.account_data.username = self._generate_username(level=level + 1)

        # Clear username field
        logger("Clearing username...", level=level + 1)
        if not self.helper.clear_field(SELECTORS["username"]):
            logger("✗ Failed to clear username", level=level + 1)
            return False
        logger("✓ Username cleared", level=level + 1)
        self.helper.wait_natural_delay(1, 2)

        # Fill username
        logger("Filling username...", level=level + 1)
        if not self.helper.fill(
            SELECTORS["username"],
            self.account_data.username,
            humanize_typing=True,
            press_tab_after=True
        ):
            logger("✗ Failed to fill username", level=level + 1)
            return False
        logger("✓ Username filled", level=level + 1)
        self.helper.wait_natural_delay(5, 10)
        return True

    def _submit_signup(self, level: int = 0) -> bool:
        logger("[######] Clicking Submit...", level=level)

        # Check if submit button is visible, if not press Enter
        if not self.helper.check_element_visible(SELECTORS["submit_button"], timeout=3000):
            self.helper.press_key("Enter", SELECTORS["username"])
            self.helper.wait_natural_delay(1, 2)

        # Wait for submit button and click
        if not self.helper.check_element_exists(SELECTORS["submit_button"], timeout=10000):
            logger("✗ Submit button not found", level=level + 1)
            return False

        self.helper.wait_natural_delay(1, 2)

        if self.helper.click(SELECTORS["submit_button"]):
            logger("✓ Submit clicked", level=level + 1)
            self.helper.wait_natural_delay(2, 5)
            return True

        logger("✗ Failed to click submit", level=level + 1)
        return False

    # --------------------------------------------------------------------------
    # Captcha / verification
    # --------------------------------------------------------------------------
    def _check_captcha_iframe_exists(self, level: int = 0) -> bool:
        exists = self.helper.check_element_exists(
            SELECTORS["captcha_iframe"],
            retries=1,
            timeout=5000,
            state="attached"
        )
        logger(("✓ Captcha iframe exists" if exists else "✗ Captcha iframe not found"), level=level)
        return exists

    def _check_puzzle_displayed(self, level: int = 0) -> bool:
        """Check if visual puzzle captcha is displayed (nested iframes)."""
        try:
            logger("Checking for puzzle in iframe...", level=level)

            # Check first iframe exists
            if not self.helper.check_element_exists(SELECTORS["captcha_iframe"], timeout=5000):
                return False

            # Check second iframe inside first
            if not self.helper.check_element_exists(
                SELECTORS["captcha_iframe_2"],
                iframe_selector=SELECTORS["captcha_iframe"],
                timeout=5000
            ):
                return False

            # Check third iframe inside second (nested frame locators)
            try:
                iframe1 = self.page.frame_locator(SELECTORS["captcha_iframe"])
                iframe2 = iframe1.frame_locator(SELECTORS["captcha_iframe_2"])
                iframe3 = iframe2.frame_locator(SELECTORS["captcha_iframe_3"])

                if iframe3.locator(SELECTORS["puzzle_button"]).is_visible(timeout=5000):
                    logger("✓ Puzzle captcha detected", level=level)
                    return True
            except Exception:
                pass

            logger("✗ Puzzle not found", level=level)
            return False
        except Exception:
            logger("✗ Puzzle check failed", level=level)
            return False

    def _wait_for_captcha_to_clear(self, level: int = 0) -> bool:
        logger("[######] Waiting for captcha to clear...", level=level)

        # Initial check with retries
        captcha_exists = self._check_captcha_iframe_exists(level=level + 1)

        if not captcha_exists:
            for _ in range(3):
                self.helper.wait_natural_delay(2, 5)
                captcha_exists = self._check_captcha_iframe_exists(level=level + 1)
                if captcha_exists:
                    break

        captcha_check_count = 0
        while captcha_exists:
            captcha_check_count += 1

            if captcha_check_count > MAX_CAPTCHA_WAIT_ITERATIONS:
                logger("⚠ Max captcha wait iterations reached", level=level + 1)
                break

            logger("Captcha iframe still present, waiting...", level=level + 1)

            if captcha_check_count > 5:
                self.helper.wait_natural_delay(1, 3)
                if self._check_puzzle_displayed(level=level + 1):
                    logger("✗ Visual puzzle captcha detected - cannot proceed", level=level + 1)
                    return False

            self.helper.wait_natural_delay(1, 3)
            captcha_exists = self._check_captcha_iframe_exists(level=level + 1)

        logger("✓ Captcha cleared", level=level + 1)
        return True

    def _wait_for_verification_form(self, level: int = 0) -> bool:
        logger("[######] Waiting for verification form...", level=level)

        for attempt in range(5):
            if self.helper.check_element_exists(SELECTORS["verification_form"], timeout=10000):
                logger("✓ Verification form found", level=level + 1)
                return True

            logger(f"Verification form not found, retrying ({attempt + 1}/5)...", level=level + 1)
            self.helper.wait_natural_delay(2, 5)

        logger("✗ Verification form not found after retries", level=level + 1)
        return False

    def _extract_verification_code(self, email_content: str) -> Optional[str]:
        match = re.search(r">\s*(\d{8})\s*</span>", email_content)
        return match.group(1) if match else None

    def _fetch_verification_code_from_email(self, level: int = 0) -> Optional[str]:
        logger("[######] Fetching verification code from email...", level=level)

        new_email = self.email_service.wait_for_email(120)
        if not new_email:
            logger("✗ No email received", level=level + 1)
            return None

        content = self.email_service.get_email(new_email)
        if not content:
            logger("✗ Failed to get email content", level=level + 1)
            return None

        code = self._extract_verification_code(content[self.email_service.body_key])
        if code:
            self.verification_code = code
            logger(f"✓ Verification code found: {code}", level=level + 1)
        else:
            logger("✗ Verification code not found in email", level=level + 1)

        return code

    def _fill_verification_code(self, code: str, level: int = 0) -> bool:
        logger("[######] Filling verification code...", level=level)

        for i, digit in enumerate(code):
            selector = SELECTORS["verification_code_field"].format(index=i)
            if not self.helper.fill(selector, digit, humanize_typing=False, clear_first=True):
                logger(f"✗ Failed to fill digit {i + 1}", level=level + 1)
                return False
            logger(f"✓ Filled digit {i + 1}: {digit}", level=level + 1)
            self.helper.wait_natural_delay(0.3, 0.7)

        logger("✓ Verification code filled", level=level + 1)
        return True

    def _submit_verification_code(self, level: int = 0) -> bool:
        logger("[######] Submitting verification code...", level=level)

        if self.helper.check_element_visible(SELECTORS["verification_submit"], timeout=5000):
            if self.helper.click(SELECTORS["verification_submit"]):
                logger("✓ Verification submitted", level=level + 1)
                return True

        # Check if auto-submitted by URL change
        current_url = self.helper.get_current_url()
        if current_url and current_url != GITHUB_SIGNUP_URL:
            logger("✓ Code auto-submitted (URL changed)", level=level + 1)
            return True

        logger("✗ Code submission failed", level=level + 1)
        return False

    # --------------------------------------------------------------------------
    # 2FA Setup
    # --------------------------------------------------------------------------
    def _login(self, level: int = 0) -> bool:
        logger("[######] Logging in...", level=level)

        login_value = self.account_data.username or self.account_data.email_address

        # Use execute_actions for login flow
        login_actions = [
            {"type": "fill", "selector": SELECTORS["login_field"], "value": login_value, "press_tab_after": True},
            {"type": "wait", "min_delay": 0.5, "max_delay": 1.0},
            {"type": "fill", "selector": SELECTORS["login_password"], "value": self.account_data.password, "press_tab_after": True},
            {"type": "wait", "min_delay": 0.5, "max_delay": 1.0},
            {"type": "click", "selector": SELECTORS["login_submit"]},
            {"type": "wait", "min_delay": 1.0, "max_delay": 2.0},
        ]

        if self.helper.execute_actions(login_actions):
            logger("✓ Login successful", level=level + 1)
            return True

        logger("✗ Login failed", level=level + 1)
        return False

    def _wait_until_on_login_page(self, level: int = 0) -> bool:
        logger("[######] Waiting for login page...", level=level)

        for attempt in range(10):
            current_url = self.helper.get_current_url()
            if current_url and "github.com/login" in current_url:
                logger("✓ On login page", level=level + 1)
                return True
            logger("⚠ Not on login page, waiting...", level=level + 1)
            self.helper.wait_natural_delay(2, 4)

        logger("✗ Failed to reach login page", level=level + 1)
        return False

    def _wait_for_dashboard(self, level: int = 0) -> bool:
        logger("[######] Waiting for dashboard...", level=level)

        if self.helper.wait_for_url_contains("dashboard", timeout=30000, retries=10):
            logger("✓ Redirected to dashboard", level=level + 1)
            return True

        logger("✗ Failed to reach dashboard", level=level + 1)
        return False

    def _simulate_human_scrolling(self) -> None:
        """Simulate human scrolling behavior."""
        self.helper.scroll_page("down")
        self.helper.wait_natural_delay(0.5, 1.0)
        self.helper.scroll_page("middle")
        self.helper.wait_natural_delay(0.5, 1.0)
        self.helper.scroll_page("up")
        self.helper.wait_natural_delay(0.5, 1.0)

    def _setup_2fa(self, level: int = 0) -> bool:
        logger("[######] Setting up 2FA...", level=level)

        try:
            # Wait for and perform login
            if not self._wait_until_on_login_page(level=level + 1):
                self.helper.goto(GITHUB_LOGIN_URL)
                self.helper.wait_natural_delay(2, 4)
                if not self._wait_until_on_login_page(level=level + 1):
                    return False

            if not self._login(level=level + 1):
                return False

            self.helper.wait_natural_delay(2, 4)

            # Wait for dashboard
            if not self._wait_for_dashboard(level=level + 1):
                return False

            self.helper.wait_natural_delay(1, 2)
            logger("Simulating human behavior...", level=level + 1)
            self._simulate_human_scrolling()

            # Navigate to 2FA settings using actions
            nav_actions = [
                # Open user menu
                {"type": "click", "selector": SELECTORS["user_menu"]},
                {"type": "wait", "min_delay": 2, "max_delay": 4},
                # Click settings
                {"type": "click", "selector": SELECTORS["settings_link"]},
                {"type": "wait", "min_delay": 2, "max_delay": 4},
            ]

            if not self.helper.execute_actions(nav_actions):
                # Fallback: try avatar click or direct navigation
                logger("Menu click failed, trying fallback...", level=level + 1)
                if not self.helper.click(SELECTORS["user_avatar"]):
                    self.helper.goto("https://github.com/settings/profile", timeout=30000)
                    self.helper.wait_natural_delay(1, 2)
                    if not self.helper.wait_for_url_contains("profile", timeout=30000, retries=10):
                        return False

            self.helper.wait_natural_delay(2, 4)

            # Scroll and navigate to security
            self.helper.scroll_page("down", 200)
            self.helper.wait_natural_delay(2, 4)
            self.helper.scroll_page("up")
            self.helper.wait_natural_delay(2, 4)

            logger("Clicking Password and authentication...", level=level + 1)
            if not self.helper.click(SELECTORS["security_link"]):
                logger("✗ Failed to click security link", level=level + 1)
                self.helper.goto("https://github.com/settings/security", timeout=30000)
                self.helper.wait_natural_delay(1, 2)
                if not self.helper.wait_for_url_contains("security", timeout=30000, retries=10):
                    return False

            self.helper.wait_natural_delay(2, 4)
            self.helper.scroll_page("down")
            self.helper.wait_natural_delay(2, 4)

            logger("Clicking Enable 2FA...", level=level + 1)
            if not self.helper.click(SELECTORS["enable_2fa_link"]):
                logger("✗ Failed to click Enable 2FA", level=level + 1)
                self.helper.goto("https://github.com/settings/two_factor_authentication/setup/intro", timeout=30000)
                self.helper.wait_natural_delay(2, 4)
                if not self.helper.wait_for_url_contains("intro", timeout=30000, retries=10):
                    return False

            self.helper.wait_natural_delay(2, 4)

            # Get 2FA secret
            secret = self.helper.get_element_content(SELECTORS["2fa_secret"], content_type="text", timeout=10000)
            if not secret:
                logger("✗ Failed to get 2FA secret", level=level + 1)
                return False

            self.secret = secret.strip()
            logger(f"✓ Secret obtained: {self.secret}", level=level + 1)

            self.helper.wait_natural_delay(2, 4)

            # Generate and enter 2FA code
            code = get_2fa_code(self.secret)
            logger(f"Generated 2FA Code: {code}", level=level + 1)

            if not self.helper.type_text(SELECTORS["2fa_code_input"], code):
                logger("✗ Failed to enter 2FA code", level=level + 1)
                return False

            self.helper.press_key("Tab")
            self.helper.wait_natural_delay(2, 4)

            # Click continue
            recovery_codes_list_exists = False
            logger("Clicking Continue...", level=level + 1)
            for i in range(5):
                if self.helper.click(SELECTORS["2fa_continue_button"], retries=1):
                    logger("✓ Continue clicked", level=level + 1)
                    break
                
                if self.helper.check_element_exists(SELECTORS["recovery_codes_list"], retries=1, timeout=10000):
                    recovery_codes_list_exists = True
                    logger("✓ Recovery codes page reached. Button continue clicked automatically", level=level + 1)
                    break
                
                self.helper.wait_natural_delay(2, 4)

                if i == 4:
                    logger("✗ Failed to click Continue", level=level + 1)
                    return False

            self.helper.wait_natural_delay(2, 4)

            # Get recovery codes
            if not recovery_codes_list_exists:
                if self.helper.check_element_exists(SELECTORS["recovery_codes_list"], timeout=10000):
                    logger("✓ Recovery codes page reached", level=level + 1)
                else:
                    logger("⚠ Recovery codes not immediately visible", level=level + 1)

            self.helper.wait_natural_delay(1, 2)

            # Extract recovery codes
            codes = self.helper.get_all_elements_content(
                f"{SELECTORS['recovery_codes_list']} li",
                content_type="inner_text"
            )
            if codes:
                self.recovery_codes = codes
                logger(f"✓ Saved {len(self.recovery_codes)} recovery codes", level=level + 1)
            else:
                logger("✗ Failed to get recovery codes", level=level + 1)

            # Complete 2FA setup
            finish_actions = [
                {"type": "click", "selector": SELECTORS["download_codes_button"]},
                {"type": "wait", "min_delay": 2, "max_delay": 4},
                {"type": "click", "selector": SELECTORS["saved_codes_button"]},
                {"type": "wait", "min_delay": 2, "max_delay": 4},
                {"type": "click", "selector": SELECTORS["done_button"]},
                {"type": "wait", "min_delay": 2, "max_delay": 4},
            ]

            self.helper.execute_actions(finish_actions)

            logger("✓ 2FA Setup completed", level=level + 1)
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
                "email": self.account_data.email_address,
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

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(account_dump, f, indent=4)
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
                # Generate account info
                self._generate_account_info(level=level + 1)

                # Get email address
                if not self._get_email_address(level=level + 1):
                    return False

                # Launch browser
                if not self._launch_browser(level=level + 1):
                    return False

                # Open signup page
                if not self._open_signup(level=level + 1):
                    return False

                # Accept cookies
                self._accept_cookies_if_present(level=level + 1)

                # Fill signup form
                if not self._fill_signup_form(level=level + 1):
                    return False
                
                # Check username error
                for i in range(MAX_RETRIES_FOR_USERNAME_UPDATE):
                    logger(f"Checking username error... {i + 1}/{MAX_RETRIES_FOR_USERNAME_UPDATE}", level=level + 1)
                    if self._check_username_error(level=level + 1):
                        if i == MAX_RETRIES_FOR_USERNAME_UPDATE - 1:
                            return False
                        self._change_username(level=level + 1)
                    else:
                        break

                # Submit signup
                if not self._submit_signup(level=level + 1):
                    return False

                # Wait for captcha to clear
                if not self._wait_for_captcha_to_clear(level=level + 1):
                    return False

                # Wait for verification form
                if not self._wait_for_verification_form(level=level + 1):
                    return False

                # Get verification code from email
                code = self._fetch_verification_code_from_email(level=level + 1)
                if not code:
                    logger("✗ Verification code not found in email", level=level + 2)
                    return False

                # Fill verification code
                if not self._fill_verification_code(code, level=level + 1):
                    return False

                # Submit verification code
                if not self._submit_verification_code(level=level + 1):
                    return False

                # Wait for account creation
                logger("Waiting for account creation...", level=level + 1)
                time.sleep(20)
                logger("✓ Waited for account creation", level=level + 2)

                # Setup 2FA
                if not self._setup_2fa(level=level + 1):
                    logger("✗ 2FA Setup failed", level=level + 1)
                else:
                    logger("✓ 2FA Setup completed", level=level + 1)

                logger("✓ Flow execution finished", level=level + 1)

                # Wait for user input
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
                    if self.use_tor:
                        renew_tor(level=level + 1)
                    time.sleep(random.uniform(5, 10))

            except Exception as e:
                if attempt < max_retries - 1:
                    logger(
                        f"✗ Flow error, retrying ({attempt + 1}/{max_retries}): {format_error(e)}",
                        level=level + 1,
                    )
                    if self.use_tor:
                        renew_tor(level=level + 1)
                    time.sleep(random.uniform(5, 10))
                else:
                    logger(f"✗ Flow failed after {max_retries} attempts: {format_error(e)}", level=level + 1)

        return False


if __name__ == "__main__":
    generator = GithubTMailorGenerator(use_tor=True)
    generator.run_flow_with_retries(max_retries=1000)