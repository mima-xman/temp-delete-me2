"""
Configuration constants for the GitHub account generator project.

This module contains all configuration settings for GitHub account generation,
browser settings, and output paths.
"""

import os
from typing import Dict, List

# ==============================================================================
# Tor Network Settings
# ==============================================================================

# Tor SOCKS proxy port (9150 for Tor Browser, 9050 for system Tor)
TOR_PORT: int = int(os.getenv("TOR_PORT", 9150))

# Tor control port for circuit renewal (9151 for Tor Browser, 9051 for system Tor)
TOR_CONTROL_PORT: int = int(os.getenv("TOR_CONTROL_PORT", 9151))

# ==============================================================================
# Account Generation Settings
# ==============================================================================

FIRST_NAMES: List[str] = [
    "Liam", "Emma", "Noah", "Olivia", "William", "Ava",
    "James", "Isabella", "Oliver", "Sophia", "Benjamin", "Mia"
]

LAST_NAMES: List[str] = [
    "Anderson", "Taylor", "Thomas", "Moore", "Jackson",
    "White", "Harris", "Martin", "Thompson", "Young"
]

# Username suffix appended to generated usernames
USERNAME_SUFFIX: str = "miamore"

# Maximum wait time for verification code (in seconds)
MAX_WAIT_TIME_FOR_VERIFICATION_CODE: int = 120

# Maximum retries for account creation
MAX_RETRIES_FOR_ACCOUNT_CREATION: int = 3

# ==============================================================================
# Browser Settings
# ==============================================================================

# Browser viewport dimensions
VIEWPORT: Dict[str, int] = {'width': 1024, 'height': 768}

# Browser locale for internationalization
LOCALE: str = 'fr-FR'

# User agent string for browser requests
USER_AGENT: str = (
    'Mozilla/5.0 (Linux; Android 12; SM-G975F Build/QP1A.190711.002; wv) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/120.0.0.0 '
    'Mobile Safari/537.36'
)

# Run browser in headless mode
HEADLESS: bool = False

# Browser launch arguments for anti-detection
ARGS: List[str] = [
    '--disable-blink-features=AutomationControlled',
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-infobars',
    '--ignore-certificate-errors',
    f'--user-agent={USER_AGENT}'
]

# Browser executable paths
BRAVE_PATH: str = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
CHROME_PATH: str = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

# ==============================================================================
# Output Settings
# ==============================================================================

OUTPUT_DIR: str = "output"