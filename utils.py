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


def renew_tor(
    tor_control_port: int = 9151,
    tor_port: int = 9150,
    level: int = 0
) -> Tuple[bool, Optional[str]]:
    """
    Request a new Tor circuit (new IP address).

    Connects to the Tor control port and sends a NEWNYM signal to get
    a fresh exit node and IP address.

    Args:
        tor_control_port: Tor control port (default 9151 for Tor Browser).
        tor_port: Tor SOCKS proxy port (default 9150 for Tor Browser).
        level: Logging indentation level.

    Returns:
        A tuple of (success: bool, new_ip: str | None).
    """
    try:
        with Controller.from_port(port=tor_control_port) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
            time.sleep(5)  # Wait for new circuit to be established
            logger("✓ Tor renewed", level=level)

            # Try to get the new IP address
            ip: Optional[str] = None
            try:
                tor_proxies: Dict[str, str] = {
                    "http": f"socks5://127.0.0.1:{tor_port}",
                    "https": f"socks5://127.0.0.1:{tor_port}"
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


if __name__ == "__main__":
    # Example usage
    test_secret = "WNC34H4G6ZHVLP43"
    code = get_2fa_code(test_secret)
    print(f"Current 2FA code: {code}")