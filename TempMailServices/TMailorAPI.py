import cloudscraper
import json
import time
from utils import logger, format_error

class TMailorAPI:
    body_key = "body"
    
    def __init__(self, access_token=None):
        self.base_url = "https://tmailor.com"
        self.api_url = f"{self.base_url}/api"
        self.access_token = access_token
        self.email = None
        self.proxies = {
            # "http": "socks5://127.0.0.1:9150",
            # "https": "socks5://127.0.0.1:9150"
        }
        self.scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
        )
    
    def _request(self, action, level: int = 0, **params):
        """Make API request"""
        payload = {
            "action": action,
            "accesstoken": self.access_token or "",
            "fbToken": None,
            "curentToken": self.access_token or "",
            **params
        }
        
        headers = {
            "content-type": "application/json",
            "origin": "https://tmailor.com",
            "referer": "https://tmailor.com/"
        }
        
        try:
            response = self.scraper.post(self.api_url, json=payload, headers=headers, proxies=self.proxies)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger(f"✗ Error {response.status_code}: {response.text[:200]}", level=level)
                return None
        except Exception as e:
            logger(f"✗ Request failed: {format_error(e)}", level=level)
            return None
    
    def generate_email(self, level: int = 0):
        """Generate new temporary email"""
        logger("[######] Generating new email...", level=level)
        data = self._request("newemail", level=level+1)
        
        if data and data.get('msg') == 'ok':
            self.access_token = data['accesstoken']
            self.email = data['email']
            
            logger(f"✅ Email: {self.email}", level=level+1)
            logger(f"✅ Token: {self.access_token[:50]}...", level=level+1)
            
            return {
                'email': self.email,
                'token': self.access_token,
                'created': data.get('create')
            }
        
        logger(f"✗ Failed to generate email: {data}", level=level+1)
        return None
    
    def get_inbox(self, level: int = 0):
        """Get all emails from inbox"""
        if not self.access_token:
            logger("✗ No access token", level=level)
            return None
        
        data = self._request("listinbox", level=level+1)
        # print(json.dumps(data, indent=4))
        
        if data and data.get('msg') == 'ok':
            messages_data = data.get('data', {}) or {}
            emails = list(messages_data.values())
            logger(f"📬 Found {len(emails)} emails", level=level)
            return {
                'email': data.get('email'),
                'code': data.get('code'),
                'emails': emails,
                'raw': data
            }
        
        return None
    
    def get_email(self, email_data, level: int = 0):
        """Get specific email content"""
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
            level=level+1
        )
        
        if data and data.get('msg') == 'ok':
            logger(f"📧 Retrieved email: {email_id}", level=level)
            return data.get('data')
        
        return None
    
    def wait_for_email(self, timeout=60, interval=3, unread_only=True, level: int = 0):
        """Wait for new email to arrive"""
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()
        
        while time.time() - start < timeout:
            inbox = self.get_inbox(level=level+1)
            
            if inbox and inbox['emails']:
                if unread_only:
                    unread = [e for e in inbox['emails'] if e.get('read') == 0]
                    if unread:
                        logger("✅ New email received!", level=level+1)
                        return unread[0]
                else:
                    logger("✅ Email found!", level=level+1)
                    return inbox['emails'][0]
            
            elapsed = int(time.time() - start)
            logger(f"⏳ Waiting... ({elapsed}/{timeout}s)", level=level+1)
            time.sleep(interval)
        
        logger("⏰ Timeout - no email received", level=level+1)
        return None
    
    def print_inbox(self, level: int = 0):
        """Pretty print inbox"""
        inbox = self.get_inbox(level=level)
        
        if not inbox or not inbox['emails']:
            logger("📭 Inbox is empty", level=level)
            return
        
        logger(f"📬 Inbox for: {inbox['email']}", level=level)
        
        for i, email in enumerate(inbox['emails'], 1):
            status = "📖" if email.get('read') == 1 else "📩"
            logger(f"{status} Email #{i}", level=level+1)
            logger(f"ID: {email['id']}", level=level+2)
            logger(f"From: {email['sender_name']} <{email['sender_email']}>", level=level+2)
            logger(f"Subject: {email['subject']}", level=level+2)
            logger(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(email['receive_time']))}", level=level+2)
            logger(f"Read: {'Yes' if email.get('read') == 1 else 'No'}", level=level+2)