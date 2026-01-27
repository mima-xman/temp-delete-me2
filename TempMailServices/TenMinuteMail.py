"""
10MinuteMail temporary email service integration.

Website: https://10minutemail.com
Features: Tor support, retry logic, session expiry handling, Cloudflare bypass
"""

import time
from typing import Any, Dict, List, Optional

import cloudscraper
from fake_useragent import UserAgent

from config import TOR_CONTROL_PORT, TOR_PORT
from utils import format_error, logger, renew_tor, mask


class TenMinuteMail:
    """
    10MinuteMail temporary email service client.

    Provides temporary email addresses with optional Tor network support
    for enhanced privacy.

    Attributes:
        body_key: Key used to access HTML body in email responses.
        BASE_URL: 10MinuteMail website URL.
    """

    body_key = "bodyHtmlContent"
    BASE_URL = "https://10minutemail.com"

    def __init__(
        self,
        use_tor: bool = False,
        max_retries: int = 5
    ):
        """
        Initialize 10MinuteMail client.

        Args:
            use_tor: Route requests through Tor network.
            max_retries: Maximum retry attempts for failed requests.
        """
        self.ua = UserAgent()
        self.use_tor = use_tor
        self.max_retries = max_retries
        self.email: Optional[str] = None
        self.session: Optional[cloudscraper.CloudScraper] = None
        self.proxies: Optional[Dict[str, str]] = {}

        if self.use_tor:
            self.proxies = {
                'http': f'socks5://127.0.0.1:{TOR_PORT}',
                'https': f'socks5://127.0.0.1:{TOR_PORT}'
            }

        self._init_session()

    def _init_session(self) -> None:
        """Initialize HTTP session with appropriate headers and proxy settings."""
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'windows',
                'desktop': True
            },
            delay=10
        )
        
        if self.proxies:
            self.session.proxies = self.proxies

        # Visit homepage to establish session
        try:
            self.session.get(self.BASE_URL, timeout=30)
            time.sleep(2)
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
    ) -> Optional[Any]:
        """
        Make HTTP request with retry logic and error handling.

        Args:
            method: HTTP method ('GET' or 'POST').
            url: Request URL.
            timeout: Request timeout in seconds.
            level: Logging indentation level.

        Returns:
            Response object on success, None on failure.
        """
        for attempt in range(self.max_retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, timeout=timeout)
                else:
                    response = self.session.post(url, timeout=timeout)

                if response.status_code == 403:
                    logger("⚠ Cloudflare block detected", level=level)
                    if attempt < self.max_retries - 1:
                        time.sleep(3)
                        self._init_session()
                        continue
                    return None

                if not response.text or len(response.text.strip()) == 0:
                    continue

                response.raise_for_status()
                return response

            except Exception as e:
                logger(f"✗ Request failed: {format_error(e)}", level=level)
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger(f"⏳ Waiting {wait_time}s before retry...", level=level)
                    time.sleep(wait_time)

                    if self.use_tor:
                        logger(f"🔄 Renewing Tor IP... ({attempt + 1}/{self.max_retries})", level=level)
                        renewed, ip = renew_tor(level=level)

                    if attempt >= 1:
                        self._init_session()

        return None

    def _parse_json(self, response: Any, level: int = 0) -> Optional[Dict]:
        """
        Safely parse JSON response.

        Args:
            response: Response object.
            level: Logging indentation level.

        Returns:
            Parsed JSON dict or None.
        """
        if not response:
            return None

        try:
            return response.json()
        except Exception as e:
            logger(f"✗ Failed to parse JSON: {format_error(e)}", level=level)
            return None

    def generate_email(
        self,
        username: Optional[str] = None,
        level: int = 0
    ) -> Optional[Dict[str, str]]:
        """
        Generate a new temporary email address.

        Note: 10MinuteMail doesn't support custom usernames.

        Args:
            username: Ignored (kept for API compatibility).
            level: Logging indentation level.

        Returns:
            Dictionary with 'email' key, or None on failure.
        """
        logger("[######] Generating new email...", level=level)

        self._init_session()

        response = self._request('GET', f"{self.BASE_URL}/session/address", level=level + 1)

        if response:
            data = self._parse_json(response, level=level + 1)

            if data:
                self.email = data.get('address')

                if self.email:
                    logger(f"✅ Email: {mask(self.email, 4)}", level=level + 1)
                    return {'email': self.email}

        logger("✗ Failed to generate email", level=level + 1)
        return None

    def get_seconds_left(self, level: int = 0) -> Optional[int]:
        """
        Get remaining seconds until email expires.

        Args:
            level: Logging indentation level.

        Returns:
            Seconds remaining, or None on failure.
        """
        response = self._request('GET', f"{self.BASE_URL}/session/secondsLeft", level=level + 1)

        if response:
            data = self._parse_json(response, level=level + 1)
            if data:
                seconds = int(data.get('secondsLeft', 0))
                logger(f"⏱ Seconds left: {seconds}", level=level)
                return seconds

        return None

    def is_expired(self, level: int = 0) -> bool:
        """
        Check if the email session has expired.

        Args:
            level: Logging indentation level.

        Returns:
            True if expired, False otherwise.
        """
        response = self._request('GET', f"{self.BASE_URL}/session/expired", level=level + 1)

        if response:
            data = self._parse_json(response, level=level + 1)
            if data:
                return data.get('expired', True)

        return True

    def get_message_count(self, level: int = 0) -> int:
        """
        Get the number of messages in inbox.

        Args:
            level: Logging indentation level.

        Returns:
            Number of messages in inbox.
        """
        response = self._request('GET', f"{self.BASE_URL}/messages/messageCount", level=level + 1)

        if response:
            data = self._parse_json(response, level=level + 1)
            if data:
                return int(data.get('messageCount', 0))

        return 0

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

        count = self.get_message_count(level=level + 1)

        if count == 0:
            logger("📬 Found 0 emails", level=level)
            return {
                'email': self.email,
                'emails': [],
            }

        response = self._request('GET', f"{self.BASE_URL}/messages/messagesAfter/0", level=level + 1)

        if not response:
            return None

        try:
            messages = response.json()

            if not isinstance(messages, list):
                return None

            emails: List[Dict[str, Any]] = []

            for msg in messages:
                emails.append({
                    'id': msg.get('id'),
                    'from': msg.get('sender', msg.get('from', 'Unknown')),
                    'to': msg.get('recipient'),
                    'subject': msg.get('subject', 'No Subject'),
                    'received': msg.get('sentDateFormatted', msg.get('sentDate')),
                    'sentDate': msg.get('sentDate'),
                    'read': 1 if msg.get('read') else 0,
                    'preview': msg.get('bodyPreview', ''),
                    'bodyHtmlContent': msg.get('bodyHtmlContent', ''),
                    'bodyPlainText': msg.get('bodyPlainText', ''),
                    'body_html': msg.get('bodyHtmlContent', ''),
                    'body_text': msg.get('bodyPlainText', ''),
                    'attachments': msg.get('attachments', []),
                    'contentType': msg.get('contentType'),
                    'forwarded': msg.get('forwarded', False),
                    'repliedTo': msg.get('repliedTo', False),
                })

            logger(f"📬 Found {len(emails)} emails", level=level)
            return {
                'email': self.email,
                'emails': emails,
            }

        except Exception as e:
            logger(f"✗ Failed to parse inbox: {format_error(e)}", level=level + 1)
            return None

    def get_email(self, email_data: Any, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Retrieve full content of a specific email.

        Args:
            email_data: Email dictionary with 'id' key, or message ID string.
            level: Logging indentation level.

        Returns:
            Dictionary with email content, or None on failure.
        """
        msg_id = email_data.get('id') if isinstance(email_data, dict) else str(email_data)

        if not msg_id:
            logger("✗ No email id", level=level)
            return None

        if isinstance(email_data, dict) and email_data.get('bodyHtmlContent'):
            logger(f"📧 Retrieved email: {mask(str(msg_id), 4)}", level=level)
            return email_data

        inbox = self.get_inbox(level=level + 1)

        if inbox and inbox['emails']:
            for email in inbox['emails']:
                if str(email.get('id')) == str(msg_id):
                    logger(f"📧 Retrieved email: {mask(str(msg_id), 4)}", level=level)
                    return email

        logger(f"✗ Email not found: {mask(str(msg_id), 4)}", level=level)
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
            unread_only: Only return unread emails.
            level: Logging indentation level.

        Returns:
            First matching email in inbox, or None if timeout.
        """
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()

        while time.time() - start < timeout:
            if self.is_expired(level=level + 1):
                logger("⚠ Session expired!", level=level + 1)
                return None

            inbox = self.get_inbox(level=level + 1)

            if inbox and inbox['emails']:
                for email in inbox['emails']:
                    if not unread_only or not email.get('read'):
                        logger("✅ New email received!", level=level + 1)
                        return email

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
            if email.get('preview'):
                logger(f"Preview: {email['preview']}", level=level + 2)


if __name__ == "__main__":
    api = TenMinuteMail(use_tor=False)

    result = api.generate_email()
    if result:
        print(f"Email: {result['email']}")

        seconds = api.get_seconds_left()
        if seconds:
            print(f"Time remaining: {seconds}s")

        expired = api.is_expired()
        print(f"Expired: {expired}")

        email = api.wait_for_email(timeout=120)
        if email:
            full_email = api.get_email(email)
            if full_email:
                print(f"Subject: {full_email['subject']}")
                print(f"Body: {full_email['bodyHtmlContent']}")

        api.print_inbox()

    api.close()