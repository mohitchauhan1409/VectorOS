"""Email-finding subsystem for Detective (configurable provider + fallback)."""

from modules.scout.detective.email.base import EmailProvider, EmailResult
from modules.scout.detective.email.finder import EmailFinder

__all__ = ["EmailFinder", "EmailProvider", "EmailResult"]
