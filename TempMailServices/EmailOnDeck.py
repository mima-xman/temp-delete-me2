"""
EmailOnDeck temporary email service integration.

Website: https://www.emailondeck.com
Features: Tor support, retry logic, rate limit handling
"""

import re
import time
from typing import Any, Dict, List, Optional

import requests
from fake_useragent import UserAgent

from config import TOR_CONTROL_PORT, TOR_PORT
from utils import format_error, logger, renew_tor


class EmailOnDeck:
    """
    EmailOnDeck temporary email service client.

    Provides temporary email addresses with optional Tor network support
    for enhanced privacy.

    Attributes:
        body_key: Key used to access HTML body in email responses.
        BASE_URL: EmailOnDeck website URL.
    """

    body_key = "body_html"
    BASE_URL = "https://www.emailondeck.com"

    def __init__(
        self,
        use_tor: bool = False,
        max_retries: int = 5
    ):
        """
        Initialize EmailOnDeck client.

        Args:
            use_tor: Route requests through Tor network.
            max_retries: Maximum retry attempts for failed requests.
        """
        self.ua = UserAgent()
        self.use_tor = use_tor
        self.max_retries = max_retries
        self.email: Optional[str] = None
        self.token: Optional[str] = None
        self.session: Optional[requests.Session] = None
        self.proxies: Optional[Dict[str, str]] = {}

        if self.use_tor:
            self.proxies = {
                'http': f'socks5://127.0.0.1:{TOR_PORT}',
                'https': f'socks5://127.0.0.1:{TOR_PORT}'
            }

        logger("🚀 Initializing EmailOnDeck...", level=0)
        self._init_session()
        logger("✅ API ready", level=0)

    def _init_session(self) -> None:
        """Initialize HTTP session with appropriate headers and proxy settings."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        self.session.proxies = self.proxies

        # Visit homepage to establish session cookies
        try:
            self.session.get(self.BASE_URL, timeout=30)
            time.sleep(1)
        except Exception:
            pass

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass

    def _request(
        self,
        method: str,
        url: str,
        timeout: int = 60,
        level: int = 0
    ) -> Optional[str]:
        """
        Make HTTP request with retry logic and rate limit handling.

        Args:
            method: HTTP method ('GET' or 'POST').
            url: Request URL.
            timeout: Request timeout in seconds.
            level: Logging indentation level.

        Returns:
            Response text on success, None on failure.
        """
        for attempt in range(self.max_retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, timeout=timeout)
                else:
                    response = self.session.post(url, timeout=timeout)

                response.raise_for_status()
                text = response.text.strip()

                # Handle rate limit responses
                if "Too many" in text or text.startswith("err:"):
                    if self.use_tor and attempt < self.max_retries - 1:
                        logger(f"⚠ Rate limit hit. Renewing Tor IP... ({attempt + 1}/{self.max_retries})", level=level)
                        if renew_tor(level=level):
                            self._init_session()
                            continue
                    return None

                return text

            except Exception as e:
                logger(f"✗ Request failed: {format_error(e)}", level=level)
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger(f"⏳ Waiting {wait_time}s before retry...", level=level)
                    time.sleep(wait_time)

                    if self.use_tor:
                        logger(f"🔄 Renewing Tor IP... ({attempt + 1}/{self.max_retries})", level=level)
                        if renew_tor(level=level):
                            self._init_session()

        return None

    def generate_email(self, level: int = 0) -> Optional[Dict[str, str]]:
        """
        Generate a new temporary email address.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with 'email' and 'token' keys, or None on failure.
        """
        logger("[######] Generating new email...", level=level)

        text = self._request('GET', f"{self.BASE_URL}/ajax/ce-new-email.php", level=level + 1)

        if text and '|' in text:
            parts = text.split('|')
            self.email = parts[0]
            self.token = parts[1]

            logger(f"✅ Email: {self.email}", level=level + 1)
            logger(f"✅ Token: {self.token}", level=level + 1)

            return {
                'email': self.email,
                'token': self.token
            }

        logger(f"✗ Failed to generate email: {text}", level=level + 1)
        return None

    def get_inbox(self, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Retrieve all emails from the inbox.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with inbox data, or None on failure.
        """
        if not self.email:
            logger("✗ No email address", level=level)
            return None

        text = self._request('POST', f"{self.BASE_URL}/ajax/messages.php", level=level + 1)

        if not text:
            return None

        if "No emails received yet" in text:
            logger("📬 Found 0 emails", level=level)
            return {
                'email': self.email,
                'token': self.token,
                'emails': [],
                'raw': text
            }

        emails: List[Dict[str, Any]] = []

        # Parse message IDs from HTML
        msg_ids = re.findall(r"<div class='inbox_rows msglink' name=(\d+)>", text)
        blocks = re.split(r"<div class='inbox_rows msglink' name=\d+>", text)[1:]

        for i, block in enumerate(blocks):
            if i >= len(msg_ids):
                break

            sender_match = re.search(r"<td[^>]*inbox_td_from[^>]*>([^<]+)</td>", block)
            subject_match = re.search(r"<td[^>]*inbox_td_subject[^>]*>([^<]+)</td>", block)
            received_match = re.search(r"<td[^>]*inbox_td_received[^>]*>([^<]+)</td>", block)

            emails.append({
                'id': msg_ids[i],
                'from': sender_match.group(1).strip() if sender_match else "Unknown",
                'subject': subject_match.group(1).strip() if subject_match else "No Subject",
                'received': received_match.group(1).strip() if received_match else "Unknown",
                'read': 0
            })

        logger(f"📬 Found {len(emails)} emails", level=level)
        return {
            'email': self.email,
            'token': self.token,
            'emails': emails,
            'raw': text
        }

    def get_email(self, email_data: Any, level: int = 0) -> Optional[Dict[str, str]]:
        """
        Retrieve full content of a specific email.

        Args:
            email_data: Email dictionary with 'id' key, or message ID string.
            level: Logging indentation level.

        Returns:
            Dictionary with email content, or None on failure.
        """
        msg_id = email_data.get('id') if isinstance(email_data, dict) else email_data

        if not msg_id:
            logger("✗ No email id", level=level)
            return None

        content = self._request(
            'GET',
            f"{self.BASE_URL}/email_iframe.php?msg_id={msg_id}",
            level=level + 1
        )

        if content:
            logger(f"📧 Retrieved email: {msg_id}", level=level)
            return {
                'id': msg_id,
                'body_html': content,
                'body_text': re.sub(r'<[^>]+>', '', content)
            }

        return None

    def wait_for_email(
        self,
        timeout: int = 60,
        interval: int = 5,
        unread_only: bool = True,
        level: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for a new email to arrive in the inbox.

        Args:
            timeout: Maximum wait time in seconds.
            interval: Poll interval in seconds.
            unread_only: Only return unread emails (not used, kept for API compatibility).
            level: Logging indentation level.

        Returns:
            First email in inbox, or None if timeout.
        """
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()

        while time.time() - start < timeout:
            inbox = self.get_inbox(level=level + 1)

            if inbox and inbox['emails']:
                logger("✅ New email received!", level=level + 1)
                return inbox['emails'][0]

            elapsed = int(time.time() - start)
            logger(f"⏳ Waiting... ({elapsed}/{timeout}s)", level=level + 1)
            time.sleep(interval)

        logger("⏰ Timeout - no email received", level=level + 1)
        return None

    def print_inbox(self, level: int = 0) -> None:
        """
        Print formatted inbox contents.

        Args:
            level: Logging indentation level.
        """
        inbox = self.get_inbox(level=level)

        if not inbox or not inbox['emails']:
            logger("📭 Inbox is empty", level=level)
            return

        logger(f"📬 Inbox for: {inbox['email']}", level=level)

        for i, email in enumerate(inbox['emails'], 1):
            logger(f"📩 Email #{i}", level=level + 1)
            logger(f"ID: {email['id']}", level=level + 2)
            logger(f"From: {email['from']}", level=level + 2)
            logger(f"Subject: {email['subject']}", level=level + 2)
            logger(f"Received: {email['received']}", level=level + 2)


if __name__ == "__main__":
    api = EmailOnDeck(use_tor=False)

    result = api.generate_email()
    if result:
        print(f"Email: {result['email']}")

        email = api.wait_for_email(timeout=120)
        if email:
            full_email = api.get_email(email['id'])
            if full_email:
                print(full_email['body_html'])

        api.print_inbox()

    api.close()