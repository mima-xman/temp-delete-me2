import json
import time
import requests
from utils import logger, format_error

class TempMailIOAPI:
    body_key = "body_html"
    
    def __init__(self):
        self.base_url = "https://temp-mail.io"
        self.api_url = "https://api.internal.temp-mail.io/api/v3"
        self.api_url_v4 = "https://api.internal.temp-mail.io/api/v4"
        self.email = None
        self.token = None
        self.session = requests.Session()
        self.proxies = {
            "http": "socks5://127.0.0.1:9150",
            "https": "socks5://127.0.0.1:9150"
        }
        
        # Set default headers
        self.session.headers.update({
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate, br, zstd',
            'accept-language': 'fr-FR,fr;q=0.7',
            'application-name': 'web',
            'application-version': '4.0.0',
            'content-type': 'application/json',
            'origin': 'https://temp-mail.io',
            'referer': 'https://temp-mail.io/',
            'sec-ch-ua': '"Brave";v="143", "Chromium";v="143", "Not A(Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'sec-gpc': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36',
            'x-cors-header': 'iaWg3pchvFx48fY'
        })
        
        logger("🚀 Initializing TempMailIOAPI...", level=0)
        logger("✅ API ready", level=0)

    def close(self):
        """Close session"""
        try:
            if self.session:
                self.session.close()
        except:
            pass

    def _request(self, method, endpoint, level: int = 0, **kwargs):
        """Make API request"""
        try:
            url = endpoint if endpoint.startswith('http') else f"{self.api_url}{endpoint}"
            
            response = self.session.request(method, url, **kwargs, proxies=self.proxies)
            
            if not response.ok:
                logger(f"✗ Error {response.status_code}: {response.text[:200]}", level=level)
                return None
            
            return response.json()

        except Exception as e:
            logger(f"✗ Request failed: {format_error(e)}", level=level)
            return None
    
    def get_domains(self, level: int = 0):
        """Get available domains"""
        logger("[######] Getting available domains...", level=level)
        data = self._request("GET", f"{self.api_url_v4}/domains", level=level+1)
        
        if data and 'domains' in data:
            domains = data['domains']
            logger(f"✅ Found {len(domains)} domains", level=level+1)
            return domains
        
        logger(f"✗ Failed to get domains: {data}", level=level+1)
        return None
    
    def generate_email(self, min_length=10, max_length=10, custom_name=None, level: int = 0):
        """Generate new temporary email with random name"""
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
            level=level+1,
            json=payload
        )
        
        if data and 'email' in data and 'token' in data:
            self.email = data['email']
            self.token = data['token']
            
            logger(f"✅ Email: {self.email}", level=level+1)
            logger(f"✅ Token: {self.token}", level=level+1)
            
            return {
                'email': self.email,
                'token': self.token
            }
        
        logger(f"✗ Failed to generate email: {data}", level=level+1)
        return None
    
    def generate_custom_email(self, name, domain=None, level: int = 0):
        """Generate new temporary email with custom name and domain"""
        logger("[######] Generating custom email...", level=level)
        
        # If no domain specified, get the first available one
        if not domain:
            domains = self.get_domains(level=level+1)
            if not domains:
                logger("✗ Failed to get domains", level=level+1)
                return None
            domain = domains[0]['name']
            logger(f"📝 Using domain: {domain}", level=level+1)
        
        payload = {
            "name": name,
            "domain": domain
        }
        
        data = self._request(
            "POST", 
            "/email/new",
            level=level+1,
            json=payload
        )
        
        if data and 'email' in data and 'token' in data:
            self.email = data['email']
            self.token = data['token']
            
            logger(f"✅ Email: {self.email}", level=level+1)
            logger(f"✅ Token: {self.token}", level=level+1)
            
            return {
                'email': self.email,
                'token': self.token
            }
        
        logger(f"✗ Failed to generate custom email: {data}", level=level+1)
        return None
    
    def get_inbox(self, level: int = 0):
        """Get all emails from inbox"""
        if not self.email:
            logger("✗ No email address", level=level)
            return None
        
        data = self._request(
            "GET",
            f"/email/{self.email}/messages",
            level=level+1
        )
        
        if data is not None:
            emails = data if isinstance(data, list) else []
            logger(f"📬 Found {len(emails)} emails", level=level)
            return {
                'email': self.email,
                'token': self.token,
                'emails': emails,
                'raw': data
            }
        
        return None
    
    def get_email(self, email_data, level: int = 0):
        """Get specific email content"""
        if isinstance(email_data, dict):
            email_id = email_data.get('id')
        else:
            email_id = email_data

        if not email_id:
            logger("✗ No email id", level=level)
            return None

        data = self._request(
            "GET",
            f"/message/{email_id}",
            level=level+1
        )
        
        if data and 'id' in data:
            logger(f"📧 Retrieved email: {email_id}", level=level)
            return data
        
        return None
    
    def wait_for_email(self, timeout=60, interval=3, level: int = 0):
        """Wait for new email to arrive"""
        logger(f"⏳ Waiting for email (timeout: {timeout}s)...", level=level)
        start = time.time()
        
        while time.time() - start < timeout:
            inbox = self.get_inbox(level=level+1)
            
            if inbox and inbox['emails']:
                logger("✅ New email received!", level=level+1)
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
            logger(f"📩 Email #{i}", level=level+1)
            logger(f"ID: {email['id']}", level=level+2)
            logger(f"From: {email['from']}", level=level+2)
            logger(f"To: {email['to']}", level=level+2)
            logger(f"Subject: {email['subject']}", level=level+2)
            logger(f"Time: {email['created_at']}", level=level+2)
            if email.get('cc'):
                logger(f"CC: {email['cc']}", level=level+2)
            if email.get('attachments'):
                logger(f"Attachments: {len(email['attachments'])}", level=level+2)