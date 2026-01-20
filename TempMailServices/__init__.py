"""
TempMailServices - Collection of temporary email service integrations.

Available services:
- EmailOnDeck: emailondeck.com API
- SmailPro: smailpro.com API
- TempMailIO: temp-mail.io API
- TempMailOrg: temp-mail.org API
- TMailor: tmailor.com API
- MailTM: mail.tm API

All services share a common interface:
- generate_email() -> dict with 'email' and 'token' keys
- get_inbox() -> list of emails
- get_email(email_data) -> full email content
- wait_for_email(timeout) -> first new email
"""

from .EmailOnDeck import EmailOnDeck
from .SmailPro import SmailPro
from .TempMailIO import TempMailIO
from .TempMailOrg import TempMailOrg
from .TMailor import TMailor
from .MailTM import MailTM

__all__ = [
    'EmailOnDeck',
    'SmailPro',
    'TempMailIO',
    'TempMailOrg',
    'TMailor',
    'MailTM',
]
