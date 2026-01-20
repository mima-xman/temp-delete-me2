"""
TempMailServices - Collection of temporary email service integrations.

Available services:
- EmailOnDeck: emailondeck.com API
- MailTM: mail.tm API
- SmailPro: smailpro.com API
- TempMailIO: temp-mail.io API
- TempMailOrg: temp-mail.org API
- TMailor: tmailor.com API

All services share a common interface:
- generate_email() -> dict with 'email' and 'token' keys
- get_inbox() -> list of emails
- get_email(email_data) -> full email content
- wait_for_email(timeout) -> first new email
"""

from .EmailOnDeck import EmailOnDeck
from .MailTM import MailTM
from .SmailPro import SmailPro
from .TempMailIO import TempMailIO
from .TempMailOrg import TempMailOrg
from .TMailor import TMailor

__all__ = [
    'EmailOnDeck',
    'MailTM',
    'SmailPro',
    'TempMailIO',
    'TempMailOrg',
    'TMailor',
]
