"""
TempMail.io temporary email service integration.

Website: https://temp-mail.io
Features: Custom email names, domain selection
"""

import time
from typing import Any, Dict, List, Optional

import requests

from config import TOR_PORT
from utils import format_error, logger, mask, renew_tor


class TempMailIO:
    """
    TempMail.io API client.

    Provides temporary email with custom name and domain selection.

    Attributes:
        body_key: Key used to access HTML body in email responses.
    """

    body_key = "body_html"

    def __init__(self, use_tor: bool = True, max_retries: int = 5):
        """
        Initialize TempMail.io client.

        Args:
            use_tor: Route requests through Tor network.
            max_retries: Maximum retry attempts.
        """
        self.base_url = "https://temp-mail.io"
        self.api_url = "https://api.internal.temp-mail.io/api/v3"
        self.api_url_v4 = "https://api.internal.temp-mail.io/api/v4"
        self.email: Optional[str] = None
        self.token: Optional[str] = None
        self.max_retries = max_retries
        self.use_tor = use_tor
        self.session = requests.Session()

        self.proxies = {}
        if use_tor:
            self.proxies = {
                "http": f"socks5://127.0.0.1:{TOR_PORT}",
                "https": f"socks5://127.0.0.1:{TOR_PORT}"
            }

        # Set default headers
        self.session.headers.update({
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br',
            'accept-language': 'en-US,en;q=0.9',
            'application-name': 'web',
            'application-version': '4.0.0',
            'content-type': 'application/json',
            'origin': self.base_url,
            'referer': f'{self.base_url}/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'x-cors-header': 'iaWg3pchvFx48fY'
        })

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
        endpoint: str,
        level: int = 0,
        **kwargs: Any
    ) -> Optional[Any]:
        """
        Make API request.

        Args:
            method: HTTP method.
            endpoint: API endpoint or full URL.
            level: Logging indentation level.
            **kwargs: Additional request arguments.

        Returns:
            JSON response, or None on failure.
        """
        try:
            url = endpoint if endpoint.startswith('http') else f"{self.api_url}{endpoint}"
            
            for attempt in range(self.max_retries):
                try:
                    response = self.session.request(method, url, proxies=self.proxies, **kwargs)

                    if response.ok:
                        return response.json()
                    
                    logger(f"✗ Error {response.status_code}: {response.text[:200]}", level=level)

                    # Handle rate limits or errors
                    if self.use_tor and attempt < self.max_retries - 1:
                        logger(f"⚠ Request failed. Renewing Tor IP... ({attempt + 1}/{self.max_retries})", level=level)
                        renewed, ip = renew_tor(level=level)
                        continue

                except Exception as e:
                    logger(f"✗ Request failed: {format_error(e)}", level=level)
                    if attempt < self.max_retries - 1:
                        wait_time = (attempt + 1) * 2
                        logger(f"⏳ Waiting {wait_time}s before retry...", level=level)
                        time.sleep(wait_time)

                        if self.use_tor:
                            logger(f"🔄 Renewing Tor IP... ({attempt + 1}/{self.max_retries})", level=level)
                            renewed, ip = renew_tor(level=level)
            
            return None

        except Exception as e:
            logger(f"✗ Fatal error: {format_error(e)}", level=level)
            return None

    def get_domains(self, level: int = 0) -> Optional[List[Dict[str, Any]]]:
        """
        Get available email domains.

        Args:
            level: Logging indentation level.

        Returns:
            List of domain dictionaries, or None on failure.
        """
        logger("[######] Getting available domains...", level=level)
        data = self._request("GET", f"{self.api_url_v4}/domains", level=level + 1)

        if data and 'domains' in data:
            domains = data['domains']
            logger(f"✅ Found {len(domains)} domains", level=level + 1)
            return domains

        logger(f"✗ Failed to get domains: {data}", level=level + 1)
        return None

    def generate_email(
        self,
        min_length: int = 10,
        max_length: int = 10,
        custom_name: Optional[str] = None,
        level: int = 0
    ) -> Optional[Dict[str, str]]:
        """
        Generate a new temporary email with random name.

        Args:
            min_length: Minimum name length.
            max_length: Maximum name length.
            custom_name: Optional custom name (uses generate_custom_email).
            level: Logging indentation level.

        Returns:
            Dictionary with 'email' and 'token' keys, or None on failure.
        """
        if custom_name:
            return self.generate_custom_email(custom_name, level=level)

        logger("[######] Generating new email...", level=level)

        payload = {
            "min_name_length": min_length,
            "max_name_length": max_length
        }

        data = self._request(
            "POST",
            "/email/new",
            level=level + 1,
            json=payload
        )

        if data and 'email' in data and 'token' in data:
            self.email = data['email']
            self.token = data['token']

            logger(f"✅ Email: {mask(self.email, 4)}", level=level + 1)
            logger(f"✅ Token: {mask(self.token, 4)}", level=level + 1)

            return {
                'email': self.email,
                'token': self.token
            }

        logger(f"✗ Failed to generate email: {data}", level=level + 1)
        return None

    def generate_custom_email(
        self,
        name: str,
        domain: Optional[str] = None,
        level: int = 0
    ) -> Optional[Dict[str, str]]:
        """
        Generate a new temporary email with custom name and domain.

        Args:
            name: Custom email name.
            domain: Optional domain (uses first available if not specified).
            level: Logging indentation level.

        Returns:
            Dictionary with 'email' and 'token' keys, or None on failure.
        """
        logger("[######] Generating custom email...", level=level)

        if not domain:
            domains = self.get_domains(level=level + 1)
            if not domains:
                logger("✗ Failed to get domains", level=level + 1)
                return None
            domain = domains[0]['name']
            logger(f"📝 Using domain: {domain}", level=level + 1)

        payload = {
            "name": name,
            "domain": domain
        }

        data = self._request(
            "POST",
            "/email/new",
            level=level + 1,
            json=payload
        )

        if data and 'email' in data and 'token' in data:
            self.email = data['email']
            self.token = data['token']

            logger(f"✅ Email: {mask(self.email, 4)}", level=level + 1)
            logger(f"✅ Token: {mask(self.token, 4)}", level=level + 1)

            return {
                'email': self.email,
                'token': self.token
            }

        logger(f"✗ Failed to generate custom email: {data}", level=level + 1)
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

        data = self._request(
            "GET",
            f"/email/{self.email}/messages",
            level=level + 1
        )

        if data is not None:
            emails: List[Dict[str, Any]] = data if isinstance(data, list) else []
            logger(f"📬 Found {len(emails)} emails", level=level)
            return {
                'email': self.email,
                'token': self.token,
                'emails': emails,
                'raw': data
            }

        return None

    def get_email(
        self,
        email_data: Any,
        level: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve full content of a specific email.

        Args:
            email_data: Email dictionary with 'id' key, or message ID string.
            level: Logging indentation level.

        Returns:
            Email content dictionary, or None on failure.
        """
        email_id = email_data.get('id') if isinstance(email_data, dict) else email_data

        if not email_id:
            logger("✗ No email id", level=level)
            return None

        data = self._request(
            "GET",
            f"/message/{email_id}",
            level=level + 1
        )

        if data and 'id' in data:
            logger(f"📧 Retrieved email: {mask(email_id, 4)}", level=level)
            return data

        return None

    def wait_for_email(
        self,
        timeout: int = 60,
        interval: int = 3,
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
            logger(f"To: {email['to']}", level=level + 2)
            logger(f"Subject: {email['subject']}", level=level + 2)
            logger(f"Time: {email['created_at']}", level=level + 2)
            if email.get('cc'):
                logger(f"CC: {email['cc']}", level=level + 2)
            if email.get('attachments'):
                logger(f"Attachments: {len(email['attachments'])}", level=level + 2)