"""
TMailor temporary email service integration.

Website: https://tmailor.com
Features: Cloudflare bypass via cloudscraper
"""

import time
from typing import Any, Dict, List, Optional

import cloudscraper

from config import TOR_PORT
from utils import format_error, logger


class TMailorAPI:
    """
    TMailor temporary email service client.

    Uses cloudscraper to bypass Cloudflare protection.

    Attributes:
        body_key: Key used to access body content in email responses.
    """

    body_key = "body"

    def __init__(
        self,
        access_token: Optional[str] = None,
        use_tor: bool = False
    ):
        """
        Initialize TMailor client.

        Args:
            access_token: Optional existing access token for session restoration.
            use_tor: Route requests through Tor network.
        """
        self.base_url = "https://tmailor.com"
        self.api_url = f"{self.base_url}/api"
        self.access_token = access_token
        self.email: Optional[str] = None

        self.proxies = {}
        if use_tor:
            self.proxies = {
                "http": f"socks5://127.0.0.1:{TOR_PORT}",
                "https": f"socks5://127.0.0.1:{TOR_PORT}"
            }

        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )

    def _request(
        self,
        action: str,
        level: int = 0,
        **params: Any
    ) -> Optional[Dict[str, Any]]:
        """
        Make API request to TMailor.

        Args:
            action: API action name.
            level: Logging indentation level.
            **params: Additional request parameters.

        Returns:
            JSON response as dictionary, or None on failure.
        """
        payload = {
            "action": action,
            "accesstoken": self.access_token or "",
            "fbToken": None,
            "curentToken": self.access_token or "",
            **params
        }

        headers = {
            "content-type": "application/json",
            "origin": self.base_url,
            "referer": f"{self.base_url}/"
        }

        try:
            response = self.scraper.post(
                self.api_url,
                json=payload,
                headers=headers,
                proxies=self.proxies
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger(f"✗ Error {response.status_code}: {response.text[:200]}", level=level)
                return None

        except Exception as e:
            logger(f"✗ Request failed: {format_error(e)}", level=level)
            return None

    def generate_email(self, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Generate a new temporary email address.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with 'email' and 'token' keys, or None on failure.
        """
        logger("[######] Generating new email...", level=level)
        data = self._request("newemail", level=level + 1)

        if data and data.get('msg') == 'ok':
            self.access_token = data['accesstoken']
            self.email = data['email']

            logger(f"✅ Email: {self.email}", level=level + 1)
            logger(f"✅ Token: {self.access_token[:50]}...", level=level + 1)

            return {
                'email': self.email,
                'token': self.access_token,
                'created': data.get('create')
            }

        logger(f"✗ Failed to generate email: {data}", level=level + 1)
        return None

    def get_inbox(self, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Retrieve all emails from the inbox.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with inbox data, or None on failure.
        """
        if not self.access_token:
            logger("✗ No access token", level=level)
            return None

        data = self._request("listinbox", level=level + 1)

        if data and data.get('msg') == 'ok':
            messages_data = data.get('data', {}) or {}
            emails: List[Dict[str, Any]] = list(messages_data.values())
            logger(f"📬 Found {len(emails)} emails", level=level)
            return {
                'email': data.get('email'),
                'code': data.get('code'),
                'emails': emails,
                'raw': data
            }

        return None

    def get_email(
        self,
        email_data: Dict[str, Any],
        level: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve full content of a specific email.

        Args:
            email_data: Email dictionary with 'id' and 'email_id' keys.
            level: Logging indentation level.

        Returns:
            Email content dictionary, or None on failure.
        """
        if not self.access_token:
            logger("✗ No access token", level=level)
            return None

        email_id = email_data.get('id')
        email_token = email_data.get('email_id')

        if not email_id:
            logger("✗ No email id", level=level)
            return None
        if not email_token:
            logger("✗ No email token", level=level)
            return None

        data = self._request(
            "read",
            email_code=email_id,
            email_token=email_token,
            level=level + 1
        )

        if data and data.get('msg') == 'ok':
            logger(f"📧 Retrieved email: {email_id}", level=level)
            return data.get('data')

        return None

    def wait_for_email(
        self,
        timeout: int = 60,
        interval: int = 3,
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
            First matching email, or None if timeout.
        """
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()

        while time.time() - start < timeout:
            inbox = self.get_inbox(level=level + 1)

            if inbox and inbox['emails']:
                if unread_only:
                    unread = [e for e in inbox['emails'] if e.get('read') == 0]
                    if unread:
                        logger("✅ New email received!", level=level + 1)
                        return unread[0]
                else:
                    logger("✅ Email found!", level=level + 1)
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
            status = "📖" if email.get('read') == 1 else "📩"
            logger(f"{status} Email #{i}", level=level + 1)
            logger(f"ID: {email['id']}", level=level + 2)
            logger(f"From: {email['sender_name']} <{email['sender_email']}>", level=level + 2)
            logger(f"Subject: {email['subject']}", level=level + 2)
            logger(
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(email['receive_time']))}",
                level=level + 2
            )
            logger(f"Read: {'Yes' if email.get('read') == 1 else 'No'}", level=level + 2)