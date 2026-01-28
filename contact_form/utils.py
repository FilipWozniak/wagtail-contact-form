from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)

LOCALHOST_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\.localhost(:\d+)?$"),
    re.compile(r"^localhost(:\d+)?$"),
    re.compile(r"^127\.0\.0\.1(:\d+)?$"),
    re.compile(r"^0\.0\.0\.0(:\d+)?$"),
    re.compile(r"^\[::1\](:\d+)?$"),
]

# Google reCAPTCHA (Test Keys) - https://developers.google.com/recaptcha/docs/faq
RECAPTCHA_TEST_SITE_KEY = "6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI"
RECAPTCHA_TEST_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe"

# Cloudflare Turnstile (Test Keys) - https://developers.cloudflare.com/turnstile/troubleshooting/testing/
TURNSTILE_TEST_SITE_KEY = "1x00000000000000000000AA"
TURNSTILE_TEST_SECRET_KEY = "1x0000000000000000000000000000000AA"


def is_localhost(request: HttpRequest | None = None, host: str | None = None) -> bool:
    if request is not None:
        host = request.get_host()

    if not host:
        return False

    host_lower = host.lower()

    for pattern in LOCALHOST_PATTERNS:
        if pattern.search(host_lower):
            return True

    return False


def get_recaptcha_test_keys() -> dict[str, str]:
    logger.info("Using Development Keys for CAPTCHA (reCAPTCHA)")
    return {
        "site_key": RECAPTCHA_TEST_SITE_KEY,
        "secret_key": RECAPTCHA_TEST_SECRET_KEY,
    }


def get_turnstile_test_keys() -> dict[str, str]:
    logger.info("Using Development Keys for CAPTCHA (Turnstile)")
    return {
        "site_key": TURNSTILE_TEST_SITE_KEY,
        "secret_key": TURNSTILE_TEST_SECRET_KEY,
    }


def get_captcha_keys_for_environment(
    provider: str,
    request: HttpRequest | None = None,
    configured_keys: dict[str, str] | None = None,
) -> dict[str, str]:
    import os

    force_production = os.getenv("CAPTCHA_FORCE_PRODUCTION", "").lower() in ("1", "true", "yes")

    if is_localhost(request) and not force_production:
        if provider == "turnstile":
            return get_turnstile_test_keys()
        else:
            return get_recaptcha_test_keys()

    return configured_keys or {"site_key": "", "secret_key": ""}
