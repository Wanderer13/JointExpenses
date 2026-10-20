"""Backward-compatible alias for the stub/file mail backend. """

from app.services.mail import send_email

__all__ = ["send_email"]
