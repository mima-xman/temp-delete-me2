"""
GitHub Account Generator using temporary email services.

This module automates GitHub account creation by:
1. Generating random account credentials
2. Obtaining a temporary email address
3. Automating the GitHub signup flow with Playwright
4. Handling email verification
5. Setting up 2FA (optional)
"""

import json
import os
import random
import re
import string
import time
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

from config import (
    ARGS,
    BRAVE_PATH,
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
from TempMailServices.TMailorAPI import TMailorAPI
from TempMailServices.TempMailExtensionAPI import TempMailExtensionAPI
from TempMailServices.TempMailIOAPI import TempMailIOAPI
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
GITHUB_CAPTCHA_IFRAME_SELECTOR = "#captcha-container-nux > div > div > div:nth-child(3) > iframe"

# Username prefix for generated accounts
USERNAME_PREFIX = "dev1"

# Maximum iterations to wait for captcha to resolve
MAX_CAPTCHA_WAIT_ITERATIONS = 25


class GithubTMailorGenerator:
    """
    GitHub account generator using temporary email services.

    Automates the complete GitHub signup flow including:
    - Credential generation
    - Temporary email acquisition
    - Form filling with human-like behavior
    - Email verification code handling
    - Optional 2FA setup

    Attributes:
        use_tor: Whether to route traffic through Tor network.
    """

    def __init__(
        self,
        use_tor: bool = False
    ):
        """
        Initialize the GitHub account generator.

        Args:
            use_tor: Enable Tor network for anonymity.
        """
        self.use_tor = use_tor

        # Browser and page instances
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.email_service = None

        # Account data
        self.account_data: Dict[str, Any] = {
            "email_address": None,
            "email_token": None,
            "password": None,
            "username": None,
            "created_at": None,
            "status": "pending"
        }
        self.ip: Optional[str] = None
        self.verification_code: Optional[str] = None
        self.secret: Optional[str] = None
        self.recovery_codes: list = []

        # Debugging
        self.screenshot_counter = 1

        # Log Tor configuration
        logger(f"TOR Port: {TOR_PORT}", level=1)
        logger(f"TOR Control Port: {TOR_CONTROL_PORT}", level=1)

        # Create output directories with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.screenshots_dir = os.path.join(OUTPUT_DIR, f"github_screenshots_{timestamp}")
        self.html_reports_dir = os.path.join(OUTPUT_DIR, f"github_html_reports_{timestamp}")

        os.makedirs(OUTPUT_DIR, exist_ok=True)
        os.makedirs(self.screenshots_dir, exist_ok=True)
        os.makedirs(self.html_reports_dir, exist_ok=True)

        # Initialize Tor if enabled
        if self.use_tor:
            logger("Using TOR network for emails...", level=1)
            success, self.ip = renew_tor(level=1)

    # ==========================================================================
    # Human-like Interaction Helpers
    # ==========================================================================

    def human_delay(self, min_ms: int = 500, max_ms: int = 1500) -> None:
        """
        Add a random delay to simulate human reaction time.

        Args:
            min_ms: Minimum delay in milliseconds.
            max_ms: Maximum delay in milliseconds.
        """
        time.sleep(random.uniform(min_ms, max_ms) / 1000)

    def natural_delay(self, min_s: float = 1, max_s: float = 3) -> None:
        """
        Add a natural random pause between major actions.

        Args:
            min_s: Minimum delay in seconds.
            max_s: Maximum delay in seconds.
        """
        time.sleep(random.uniform(min_s, max_s))

    def human_type(
        self,
        selector: str,
        text: str,
        min_delay_ms: int = 50,
        max_delay_ms: int = 200
    ) -> None:
        """
        Type text with random delays between keystrokes to simulate human typing.

        Falls back to direct fill if typing fails.

        Args:
            selector: CSS selector for the input field.
            text: Text to type.
            min_delay_ms: Minimum delay between keystrokes in milliseconds.
            max_delay_ms: Maximum delay between keystrokes in milliseconds.
        """
        try:
            delay = random.randint(min_delay_ms, max_delay_ms)
            self.page.type(selector, text, delay=delay, timeout=60000)
        except Exception as e:
            logger(f"⚠ Human type fallback for {selector}: {e}")
            self.page.fill(selector, text)

    def human_click(self, selector: str) -> bool:
        """
        Click an element with human-like behavior (hover first, then click).

        Falls back to force click if normal click fails.

        Args:
            selector: CSS selector for the element to click.

        Returns:
            True if click succeeded, False otherwise.
        """
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

    def _wait_for_network_idle(self) -> None:
        """Wait for network to become idle (no pending requests)."""
        try:
            self.page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # Timeout is acceptable here

    # ==========================================================================
    # Account Generation Methods
    # ==========================================================================

    def _generate_account_info(self, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Generate random account credentials.

        Creates a password, selects random first/last names, and generates
        a username in the format: {firstname}{lastname}-{prefix}

        Args:
            level: Logging indentation level.

        Returns:
            Account data dictionary, or None on failure.
        """
        logger("[######] Generating account info...", level=level)

        try:
            # Generate strong password with mixed characters
            password_chars = string.ascii_letters + string.digits + "!@#$%^&*"
            password = ''.join(random.choice(password_chars) for _ in range(15))

            # Generate name from configured lists
            first_name = random.choice(FIRST_NAMES)
            last_name = random.choice(LAST_NAMES)

            # Generate username: {firstname}{lastname}-{prefix} in lowercase
            username = f"{first_name}{last_name}-{USERNAME_PREFIX}".lower()

            self.account_data = {
                "email_address": None,
                "email_token": None,
                "password": password,
                "username": username,
                "created_at": datetime.now().isoformat(),
                "status": "pending"
            }

            logger(f"✓ Generated account info: {username} | {password}", level=level + 1)
            return self.account_data

        except Exception as e:
            logger(f"✗ Failed to generate account info: {format_error(e)}", level=level + 1)
            return None

    def _get_email_address(self, level: int = 0) -> Optional[str]:
        """
        Obtain a temporary email address from the email service.

        Available services (change by modifying email_service instantiation):
        - EmailOnDeck (default)
        - TempMailExtensionAPI
        - TMailorAPI
        - TempMailIOAPI

        Args:
            level: Logging indentation level.

        Returns:
            Email address string, or None on failure.
        """
        logger("[######] Getting email address...", level=level)

        try:
            # Select email service (change here to use different provider)
            self.email_service = EmailOnDeck()

            result = self.email_service.generate_email()

            if not result or not result.get('email'):
                logger("✗ Failed to generate email address", level=level + 1)
                return None

            email_address = result['email']
            self.account_data['email_address'] = email_address
            self.account_data['email_token'] = result.get('token', 'N/A')

            logger(f"✓ Email obtained: {email_address}", level=level + 1)
            return email_address

        except Exception as e:
            logger(f"✗ Failed to get email address: {format_error(e)}", level=level + 1)
            return None

    # ==========================================================================
    # Browser Management
    # ==========================================================================

    def _launch_browser(self, level: int = 0) -> bool:
        """
        Launch the browser with anti-detection settings.

        Configures the browser with:
        - Custom viewport and user agent
        - Tor proxy (if enabled)
        - WebDriver property removal for stealth

        Args:
            level: Logging indentation level.

        Returns:
            True if browser launched successfully, False otherwise.
        """
        logger("[######] Launching browser...", level=level)

        try:
            launch_kwargs = {
                "headless": HEADLESS,
                "args": ARGS
            }

            # Configure Tor proxy if enabled
            if self.use_tor:
                tor_proxy = f"socks5://127.0.0.1:{TOR_PORT}"
                launch_kwargs["proxy"] = {"server": tor_proxy}
                logger(f"Using Tor proxy: {tor_proxy}", level=level + 1)

            # Use Chrome if available, otherwise fall back to Chromium
            browser_path = CHROME_PATH
            if os.path.exists(browser_path):
                launch_kwargs["executable_path"] = browser_path
                logger(f"Using Browser: {browser_path}", level=level + 1)
            else:
                logger(f"⚠ Browser not found at {browser_path}, using default Chromium", level=level + 1)

            self.browser = self.playwright.chromium.launch(**launch_kwargs)

            self.context = self.browser.new_context(
                viewport=VIEWPORT,
                locale=LOCALE,
                user_agent=USER_AGENT
            )

            # Remove webdriver property to avoid detection
            self.context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            self.page = self.context.new_page()

            logger("✓ Browser launched successfully", level=level + 1)
            return True

        except Exception as e:
            logger(f"✗ Error launching browser: {format_error(e)}", level=level + 1)
            return False

    # ==========================================================================
    # Form Interaction Helpers
    # ==========================================================================

    def _wait_and_fill(
        self,
        selector: str,
        value: str,
        field_name: str,
        level: int = 0
    ) -> bool:
        """
        Wait for a form field to become visible and fill it.

        Args:
            selector: CSS selector for the input field.
            value: Value to enter.
            field_name: Human-readable field name for logging.
            level: Logging indentation level.

        Returns:
            True if field was filled successfully, False otherwise.
        """
        logger(f"[######] Filling {field_name}...", level=level)

        try:
            self.page.wait_for_selector(selector, state="visible", timeout=30000)
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

    # ==========================================================================
    # Captcha Checking Methods
    # ==========================================================================

    def _check_captcha_iframe_exists(self, level: int = 0) -> bool:
        """
        Check if the captcha iframe is present on the page.

        Args:
            level: Logging indentation level.

        Returns:
            True if captcha iframe exists, False otherwise.
        """
        try:
            self.page.wait_for_selector(
                GITHUB_CAPTCHA_IFRAME_SELECTOR,
                state='attached',
                timeout=30000
            )
            logger("✓ Captcha iframe exists", level=level + 2)
            return True
        except Exception:
            logger("✗ Captcha iframe not found", level=level + 2)
            return False

    def _check_puzzle_displayed(self, level: int = 0) -> bool:
        """
        Check if a visual puzzle captcha is being displayed.

        Navigates through nested iframes to find the puzzle button.

        Args:
            level: Logging indentation level.

        Returns:
            True if puzzle is displayed, False otherwise.
        """
        try:
            # Navigate through nested iframes
            logger(f"Checking for puzzle in iframe...", level=level + 1)
            self.page.wait_for_selector(GITHUB_CAPTCHA_IFRAME_SELECTOR, state='attached', timeout=30000)
            iframe1 = self.page.frame_locator(GITHUB_CAPTCHA_IFRAME_SELECTOR)

            iframe2_selector = "#funcaptcha > div > iframe"
            iframe1.locator(iframe2_selector).wait_for(state='attached', timeout=30000)
            iframe2 = iframe1.frame_locator(iframe2_selector)

            iframe3_selector = "#game-core-frame"
            iframe2.locator(iframe3_selector).wait_for(state='attached', timeout=30000)
            iframe3 = iframe2.frame_locator(iframe3_selector)

            # Check for visual puzzle button
            puzzle_btn_selector = "#root > div > div > button[aria-label='Visual puzzle']"
            if iframe3.locator(puzzle_btn_selector).is_visible(timeout=5000):
                logger("✓ Puzzle captcha detected", level=level + 1)
                return True

            logger("✗ Puzzle not found", level=level + 1)
            return False

        except Exception:
            logger("✗ Puzzle check failed", level=level + 1)
            return False

    def _check_verification_code_form_exists(self, level: int = 0) -> bool:
        """
        Check if the verification code input form is displayed.

        Args:
            level: Logging indentation level.

        Returns:
            True if verification form exists, False otherwise.
        """
        try:
            self.page.wait_for_selector(
                GITHUB_VERIFICATION_FORM_SELECTOR,
                state='attached',
                timeout=30000
            )
            logger("✓ Verification code form exists", level=level + 2)
            return True
        except Exception:
            logger("✗ Verification code form not found", level=level + 2)
            return False

    # ==========================================================================
    # Verification Code Handling
    # ==========================================================================

    def _extract_verification_code(self, email_content: str) -> Optional[str]:
        """
        Extract the 8-digit verification code from email content.

        Args:
            email_content: HTML content of the verification email.

        Returns:
            The 8-digit verification code, or None if not found.
        """
        match = re.search(r'>\s*(\d{8})\s*</span>', email_content)
        if match:
            return match.group(1)
        return None

    def _fill_verification_code(self, code: str, level: int = 0) -> None:
        """
        Fill the verification code into the individual input fields.

        GitHub uses 8 separate input fields for the verification code.

        Args:
            code: The 8-digit verification code.
            level: Logging indentation level.
        """
        for i, digit in enumerate(code):
            self.page.fill(f"#launch-code-{i}", digit)
            logger(f"Filled verification code field {i + 1}: {digit}", level=level)
            self.natural_delay()

    # ==========================================================================
    # 2FA Setup
    # ==========================================================================

    def _login(self, level: int = 0) -> bool:
        """
        Log into GitHub with the generated credentials.

        Args:
            level: Logging indentation level.

        Returns:
            True if login succeeded, False otherwise.
        """
        logger("[######] Logging in...", level=level)

        try:
            email_selector = "#login_field"
            login_value = self.account_data.get('username') or self.account_data.get('email_address')

            if not self._wait_and_fill(email_selector, login_value, "Login Field", level=level + 1):
                return False

            password_selector = "#password"
            if not self._wait_and_fill(password_selector, self.account_data['password'], "Password", level=level + 1):
                return False

            self.natural_delay()

            login_button_selector = "body > div > div > main > div > div > form > div:nth-child(4) > input"
            logger("Clicking Login...", level=level + 1)
            self.human_click(login_button_selector)

            self.natural_delay()
            return True

        except Exception as e:
            logger(f"✗ Login failed: {format_error(e)}", level=level + 1)
            return False

    def _setup_2fa(self, level: int = 0) -> bool:
        """
        Set up two-factor authentication for the account.

        Navigates to settings, enables 2FA, extracts the secret,
        generates a verification code, and saves recovery codes.

        Args:
            level: Logging indentation level.

        Returns:
            True if 2FA setup succeeded, False otherwise.
        """
        logger("[######] Setting up 2FA...", level=level)

        try:
            # Wait for redirect to login page
            for attempt in range(10):
                current_url = self.page.url
                if "github.com/login" in current_url:
                    logger("✓ On login page", level=level + 1)
                    break
                logger("⚠ Not on login page, waiting...", level=level + 1)
                if attempt == 9:
                    return False
                self.natural_delay(2, 4)

            # Login
            if not self._login(level=level + 1):
                return False

            self.natural_delay(2, 4)

            # Wait for dashboard redirect
            logger("Checking redirection to dashboard...", level=level + 1)
            for attempt in range(10):
                try:
                    self.page.wait_for_url("https://github.com/dashboard", timeout=30000)
                    logger("✓ Redirected to dashboard", level=level + 1)
                    break
                except Exception:
                    logger("⚠ Not on dashboard yet, waiting...", level=level + 1)
                    self.natural_delay(2, 4)
                    if attempt == 9:
                        return False

            self.natural_delay()

            # Simulate human browsing behavior
            logger("Simulating human behavior...", level=level + 1)
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.natural_delay()
            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            self.natural_delay()
            self.page.evaluate("window.scrollTo(0, 0)")
            self.natural_delay()

            # Navigate to settings
            logger("Opening user menu...", level=level + 1)
            self.human_click("button[aria-label='Open user navigation menu']")
            self.natural_delay()

            logger("Clicking Settings...", level=level + 1)
            self.human_click("#__primerPortalRoot__ > div > div a[href='/settings/profile']")
            self.natural_delay()

            # Scroll behavior
            self.page.evaluate("window.scrollBy(0, 200)")
            self.natural_delay(0.5, 1)
            self.page.evaluate("window.scrollTo(0, 0)")
            self.natural_delay()

            # Navigate to security settings
            logger("Clicking Password and authentication...", level=level + 1)
            self.human_click("a[href='/settings/security']")
            self.natural_delay()

            self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            self.natural_delay()

            # Enable 2FA
            logger("Clicking Enable 2FA...", level=level + 1)
            self.human_click("a[href='/settings/two_factor_authentication/setup/intro']")
            self.natural_delay()

            # Get 2FA secret
            secret_selector = (
                "#two-factor-setup-verification-mashed-secret > scrollable-region > div > div, "
                "[data-target='two-factor-setup-verification.mashedSecret']"
            )
            self.page.wait_for_selector(secret_selector, state='visible')
            secret = self.page.text_content(secret_selector)

            if secret:
                self.secret = secret.strip()
                logger(f"✓ Secret obtained: {self.secret}", level=level + 2)
            else:
                logger("✗ Failed to get secret", level=level + 2)
                return False

            self.natural_delay()

            # Generate and enter 2FA code
            code = get_2fa_code(self.secret)
            logger(f"Generated 2FA Code: {code}", level=level + 2)

            input_selector = "#two-factor-setup-verification-step > div:nth-child(1) > form > div > div > input"
            self.human_type(input_selector, code)

            logger("Pressing Tab...", level=level + 1)
            self.page.keyboard.press("Tab")
            self.natural_delay()

            # Continue to recovery codes
            continue_btn = (
                "#wizard-step-factor > div > div > div > div > div > "
                "button[data-action='click:single-page-wizard-step#onNext']"
            )
            logger("Clicking Continue...", level=level + 1)
            self.human_click(continue_btn)
            self.natural_delay()

            # Get recovery codes
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

            # Download recovery codes
            logger("Clicking Download codes...", level=level + 1)
            self.human_click("button[data-action='click:two-factor-setup-recovery-codes#onDownloadClick']")
            self.natural_delay()

            # Confirm saved
            logger("Clicking 'I have saved my recovery codes'...", level=level + 1)
            self.human_click(
                "button[data-target='single-page-wizard-step.nextButton']:has-text('I have saved my recovery codes')"
            )
            self.natural_delay()

            # Complete setup
            logger("Clicking Done...", level=level + 1)
            self.human_click("button[data-target='single-page-wizard-step.nextButton']:has-text('Done')")
            self.natural_delay()

            return True

        except Exception as e:
            logger(f"✗ 2FA Setup error: {format_error(e)}", level=level + 1)
            self._save_screenshot(level=level + 1)
            return False

    # ==========================================================================
    # Debugging and Persistence
    # ==========================================================================

    def _save_screenshot(self, level: int = 0) -> None:
        """
        Take a screenshot for debugging purposes.

        Args:
            level: Logging indentation level.
        """
        logger("[######] Saving screenshot...", level=level)

        if self.page:
            try:
                screenshot_path = f"{self.screenshots_dir}/{self.screenshot_counter}.png"
                self.page.screenshot(path=screenshot_path)
                logger(f"✓ Screenshot saved: {screenshot_path}", level=level + 1)
                self.screenshot_counter += 1
            except Exception as e:
                logger(f"✗ Screenshot failed: {format_error(e)}", level=level + 1)
        else:
            logger("✗ No page to save screenshot", level=level + 1)

    def _save_account_data(self, level: int = 0) -> None:
        """
        Save account credentials to a JSON file.

        Args:
            level: Logging indentation level.
        """
        try:
            account_data = {
                'email': self.account_data.get('email'),
                'email_token': self.account_data.get('email_token'),
                'username': self.account_data.get('username'),
                'password': self.account_data.get('password'),
                'ip': self.ip,
                'verification_code': self.verification_code,
                'secret': self.secret,
                'recovery_codes': self.recovery_codes
            }

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filepath = f"{OUTPUT_DIR}/account_{timestamp}.json"

            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(account_data, indent=4))
                logger(f"✓ Account data saved: {filepath}", level=level + 2)

        except Exception as e:
            logger(f"✗ Failed to save account data: {format_error(e)}", level=level + 2)

    # ==========================================================================
    # Main Flow
    # ==========================================================================

    def run_flow(self, level: int = 0) -> bool:
        """
        Execute the complete GitHub account creation flow.

        Steps:
        1. Generate account credentials
        2. Obtain temporary email
        3. Launch browser and navigate to signup
        4. Fill signup form
        5. Wait for and handle captcha (if any)
        6. Extract and enter verification code
        7. Complete account creation
        8. Set up 2FA (optional)

        Args:
            level: Logging indentation level.

        Returns:
            True if account was created successfully, False otherwise.
        """
        logger("GitHub TMailor Account Generator", level=level)

        with sync_playwright() as p:
            self.playwright = p

            try:
                # Step 1: Generate credentials
                self._generate_account_info(level=level + 1)

                # Step 2: Get email
                current_email = self._get_email_address(level=level + 1)
                if not current_email:
                    return False

                self.account_data['email_address'] = current_email

                # Step 3: Launch browser
                if not self._launch_browser(level=level + 1):
                    return False

                # Step 4: Navigate to signup
                logger("[######] Opening GitHub signup...", level=level + 1)
                self.page.goto(GITHUB_SIGNUP_URL, timeout=60000)
                self._wait_for_network_idle()

                # Accept cookies if banner appears
                try:
                    self.page.wait_for_selector(GITHUB_COOKIES_BUTTON_SELECTOR, timeout=30000)
                    self.page.click(GITHUB_COOKIES_BUTTON_SELECTOR)
                    logger("✓ Accepted cookies", level=level + 2)
                except Exception:
                    logger("✗ Cookie banner not found or already accepted", level=level + 2)

                # Step 5: Fill signup form
                self.natural_delay()
                if not self._wait_and_fill(
                    GITHUB_EMAIL_SELECTOR,
                    self.account_data['email_address'],
                    "Email",
                    level=level + 1
                ):
                    return False

                self.natural_delay()

                # Continue to password field
                if not self.page.is_visible(GITHUB_PASSWORD_SELECTOR):
                    logger("Password field not yet visible, pressing Enter...", level=level + 1)
                    self.page.press(GITHUB_EMAIL_SELECTOR, "Enter")

                if not self._wait_and_fill(
                    GITHUB_PASSWORD_SELECTOR,
                    self.account_data['password'],
                    "Password",
                    level=level + 1
                ):
                    return False

                self.natural_delay()

                # Continue to username field
                if not self.page.is_visible(GITHUB_USERNAME_SELECTOR):
                    logger("Username field not yet visible, pressing Enter...", level=level + 1)
                    self.page.press(GITHUB_PASSWORD_SELECTOR, "Enter")

                if not self._wait_and_fill(
                    GITHUB_USERNAME_SELECTOR,
                    self.account_data['username'],
                    "Username",
                    level=level + 1
                ):
                    return False

                self.natural_delay(5, 10)

                # Step 6: Submit signup form
                logger("[######] Clicking Submit...", level=level + 1)

                if not self.page.is_visible(GITHUB_SUBMIT_BUTTON_SELECTOR):
                    self.page.press(GITHUB_USERNAME_SELECTOR, "Enter")

                self.page.wait_for_selector(GITHUB_SUBMIT_BUTTON_SELECTOR, state='visible', timeout=10000)
                self.natural_delay()
                self.human_click(GITHUB_SUBMIT_BUTTON_SELECTOR)
                logger("✓ Submit clicked", level=level + 2)

                self.natural_delay(2, 5)

                # Step 7: Wait for captcha to resolve (if any)
                captcha_exists = self._check_captcha_iframe_exists(level=level + 1)
                if not captcha_exists:
                    # Retry a few times
                    for _ in range(3):
                        captcha_exists = self._check_captcha_iframe_exists(level=level + 1)
                        if captcha_exists:
                            break
                        self.natural_delay(2, 5)

                # Wait for captcha to be solved (manually or automatically)
                captcha_check_count = 0
                while captcha_exists:
                    captcha_check_count += 1

                    if captcha_check_count > MAX_CAPTCHA_WAIT_ITERATIONS:
                        logger("⚠ Max captcha wait iterations reached", level=level + 2)
                        break

                    logger("Captcha iframe still present, waiting...", level=level + 2)

                    # Check for unsolvable puzzle after several iterations
                    if captcha_check_count > 5:
                        self.natural_delay()
                        if self._check_puzzle_displayed(level=level + 1):
                            logger("✗ Visual puzzle captcha detected - cannot proceed", level=level + 2)
                            return False

                    self.natural_delay()
                    captcha_exists = self._check_captcha_iframe_exists(level=level + 1)

                # Step 8: Wait for verification code form
                verification_form_exists = self._check_verification_code_form_exists(level=level + 1)
                if not verification_form_exists:
                    for _ in range(3):
                        verification_form_exists = self._check_verification_code_form_exists(level=level + 1)
                        if verification_form_exists:
                            break
                        self.natural_delay(2, 5)

                # Step 9: Get verification code from email
                code = None
                new_email = self.email_service.wait_for_email(120)
                if new_email:
                    content = self.email_service.get_email(new_email)
                    if content:
                        code = self._extract_verification_code(content[self.email_service.body_key])
                        if code:
                            self.verification_code = code
                            logger(f"Verification code: {code}", level=level + 2)

                if not code:
                    logger("✗ Verification code not found in email", level=level + 2)
                    return False

                # Step 10: Fill verification code
                self._fill_verification_code(code, level=level + 2)

                # Step 11: Submit verification code
                try:
                    self.page.wait_for_selector(
                        GITHUB_VERIFICATION_SUBMIT_SELECTOR,
                        state='visible',
                        timeout=10000
                    )
                    self.page.click(GITHUB_VERIFICATION_SUBMIT_SELECTOR)
                    logger("✓ Verification submitted", level=level + 2)
                except Exception:
                    # Check if code was auto-submitted
                    current_url = self.page.evaluate("window.location.href")
                    logger(f"Current URL: {current_url}", level=level + 2)
                    if current_url != GITHUB_SIGNUP_URL:
                        logger("✓ Code auto-submitted", level=level + 2)
                    else:
                        raise Exception("✗ Code submission failed")

                time.sleep(20)
                logger("✓ Waited for account creation", level=level + 2)

                # Step 12: Set up 2FA
                if not self._setup_2fa(level=level + 1):
                    logger("✗ 2FA Setup failed", level=level + 1)
                else:
                    logger("✓ 2FA Setup completed", level=level + 1)

                logger("✓ Flow execution finished", level=level + 1)

                # Wait for user confirmation before closing
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
        """
        Execute the account creation flow with automatic retries.

        On failure, renews the Tor circuit and retries.

        Args:
            max_retries: Maximum number of retry attempts.
            level: Logging indentation level.

        Returns:
            True if account was created successfully, False otherwise.
        """
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
                        level=level + 1
                    )
                    renew_tor(level=level + 1)
                    time.sleep(random.uniform(5, 10))
                else:
                    logger(f"✗ Flow failed after {max_retries} attempts: {format_error(e)}", level=level + 1)

        return False


if __name__ == "__main__":
    generator = GithubTMailorGenerator(use_tor=True)
    generator.run_flow_with_retries(max_retries=1000)
