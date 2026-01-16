"""
TempMailExtension temporary email service integration.

Website: https://temp-mail.org
Features: curl_cffi for Cloudflare bypass, Tor support
"""

import random
import time
from typing import Any, Dict, List, Optional

from curl_cffi import requests

from config import TOR_PORT
from utils import format_error, logger


class TempMailExtensionAPI:
    """
    TempMail Extension API client.

    Uses curl_cffi to bypass Cloudflare protection.

    Attributes:
        body_key: Key used to access HTML body in email responses.
    """

    body_key = "bodyHtml"

    def __init__(
        self,
        token: Optional[str] = None,
        use_tor: bool = False
    ):
        """
        Initialize TempMailExtension client.

        Args:
            token: Optional existing token for session restoration.
            use_tor: Route requests through Tor network.
        """
        self.base_url = "https://web2.temp-mail.org"
        self.token = token
        self.email: Optional[str] = None
        self.session = requests.Session()
        self.use_tor = use_tor
        self.proxies = {}

        if use_tor:
            self.proxies = {
                "http": f"socks5://127.0.0.1:{TOR_PORT}",
                "https": f"socks5://127.0.0.1:{TOR_PORT}"
            }

    def _get_headers(self) -> Dict[str, str]:
        """
        Get request headers with authorization.

        Returns:
            Headers dictionary.
        """
        headers = {
            "accept": "*/*",
            "content-type": "application/json",
            "origin": "https://temp-mail.org",
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site"
        }
        if self.token:
            headers["authorization"] = f"Bearer {self.token}"
        return headers

    def _request_with_retry(
        self,
        method: str,
        url: str,
        max_retries: int = 3,
        **kwargs: Any
    ) -> Optional[requests.Response]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method ('GET' or 'POST').
            url: Request URL.
            max_retries: Maximum retry attempts.
            **kwargs: Additional request arguments.

        Returns:
            Response object on success, None on failure.
        """
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = self.session.get(url, **kwargs)
                else:
                    response = self.session.post(url, **kwargs)

                if response.status_code == 200:
                    return response

                # Rate limit - wait and retry
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 5
                    logger(f"⚠ Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue

                # Cloudflare block - wait longer
                if response.status_code == 403:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        logger(f"⚠ Blocked (403). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    return response

                return response

            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger(f"⚠ Request error: {str(e)[:50]}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise

        return None

    def generate_email(self, level: int = 0) -> Optional[Dict[str, str]]:
        """
        Generate a new temporary email address.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with 'email' and 'token' keys, or None on failure.
        """
        try:
            # Random delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))

            response = self._request_with_retry(
                "POST",
                f"{self.base_url}/mailbox",
                headers=self._get_headers(),
                proxies=self.proxies,
                timeout=15
            )

            if response and response.status_code == 200:
                data = response.json()
                self.token = data['token']
                self.email = data['mailbox']

                logger(f"✅ Email: {self.email}", level=level)
                logger(f"✅ Token: {self.token[:50]}...", level=level)

                return {
                    'email': self.email,
                    'token': self.token
                }
            elif response:
                logger(f"✗ Error {response.status_code}: {response.text[:200]}", level=level)
                return None
            else:
                logger("✗ Failed after retries", level=level)
                return None

        except Exception as e:
            logger(f"✗ Request failed: {format_error(e)}", level=level)
            return None

    def get_inbox(self, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Retrieve all emails from the inbox.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with inbox data, or None on failure.
        """
        if not self.token:
            logger("✗ No token", level=level)
            return None

        try:
            response = self._request_with_retry(
                "GET",
                f"{self.base_url}/messages",
                headers=self._get_headers(),
                impersonate="chrome110",
                proxies=self.proxies,
                timeout=15
            )

            if response and response.status_code == 200:
                data = response.json()
                messages: List[Dict[str, Any]] = data.get('messages', [])
                logger(f"📬 Found {len(messages)} emails", level=level)
                return {
                    'email': data.get('mailbox'),
                    'messages': messages
                }
            elif response:
                logger(f"✗ Error {response.status_code}: {response.text[:200]}", level=level)
                return None
            else:
                return None

        except Exception as e:
            logger(f"✗ Request failed: {format_error(e)}", level=level)
            return None

    def get_email(
        self,
        message_data: Dict[str, Any],
        level: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve full content of a specific email.

        Args:
            message_data: Message dictionary with '_id' key.
            level: Logging indentation level.

        Returns:
            Email content dictionary, or None on failure.
        """
        if not self.token:
            logger("✗ No token", level=level)
            return None

        message_id = message_data.get('_id')
        if not message_id:
            logger("✗ No message id", level=level)
            return None

        try:
            response = self._request_with_retry(
                "GET",
                f"{self.base_url}/messages/{message_id}",
                headers=self._get_headers(),
                impersonate="chrome110",
                proxies=self.proxies,
                timeout=15
            )

            if response and response.status_code == 200:
                data = response.json()
                logger(f"📧 Retrieved email: {message_id}", level=level)
                return data
            elif response:
                logger(f"✗ Error {response.status_code}: {response.text[:200]}", level=level)
                return None
            else:
                return None

        except Exception as e:
            logger(f"✗ Request failed: {format_error(e)}", level=level)
            return None

    def wait_for_email(
        self,
        timeout: int = 60,
        interval: int = 5,
        level: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for a new email to arrive in the inbox.

        Args:
            timeout: Maximum wait time in seconds.
            interval: Poll interval in seconds.
            level: Logging indentation level.

        Returns:
            First email in inbox, or None if timeout.
        """
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()

        while time.time() - start < timeout:
            inbox = self.get_inbox(level=level + 1)

            if inbox and inbox['messages']:
                logger("✅ Email received!", level=level)
                return inbox['messages'][0]

            elapsed = int(time.time() - start)
            logger(f"⏳ Waiting... ({elapsed}/{timeout}s)", level=level)
            time.sleep(interval)

        logger("⏰ Timeout - no email received", level=level)
        return None

    def print_inbox(self, level: int = 0) -> None:
        """
        Print formatted inbox contents.

        Args:
            level: Logging indentation level.
        """
        inbox = self.get_inbox(level=level)

        if not inbox or not inbox['messages']:
            logger("📭 Inbox is empty", level=level)
            return

        logger(f"📬 Inbox for: {inbox['email']}", level=level)

        for i, msg in enumerate(inbox['messages'], 1):
            logger(f"📩 Email #{i}", level=level + 1)
            logger(f"ID: {msg['_id']}", level=level + 2)
            logger(f"From: {msg['from']}", level=level + 2)
            logger(f"Subject: {msg['subject']}", level=level + 2)
            logger(f"Preview: {msg['bodyPreview']}", level=level + 2)
            logger(
                f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(msg['receivedAt']))}",
                level=level + 2
            )
            logger(f"Attachments: {msg['attachmentsCount']}", level=level + 2)

    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()


if __name__ == "__main__":
    api = TempMailExtensionAPI(token=None, use_tor=False)

    try:
        result = api.generate_email()

        if result:
            print(f"\n📧 Your temporary email: {api.email}")
            api.print_inbox()

            new_email = api.wait_for_email(timeout=120)
            if new_email:
                content = api.get_email(new_email)
                if content:
                    print(f"\nFrom: {content['from']}")
                    print(f"Subject: {content['subject']}")
                    print(f"\nHTML Body:\n{content['bodyHtml']}")
    finally:
        api.close()