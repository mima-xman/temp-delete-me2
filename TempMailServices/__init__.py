"""
TempMailServices - Collection of temporary email service integrations.

Available services:
- EmailOnDeck: emailondeck.com API
- TMailorAPI: tmailor.com API
- TempMailExtensionAPI: temp-mail.org extension API
- TempMailIOAPI: temp-mail.io API

All services share a common interface:
- generate_email() -> dict with 'email' and 'token' keys
- get_inbox() -> list of emails
- get_email(email_data) -> full email content
- wait_for_email(timeout) -> first new email
"""

from .EmailOnDeck import EmailOnDeck
from .TMailorAPI import TMailorAPI
from .TempMailExtensionAPI import TempMailExtensionAPI
from .TempMailIOAPI import TempMailIOAPI

__all__ = [
    'EmailOnDeck',
    'TMailorAPI',
    'TempMailExtensionAPI',
    'TempMailIOAPI',
]
