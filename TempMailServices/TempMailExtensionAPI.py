from curl_cffi import requests
import json
import time
import random
import os

class TempMailExtensionAPI:
    body_key = "bodyHtml"

    def __init__(self, token=None, use_tor=False):
        self.base_url = "https://web2.temp-mail.org"
        self.token = token
        self.email = None
        self.session = requests.Session()
        self.use_tor = use_tor
        self.tor_proxies = {
            "http": "socks5://127.0.0.1:9150",
            "https": "socks5://127.0.0.1:9150"
        } if use_tor else {}
    
    def _get_headers(self):
        """Get headers with authorization"""
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
    
    def _request_with_retry(self, method, url, max_retries=3, **kwargs):
        """Make request with retry logic"""
        for attempt in range(max_retries):
            try:
                if method == "GET":
                    response = self.session.get(url, **kwargs)
                else:
                    response = self.session.post(url, **kwargs)
                
                # Success
                if response.status_code == 200:
                    return response
                
                # Rate limit - wait and retry
                if response.status_code == 429:
                    wait_time = (attempt + 1) * 5
                    print(f"⚠️ Rate limited. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                
                # Cloudflare block - wait longer
                if response.status_code == 403:
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 10
                        print(f"⚠️ Blocked (403). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        return response
                
                # Other errors
                return response
                
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    print(f"⚠️ Request error: {str(e)[:50]}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    raise
        
        return None
    
    def generate_email(self):
        """Generate new temporary email"""
        try:
            # Add random delay to avoid rate limiting
            time.sleep(random.uniform(1, 3))
            
            response = self._request_with_retry(
                "POST",
                f"{self.base_url}/mailbox",
                headers=self._get_headers(),
                # impersonate="chrome110",
                proxies=self.tor_proxies,
                timeout=15
            )
            
            if response and response.status_code == 200:
                data = response.json()
                self.token = data['token']
                self.email = data['mailbox']
                
                print(f"✅ Email: {self.email}")
                print(f"✅ Token: {self.token[:50]}...")
                
                return {
                    'email': self.email,
                    'token': self.token
                }
            elif response:
                print(f"❌ Error {response.status_code}: {response.text[:200]}")
                return None
            else:
                print("❌ Failed after retries")
                return None
        except Exception as e:
            print(f"❌ Request failed: {str(e)}")
            return None
    
    def get_inbox(self):
        """Get all emails from inbox"""
        if not self.token:
            print("❌ No token")
            return None
        
        try:
            response = self._request_with_retry(
                "GET",
                f"{self.base_url}/messages",
                headers=self._get_headers(),
                impersonate="chrome110",
                proxies=self.tor_proxies,
                timeout=15
            )
            
            if response and response.status_code == 200:
                data = response.json()
                messages = data.get('messages', [])
                print(f"📬 Found {len(messages)} emails")
                return {
                    'email': data.get('mailbox'),
                    'messages': messages
                }
            elif response:
                print(f"❌ Error {response.status_code}: {response.text[:200]}")
                return None
            else:
                return None
        except Exception as e:
            print(f"❌ Request failed: {str(e)[:100]}")
            return None
    
    def get_email(self, message_data):
        """Get specific email content"""
        if not self.token:
            print("❌ No token")
            return None

        message_id = message_data.get('_id')
        if not message_id:
            print("❌ No message id")
            return None
        
        try:
            response = self._request_with_retry(
                "GET",
                f"{self.base_url}/messages/{message_id}",
                headers=self._get_headers(),
                impersonate="chrome110",
                proxies=self.tor_proxies,
                timeout=15
            )
            
            if response and response.status_code == 200:
                data = response.json()
                print(f"📧 Retrieved email: {message_id}")
                return data
            elif response:
                print(f"❌ Error {response.status_code}: {response.text[:200]}")
                return None
            else:
                return None
        except Exception as e:
            print(f"❌ Request failed: {str(e)[:100]}")
            return None
    
    def wait_for_email(self, timeout=60, interval=5):
        """Wait for new email to arrive"""
        print(f"⏳ Waiting for email (timeout: {timeout}s)...")
        start = time.time()
        
        while time.time() - start < timeout:
            inbox = self.get_inbox()
            
            if inbox and inbox['messages']:
                print("✅ Email received!")
                return inbox['messages'][0]
            
            elapsed = int(time.time() - start)
            print(f"⏳ Waiting... ({elapsed}/{timeout}s)")
            time.sleep(interval)
        
        print("⏰ Timeout - no email received")
        return None
    
    def print_inbox(self):
        """Pretty print inbox"""
        inbox = self.get_inbox()
        
        if not inbox or not inbox['messages']:
            print("📭 Inbox is empty")
            return
        
        print(f"\n📬 Inbox for: {inbox['email']}")
        print("=" * 80)
        
        for i, msg in enumerate(inbox['messages'], 1):
            print(f"\n📩 Email #{i}")
            print(f"   ID: {msg['_id']}")
            print(f"   From: {msg['from']}")
            print(f"   Subject: {msg['subject']}")
            print(f"   Preview: {msg['bodyPreview']}")
            print(f"   Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(msg['receivedAt']))}")
            print(f"   Attachments: {msg['attachmentsCount']}")
    
    def close(self):
        """Close session"""
        self.session.close()


# Usage Examples
if __name__ == "__main__":

    token_file_path = "temp_mail_token.txt"
    
    # Example 1: Generate new email WITHOUT Tor
    print("=" * 60)
    print("EXAMPLE 1: Without Tor")
    print("=" * 60)
    
    # Get token from file if exists
    TOKEN = None
    if os.path.exists(token_file_path):
        with open(token_file_path, "r") as f:
            TOKEN = f.read().strip()
            print(f"🔑 History Token: {TOKEN}")
    else:
        print("🔍 No history token found")
    
    api = TempMailExtensionAPI(token=None, use_tor=True)
    
    try:
        result = api.generate_email()
        
        if result:
            token = result['token']

            # Save token in txt file
            with open(token_file_path, "w") as f:
                f.write(token)

            print(f"\n📧 Your temporary email: {api.email}")
            api.print_inbox()
            
            # Wait for email
            new_email = api.wait_for_email(timeout=120)
            if new_email:
                content = api.get_email(new_email['_id'])
                if content:
                    print("\n" + "=" * 60)
                    print("EMAIL CONTENT")
                    print("=" * 60)
                    print(f"From: {content['from']}")
                    print(f"Subject: {content['subject']}")
                    print(f"\nHTML Body:\n{content['bodyHtml']}")
    finally:
        api.close()
    
    # Example 2: WITH Tor (may have issues due to Cloudflare)
    # print("\n" + "=" * 60)
    # print("EXAMPLE 2: With Tor")
    # print("=" * 60)
    
    # api2 = TempMailExtensionAPI(use_tor=True)
    # try:
    #     result = api2.generate_email()
    #     if result:
    #         print(f"\n📧 Email: {api2.email}")
    # finally:
    #     api2.close()