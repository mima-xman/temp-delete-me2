"""
SmailPro temporary email service integration.

Website: https://smailpro.com
API: https://api.sonjj.com
Features: Tor support, retry logic, payload management, auto-refresh
"""

import re
import time
from typing import Any, Dict, List, Optional

import requests
from fake_useragent import UserAgent

from config import TOR_CONTROL_PORT, TOR_PORT
from utils import format_error, logger, renew_tor, mask


class SmailPro:
    """
    SmailPro temporary email service client.

    Provides temporary email addresses with optional Tor network support
    for enhanced privacy.

    Attributes:
        body_key: Key used to access HTML body in email responses.
        BASE_URL: SmailPro website URL.
        API_URL: SmailPro API base URL.
    """

    body_key = "body"
    BASE_URL = "https://smailpro.com"
    API_URL = "https://api.sonjj.com/v1/temp_email"

    def __init__(
        self,
        use_tor: bool = False,
        max_retries: int = 5
    ):
        """
        Initialize SmailPro client.

        Args:
            use_tor: Route requests through Tor network.
            max_retries: Maximum retry attempts for failed requests.
        """
        self.ua = UserAgent()
        self.use_tor = use_tor
        self.max_retries = max_retries
        self.email: Optional[str] = None
        self.token: Optional[str] = None  # Payload token
        self.expired_at: Optional[int] = None
        self.session: Optional[requests.Session] = None
        self.proxies: Dict[str, str] = {}

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
            # 'Accept': 'application/json, text/plain, */*',
            # 'Accept-Language': 'en-US,en;q=0.5',
            # 'Accept-Encoding': 'gzip, deflate, br',
            # 'Connection': 'keep-alive',
            # 'Origin': self.BASE_URL,
            # 'Referer': f'{self.BASE_URL}/',
        })
        self.session.proxies = self.proxies

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
        level: int = 0,
        json_response: bool = True
    ) -> Optional[Any]:
        """
        Make HTTP request with retry logic.

        Args:
            method: HTTP method ('GET' or 'POST').
            url: Request URL.
            timeout: Request timeout in seconds.
            level: Logging indentation level.
            json_response: Whether to parse response as JSON.

        Returns:
            Response data on success, None on failure.
            Returns dict with 'error': 'unauthorized' on 401.
        """
        for attempt in range(self.max_retries):
            try:
                if method == 'GET':
                    response = self.session.get(url, timeout=timeout)
                else:
                    response = self.session.post(url, timeout=timeout)

                # Handle 401 Unauthorized (payload expired)
                if response.status_code == 401:
                    return {'error': 'unauthorized', 'status_code': 401}

                response.raise_for_status()

                if json_response:
                    return response.json()
                return response.text.strip()

            except requests.exceptions.JSONDecodeError:
                # If JSON parsing fails, return text
                return response.text.strip() if response else None

            except Exception as e:
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

    def _get_payload(self, email: Optional[str] = None, level: int = 0) -> Optional[str]:
        """
        Get payload token for API requests.

        Args:
            email: Existing email address (optional, for reload).
            level: Logging indentation level.

        Returns:
            Payload token string, or None on failure.
        """
        url = f"{self.BASE_URL}/app/payload?url={self.API_URL}/create"
        if email:
            url += f"&email={email}"

        payload = self._request('GET', url, level=level, json_response=False)

        if payload and isinstance(payload, str) and not payload.startswith('{'):
            return payload

        logger("✗ Failed to get payload", level=level)
        return None

    def _refresh_payload(self, level: int = 0) -> bool:
        """
        Refresh the payload token for current email.

        Args:
            level: Logging indentation level.

        Returns:
            True if payload was refreshed successfully.
        """
        if not self.email:
            return False

        logger("🔄 Refreshing payload...", level=level)
        new_payload = self._get_payload(email=self.email, level=level + 1)

        if new_payload:
            self.token = new_payload
            # Re-create/reload the email to validate and update expiration
            result = self._request(
                'GET',
                f"{self.API_URL}/create?payload={self.token}",
                level=level + 1
            )
            if result and isinstance(result, dict) and 'email' in result:
                self.expired_at = result.get('expired_at')
                logger("✅ Payload refreshed", level=level)
                return True

        return False

    def _handle_unauthorized(self, level: int = 0) -> bool:
        """
        Handle unauthorized response by refreshing payload.

        Args:
            level: Logging indentation level.

        Returns:
            True if successfully refreshed, False otherwise.
        """
        logger("⚠ Payload expired, refreshing...", level=level)
        return self._refresh_payload(level=level)

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
            Dictionary with 'email' and 'token' keys, or None on failure.
        """
        logger("[######] Generating new email...", level=level)

        # Get payload for new email
        self.token = self._get_payload(level=level + 1)
        logger(f"✅ Token: {mask(self.token, 4)}", level=level + 1)
        if not self.token:
            return None

        # Create email
        result = self._request(
            'GET',
            f"{self.API_URL}/create?payload={self.token}",
            level=level + 1
        )

        if result and isinstance(result, dict) and 'email' in result:
            self.email = result['email']
            self.expired_at = result.get('expired_at')

            logger(f"✅ Email: {mask(self.email, 4)}", level=level + 1)
            logger(f"✅ Action: {result.get('action', 'unknown')}", level=level + 1)

            return {
                'email': self.email,
                'token': self.token
            }

        logger(f"✗ Failed to generate email: {result}", level=level + 1)
        return None

    def get_inbox(self, level: int = 0) -> Optional[Dict[str, Any]]:
        """
        Retrieve all emails from the inbox.

        Args:
            level: Logging indentation level.

        Returns:
            Dictionary with inbox data, or None on failure.
        """
        if not self.email or not self.token:
            logger("✗ No email address", level=level)
            return None

        result = self._request(
            'GET',
            f"{self.API_URL}/inbox?payload={self.token}",
            level=level + 1
        )

        # Handle payload expiration
        if isinstance(result, dict) and result.get('error') == 'unauthorized':
            if self._handle_unauthorized(level=level + 1):
                result = self._request(
                    'GET',
                    f"{self.API_URL}/inbox?payload={self.token}",
                    level=level + 1
                )
            else:
                return None

        if not result or not isinstance(result, dict) or 'messages' not in result:
            return None

        messages = result['messages']
        emails: List[Dict[str, Any]] = []

        for msg in messages:
            emails.append({
                'id': msg.get('mid'),
                'from': msg.get('textFrom', 'Unknown'),
                'subject': msg.get('textSubject', 'No Subject'),
                'received': msg.get('textDate', 'Unknown'),
                'to': msg.get('textTo', self.email),
                'read': 0
            })

        logger(f"📬 Found {len(emails)} emails", level=level)
        return {
            'email': self.email,
            'token': self.token,
            'emails': emails,
            'raw': result
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

        if not self.token:
            logger("✗ No payload token", level=level)
            return None

        result = self._request(
            'GET',
            f"{self.API_URL}/message?payload={self.token}&mid={msg_id}",
            level=level + 1
        )

        # Handle payload expiration
        if isinstance(result, dict) and result.get('error') == 'unauthorized':
            if self._handle_unauthorized(level=level + 1):
                result = self._request(
                    'GET',
                    f"{self.API_URL}/message?payload={self.token}&mid={msg_id}",
                    level=level + 1
                )
            else:
                return None

        if result and isinstance(result, dict) and 'body' in result:
            body_html = result['body']
            logger(f"📧 Retrieved email: {mask(msg_id, 4)}", level=level)
            return {
                'id': msg_id,
                'body': body_html,
                'body_html': body_html,
                'body_text': re.sub(r'<[^>]+>', '', body_html)
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
            unread_only: Only return unread emails (kept for API compatibility).
            level: Logging indentation level.

        Returns:
            First email in inbox, or None if timeout.
        """
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()
        seen_ids: set = set()

        while time.time() - start < timeout:
            inbox = self.get_inbox(level=level + 1)

            if inbox and inbox['emails']:
                for email in inbox['emails']:
                    if email['id'] not in seen_ids:
                        logger("✅ New email received!", level=level + 1)
                        return email
                # Track seen emails for unread_only logic
                seen_ids.update(e['id'] for e in inbox['emails'])

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
    api = SmailPro(use_tor=False)

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