import typing
from datetime import timedelta

from django.core.cache import cache
from django.utils.translation import gettext
from django.utils.translation import gettext_lazy as _

from djangoblog.utils import send_email

_code_ttl = timedelta(minutes=5)


def send_verify_email(to_mail: str, code: str, subject: str = _("Verify Email")):
    """Send password reset verification code
    Args:
        to_mail: Recipient email
        subject: Email subject
        code: Verification code
    """
    html_content = _(
        "You are resetting the password, the verification code is：%(code)s, valid within 5 minutes, please keep it "
        "properly") % {'code': code}
    send_email([to_mail], subject, html_content)


def verify(email: str, code: str) -> typing.Optional[str]:
    """Verify if the code is valid
    Args:
        email: Requested email
        code: Verification code
    Return:
        Return error string if there is an error
    Note:
        The error handling here is not ideal; it should use raise to throw exceptions
        Otherwise, the caller also needs to handle the error
    """
    cache_code = get_code(email)
    if cache_code != code:
        return gettext("Verification code error")


def set_code(email: str, code: str):
    """Set code"""
    cache.set(email, code, _code_ttl.seconds)


def get_code(email: str) -> typing.Optional[str]:
    """Get code"""
    return cache.get(email)