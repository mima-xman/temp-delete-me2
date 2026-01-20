"""
Mail.tm temporary email service integration. (internxt.com)

Website: https://mail.tm
API: https://api.mail.tm
Features: Tor support, retry logic, JWT authentication
"""

import random
import string
import time
from typing import Any, Dict, List, Optional

import requests
from fake_useragent import UserAgent

from config import TOR_CONTROL_PORT, TOR_PORT
from utils import format_error, logger, renew_tor, mask


class MailTM:
    """
    Mail.tm temporary email service client.

    Provides temporary email addresses with optional Tor network support
    for enhanced privacy.

    Attributes:
        body_key: Key used to access HTML body in email responses.
        BASE_URL: Mail.tm API URL.
    """

    body_key = "body_html"
    BASE_URL = "https://api.mail.tm"

    def __init__(
        self,
        use_tor: bool = False,
        max_retries: int = 5
    ):
        """
        Initialize Mail.tm client.

        Args:
            use_tor: Route requests through Tor network.
            max_retries: Maximum retry attempts for failed requests.
        """
        self.ua = UserAgent()
        self.use_tor = use_tor
        self.max_retries = max_retries
        self.email: Optional[str] = None
        self.password: Optional[str] = None
        self.token: Optional[str] = None
        self.account_id: Optional[str] = None
        self.session: Optional[requests.Session] = None
        self.proxies: Optional[Dict[str, str]] = {}

        if self.use_tor:
            self.proxies = {
                'http': f'socks5://127.0.0.1:{TOR_PORT}',
                'https': f'socks5://127.0.0.1:{TOR_PORT}'
            }

        self._init_session()

    def _init_session(self) -> None:
        """Initialize HTTP session with appropriate headers and proxy settings."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'application/json',
            'Content-Type': 'application/json',
        })
        self.session.proxies = self.proxies

    def close(self) -> None:
        """Close the HTTP session."""
        if self.session:
            try:
                self.session.close()
            except Exception:
                pass

    def _generate_random_string(self, length: int = 8) -> str:
        """
        Generate a random alphanumeric string.

        Args:
            length: Length of the string to generate.

        Returns:
            Random string of specified length.
        """
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def _request(
        self,
        method: str,
        url: str,
        json_data: Optional[Dict] = None,
        timeout: int = 60,
        level: int = 0,
        use_auth: bool = False
    ) -> Optional[Any]:
        """
        Make HTTP request with retry logic and error handling.

        Args:
            method: HTTP method ('GET' or 'POST').
            url: Request URL.
            json_data: JSON payload for POST requests.
            timeout: Request timeout in seconds.
            level: Logging indentation level.
            use_auth: Include Authorization header with Bearer token.

        Returns:
            JSON response on success, None on failure.
        """
        headers = {}
        if use_auth and self.token:
            headers['Authorization'] = f'Bearer {self.token}'

        for attempt in range(self.max_retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, headers=headers, timeout=timeout)
                else:
                    response = self.session.post(url, json=json_data, headers=headers, timeout=timeout)

                # Handle successful responses
                if response.status_code in (200, 201):
                    return response.json()

                # Handle authentication errors
                if response.status_code == 401:
                    error_msg = response.json().get('message', 'Unknown error')
                    logger(f"✗ Authentication failed: {error_msg}", level=level)
                    return None

                # Handle validation errors
                if response.status_code == 422:
                    error_detail = response.json().get('detail', 'Validation error')
                    logger(f"✗ Validation error: {error_detail}", level=level)
                    return None

                # Handle rate limiting
                if response.status_code == 429:
                    if self.use_tor and attempt < self.max_retries - 1:
                        logger(f"⚠ Rate limit hit. Renewing Tor IP... ({attempt + 1}/{self.max_retries})", level=level)
                        renewed, ip = renew_tor(level=level)
                        if renewed:
                            self._init_session()
                            continue
                    return None

                # Handle other errors
                response.raise_for_status()

            except requests.exceptions.RequestException as e:
                logger(f"✗ Request failed: {format_error(e)}", level=level)
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    logger(f"⏳ Waiting {wait_time}s before retry...", level=level)
                    time.sleep(wait_time)

                    if self.use_tor:
                        logger(f"🔄 Renewing Tor IP... ({attempt + 1}/{self.max_retries})", level=level)
                        renewed, ip = renew_tor(level=level)
                        if renewed:
                            self._init_session()

        return None

    def _get_domains(self, level: int = 0) -> Optional[List[Dict[str, Any]]]:
        """
        Get available email domains.

        Args:
            level: Logging indentation level.

        Returns:
            List of active domain dictionaries, or None on failure.
        """
        response = self._request('GET', f"{self.BASE_URL}/domains", level=level)

        if response and isinstance(response, list):
            active_domains = [d for d in response if d.get('isActive', False)]
            return active_domains

        return None

    def _create_account(
        self,
        address: str,
        password: str,
        level: int = 0
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new email account.

        Args:
            address: Full email address.
            password: Account password.
            level: Logging indentation level.

        Returns:
            Account data dictionary, or None on failure.
        """
        payload = {
            "address": address,
            "password": password
        }

        return self._request(
            'POST',
            f"{self.BASE_URL}/accounts",
            json_data=payload,
            level=level
        )

    def _get_token(
        self,
        address: str,
        password: str,
        level: int = 0
    ) -> Optional[str]:
        """
        Get authentication token for the account.

        Args:
            address: Full email address.
            password: Account password.
            level: Logging indentation level.

        Returns:
            JWT token string, or None on failure.
        """
        payload = {
            "address": address,
            "password": password
        }

        response = self._request(
            'POST',
            f"{self.BASE_URL}/token",
            json_data=payload,
            level=level
        )

        if response and 'token' in response:
            return response['token']

        return None

    def generate_email(
        self,
        username: Optional[str] = None,
        level: int = 0
    ) -> Optional[Dict[str, str]]:
        """
        Generate a new temporary email address.

        Args:
            username: Optional custom name.
            level: Logging indentation level.

        Returns:
            Dictionary with 'email', 'password', and 'token' keys, or None on failure.
        """
        logger("[######] Generating new email...", level=level)

        # Get available domains
        domains = self._get_domains(level=level + 1)
        if not domains:
            logger("✗ Failed to get available domains", level=level + 1)
            return None

        domain = domains[0]['domain']
        logger(f"✅ Using domain: {domain}", level=level + 1)

        # Generate username and password
        if not username:
            username = self._generate_random_string(10)
        password = self._generate_random_string(12)
        address = f"{username}@{domain}"

        # Create account
        account = self._create_account(address, password, level=level + 1)
        if not account:
            logger("✗ Failed to create account", level=level + 1)
            return None

        self.account_id = account.get('id')
        logger(f"✅ Account created: {mask(address, 4)}", level=level + 1)

        # Get authentication token
        token = self._get_token(address, password, level=level + 1)
        if not token:
            logger("✗ Failed to get authentication token", level=level + 1)
            return None

        self.email = address
        self.password = password
        self.token = token

        logger(f"✅ Email: {mask(self.email, 4)}", level=level + 1)
        logger(f"✅ Token: {mask(self.token, 10)}", level=level + 1)

        return {
            'email': self.email,
            'token': self.password
        }

    def get_inbox(self, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Retrieve all emails from the inbox.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with inbox data, or None on failure.
        """
        if not self.email or not self.token:
            logger("✗ No email address or token", level=level)
            return None

        response = self._request(
            'GET',
            f"{self.BASE_URL}/messages",
            level=level + 1,
            use_auth=True
        )

        if response is None:
            return None

        emails: List[Dict[str, Any]] = []

        if isinstance(response, list):
            for msg in response:
                from_data = msg.get('from', {})
                emails.append({
                    'id': msg.get('id'),
                    'from': from_data.get('address', 'Unknown'),
                    'from_name': from_data.get('name', ''),
                    'subject': msg.get('subject', 'No Subject'),
                    'intro': msg.get('intro', ''),
                    'seen': msg.get('seen', False),
                    'has_attachments': msg.get('hasAttachments', False),
                    'created_at': msg.get('createdAt', ''),
                    'read': 1 if msg.get('seen', False) else 0
                })

        logger(f"📬 Found {len(emails)} emails", level=level)
        return {
            'email': self.email,
            'token': self.token,
            'emails': emails,
            'raw': response
        }

    def get_email(self, email_data: Any, level: int = 0) -> Optional[Dict[str, Any]]:
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

        if not self.token:
            logger("✗ No authentication token", level=level)
            return None

        response = self._request(
            'GET',
            f"{self.BASE_URL}/messages/{msg_id}",
            level=level + 1,
            use_auth=True
        )

        if response:
            # Handle html field which is an array
            html_content = response.get('html', [])
            if isinstance(html_content, list):
                html_content = ''.join(html_content)

            from_data = response.get('from', {})

            logger(f"📧 Retrieved email: {mask(msg_id, 4)}", level=level)
            return {
                'id': msg_id,
                'from': from_data.get('address', 'Unknown'),
                'from_name': from_data.get('name', ''),
                'to': response.get('to', []),
                'cc': response.get('cc', []),
                'bcc': response.get('bcc', []),
                'subject': response.get('subject', 'No Subject'),
                'body_html': html_content,
                'body_text': response.get('text', ''),
                'seen': response.get('seen', False),
                'has_attachments': response.get('hasAttachments', False),
                'created_at': response.get('createdAt', ''),
                'download_url': response.get('downloadUrl', ''),
                'raw': response
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
            unread_only: Only return unread emails.
            level: Logging indentation level.

        Returns:
            First matching email in inbox, or None if timeout.
        """
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()

        while time.time() - start < timeout:
            inbox = self.get_inbox(level=level + 1)

            if inbox and inbox['emails']:
                if unread_only:
                    unread = [e for e in inbox['emails'] if not e.get('seen', False)]
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
            logger(f"📩 Email #{i}", level=level + 1)
            logger(f"ID: {email['id']}", level=level + 2)
            logger(f"From: {email['from']}", level=level + 2)
            logger(f"Subject: {email['subject']}", level=level + 2)
            logger(f"Preview: {email['intro'][:50]}..." if email['intro'] else "Preview: N/A", level=level + 2)
            logger(f"Seen: {email['seen']}", level=level + 2)
            logger(f"Date: {email['created_at']}", level=level + 2)


if __name__ == "__main__":
    api = MailTM(use_tor=False)

    result = api.generate_email()
    if result:
        print(f"Email: {result['email']}")
        print(f"Password: {result['password']}")

        email = api.wait_for_email(timeout=120)
        if email:
            full_email = api.get_email(email['id'])
            if full_email:
                print(full_email['body_html'])

        api.print_inbox()

    api.close()