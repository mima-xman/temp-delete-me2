"""
Utility functions for the account generator project.

Provides logging, error formatting, Tor network management, and 2FA code generation.
"""

import time
from typing import Optional, Tuple, Dict, List

import pyotp
import requests
from stem import Signal
from stem.control import Controller
import stem.descriptor.remote

from config import TOR_CONTROL_PORT, TOR_PORT, TOR_CONTROL_PASSWORD

from dotenv import load_dotenv 
from pathlib import Path


# Your preferred exit node IPs
PREFERRED_EXIT_IPS = [
    '192.42.116.194',
    '192.42.116.180',
    '107.189.7.144',
    '185.181.60.205',
    '185.220.101.104',
]


# Load environment variables from .env file
# Check for .env in current directory first (for zipapp support)
env_path = Path.cwd() / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    # Fallback to default discovery (for development)
    try:
        load_dotenv()
    except AssertionError:
        # Can happen in zipapp if .env is missing and finding logic fails
        pass


def logger(message: str, level: int = 0) -> None:
    """
    Print a message with indentation based on level.

    Args:
        message: The message to print.
        level: Indentation level (each level adds 2 spaces).
    """
    indent = "  " * level
    print(f"{indent}{message}")


def format_error(e: Exception) -> str:
    """
    Format an exception message by removing Playwright call logs.

    Playwright exceptions include verbose call logs that clutter output.
    This function strips everything after "Call log:" for cleaner messages.

    Args:
        e: The exception to format.

    Returns:
        A cleaned error message string.
    """
    return str(e).split("Call log:")[0].strip()


def renew_tor(level: int = 0) -> Tuple[bool, Optional[str]]:
    """
    Request a new Tor circuit (new IP address).

    Connects to the Tor control port and sends a NEWNYM signal to get
    a fresh exit node and IP address.

    Args:
        level: Logging indentation level.

    Returns:
        A tuple of (success: bool, new_ip: str | None).
    """
    try:
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
            time.sleep(5)  # Wait for new circuit to be established
            logger("✓ Tor renewed", level=level)

            # Try to get the new IP address
            ip: Optional[str] = None
            try:
                tor_proxies: Dict[str, str] = {
                    "http": f"socks5://127.0.0.1:{TOR_PORT}",
                    "https": f"socks5://127.0.0.1:{TOR_PORT}"
                }
                ip = get_current_ip(proxies=tor_proxies, level=level)
            except Exception:
                pass

            return True, ip

    except Exception as e:
        logger(f"✗ Failed to renew Tor: {e}", level=level)
        return False, None


def get_current_ip(
    proxies: Optional[Dict[str, str]] = None,
    timeout: int = 10,
    level: int = 0
) -> Optional[str]:
    """
    Get the current public IP address.

    Tries multiple IP lookup services until one succeeds.

    Args:
        proxies: Optional proxy dictionary for requests (e.g., for Tor).
        timeout: Request timeout in seconds.
        level: Logging indentation level.

    Returns:
        The IP address string, or None if all services fail.
    """
    if proxies is None:
        proxies = {}

    ip_services: List[str] = [
        'https://ifconfig.me/ip',
        'https://icanhazip.com',
        'https://checkip.amazonaws.com',
        'https://ipinfo.io/ip',
        'https://ident.me'
    ]

    for service in ip_services:
        try:
            response = requests.get(
                service,
                proxies=proxies,
                timeout=timeout
            )
            if response.status_code == 200:
                ip = response.text.strip()
                logger(f"✓ Current IP: {ip}", level=level)
                return ip
        except requests.RequestException:
            continue

    logger("✗ Failed to get current IP", level=level)
    return None


def get_2fa_code(secret: str) -> str:
    """
    Generate a TOTP 2FA code from a secret key.

    Args:
        secret: The base32-encoded TOTP secret key.

    Returns:
        The current 6-digit TOTP code.
    """
    totp = pyotp.TOTP(secret)
    return totp.now()


def mask(value: str, show_chars: int = 3) -> str:
    """Mask sensitive data, showing only first few characters."""
    if not value:
        return "***"
    if len(value) <= show_chars:
        return "*" * len(value)
    return value[:show_chars] + "*" * (len(value) - show_chars)


# ====================================================================================
# NEW METHODS FOR RENEWING TOR IP
# ====================================================================================

def get_exit_fingerprints_by_ip(target_ips: List[str], level: int = 0) -> Dict[str, str]:
    """
    Get fingerprints for exit nodes with specific IPs.
    
    Args:
        target_ips: List of target IP addresses
        level: Logging level
    
    Returns:
        Dict mapping IP -> fingerprint
    """
    fingerprints = {}
    
    try:
        # Fetch current consensus (list of all relays)
        for desc in stem.descriptor.remote.get_consensus():
            if desc.address in target_ips and 'Exit' in desc.flags:
                fingerprints[desc.address] = desc.fingerprint
                # logger(f"Found: {desc.address} -> {desc.fingerprint}", level=level)
    except Exception as e:
        logger(f"Error fetching descriptors: {e}", level=level)
    
    logger(f"Found {len(fingerprints)} exit nodes", level=level)
    return fingerprints


def configure_preferred_exits(
    preferred_ips: List[str],
    strict: bool = False,
    level: int = 0
) -> bool:
    """
    Configure Tor to use preferred exit nodes.
    
    Args:
        preferred_ips: List of preferred exit node IPs
        strict: If True, ONLY use these exits (may fail if none available)
        level: Logging level
    """
    try:
        # Get fingerprints for our preferred IPs
        fingerprints = get_exit_fingerprints_by_ip(preferred_ips, level=level)
        
        if not fingerprints:
            logger("⚠ No matching exit nodes found for preferred IPs", level=level)
            return False
        
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            if TOR_CONTROL_PASSWORD:
                controller.authenticate(password=TOR_CONTROL_PASSWORD)
            else:
                controller.authenticate()
            
            # Format fingerprints for Tor config
            fingerprint_list = ','.join(f'${fp}' for fp in fingerprints.values())
            
            # Set exit node preferences
            controller.set_conf('ExitNodes', fingerprint_list)
            controller.set_conf('StrictNodes', '1' if strict else '0')
            
            logger(f"✓ Configured {len(fingerprints)} preferred exit nodes", level=level)
            return True
            
    except Exception as e:
        logger(f"✗ Error configuring exits: {e}", level=level)
        return False


def renew_tor_ip_with_preferred_exit(
    preferred_ips: Optional[List[str]] = None,
    max_attempts: int = 10,
    level: int = 0
) -> Tuple[bool, Optional[str]]:
    """
    Renew Tor circuit, trying to get a preferred exit node.
    
    Args:
        preferred_ips: List of preferred exit IPs
        max_attempts: Max circuit renewal attempts
        level: Logging level
        
    Returns:
        New IP address or None
    """
    if preferred_ips is None:
        preferred_ips = PREFERRED_EXIT_IPS
    
    # First, configure preferred exits
    configure_preferred_exits(
        preferred_ips,
        strict=False,  # Allow fallback to other exits
        level=level
    )
    
    tor_proxies = {
        'http': f'socks5://127.0.0.1:{TOR_PORT}',
        'https': f'socks5://127.0.0.1:{TOR_PORT}'
    }
    
    for attempt in range(max_attempts):
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
                if TOR_CONTROL_PASSWORD:
                    controller.authenticate(password=TOR_CONTROL_PASSWORD)
                else:
                    controller.authenticate()
                
                # Request new circuit
                controller.signal(Signal.NEWNYM)
                time.sleep(5)  # Wait for new circuit
            
            # Check new IP
            new_ip = get_current_ip(proxies=tor_proxies, level=level+1)
            
            if new_ip and new_ip in preferred_ips:
                logger(f"✓ Got preferred exit IP: {new_ip}", level=level)
                return True, new_ip
            elif new_ip:
                logger(f"Got IP: {new_ip} (not preferred, attempt {attempt+1}/{max_attempts})", level=level)
                
        except Exception as e:
            logger(f"Failed to renew Tor circuit with preferred exits (attempt {attempt+1}/{max_attempts}): {e}", level=level)
    
    # Return whatever IP we have
    new_ip = get_current_ip(proxies=tor_proxies, level=level)
    return False, new_ip


def renew_tor_ip_strict(
    preferred_ips: Optional[List[str]] = None,
    level: int = 0
) -> Tuple[bool, Optional[str]]:
    """
    Renew Tor circuit, ONLY using preferred exit nodes.

    Args:
        preferred_ips: List of preferred exit node IPs
        level: Logging level
    Returns:
        Tuple of (success: bool, new_ip: str | None)

    ⚠ Warning: Will fail if none of the preferred exits are available.
    """
    try:
        if preferred_ips is None:
            preferred_ips = PREFERRED_EXIT_IPS
        
        # Strict mode - only use our preferred exits
        success = configure_preferred_exits(
            preferred_ips,
            strict=True,  # StrictNodes = 1
            level=level
        )
        
        if not success:
            return False, None
        
        tor_proxies = {
            'http': f'socks5://127.0.0.1:{TOR_PORT}',
            'https': f'socks5://127.0.0.1:{TOR_PORT}'
        }
        
        with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
            if TOR_CONTROL_PASSWORD:
                controller.authenticate(password=TOR_CONTROL_PASSWORD)
            else:
                controller.authenticate()
            
            controller.signal(Signal.NEWNYM)
            time.sleep(5)
        
        new_ip = get_current_ip(proxies=tor_proxies, level=level)
        return True, new_ip
    except Exception as e:
        logger(f"✗ Error renewing Tor IP: {e}", level=level)
        return False, None

# ====================================================================================





if __name__ == "__main__":
    # Example usage
    # test_secret = "WNC34H4G6ZHVLP43"
    # test_secret = "A6LC2I47LLR7OM55"
    # test_secret = "5NHY67EX7J5X2BN7"
    # test_secret = "YXTMXS5XT63GWJIM"
    # test_secret = "SDMPOF5YZGOSAFOU"
    test_secret = "SPCKDSBS3IFSNJKE"
    code = get_2fa_code(test_secret)
    print(f"Current 2FA code: {code}")