from __future__ import annotations

import ast
import hashlib
import logging
import re
from collections.abc import Mapping
from datetime import timedelta
from typing import TYPE_CHECKING
from typing import Any

from django.conf import settings
from django.core.mail import send_mail

from contact_form.security import SecurityStateUnavailable
from contact_form.security import acquire_security_window
from contact_form.security import get_page_scope_hash
from contact_form.security import privacy_hash
from contact_form.models import SecurityEventKind
from contact_form.utils import is_localhost

if TYPE_CHECKING:
    from django.http import HttpRequest

    from contact_form.models import ContactPage

logger = logging.getLogger(__name__)

_SAFE_ERROR_CODE = re.compile(r"^[a-z0-9_-]{1,80}$")
_SENSITIVE_EXTRA_NAMES = ("token", "response", "secret")


def _get_site_label() -> str | None:
    return (
        getattr(settings, "WEBSITE_SHORT_NAME", None)
        or getattr(settings, "WEBSITE_FULL_NAME", None)
        or getattr(settings, "BASE_URL", None)
        or getattr(settings, "WAGTAILADMIN_BASE_URL", None)
        or getattr(settings, "WAGTAIL_SITE_NAME", None)
    )


def _get_site_phrase() -> str:
    if site_label := _get_site_label():
        return f"on the {site_label} website"
    return "on the website"


def get_technical_from_email() -> str | None:
    return (
        getattr(settings, "SERVER_EMAIL", None)
        or getattr(settings, "WAGTAILADMIN_NOTIFICATION_FROM_EMAIL", None)
        or getattr(settings, "DEFAULT_FROM_EMAIL", None)
    )


def get_technical_recipients(page: ContactPage | None) -> list[str]:
    if page is None:
        return []

    recipients: list[str] = []
    seen: set[str] = set()
    for raw_address in page.technical_to_address.split(","):
        address = raw_address.strip()
        normalized = address.casefold()
        if address and normalized not in seen:
            recipients.append(address)
            seen.add(normalized)
    return recipients


def _is_sentry_configured() -> bool:
    try:
        import sentry_sdk

        return sentry_sdk.get_client().is_active()
    except (ImportError, RuntimeError):
        return False
    except Exception:
        return False


def _report_to_sentry(
    error_message: str,
    extra_data: Mapping[str, Any] | None = None,
    *,
    error_key: str = "captcha.unknown",
) -> None:
    try:
        import sentry_sdk

        expected_rejection = error_key.startswith("turnstile.verification.")
        client = sentry_sdk.get_client()
        scope = sentry_sdk.Scope()
        scope.set_client(client)
        scope.set_tag("component", "captcha")
        scope.set_tag("captcha_error_key", error_key)
        scope.fingerprint = ["contact-form-captcha", error_key]
        if extra_data:
            for key, value in extra_data.items():
                scope.set_extra(key, value)
        client.capture_event(
            event={
                "message": error_message,
                "level": "warning" if expected_rejection else "error",
            },
            scope=scope,
        )
    except ImportError:
        return
    except Exception as exc:
        logger.debug("Failed to report CAPTCHA error to Sentry: %s", type(exc).__name__)


def build_captcha_error_key(provider: str, error_message: str) -> str:
    provider_key = re.sub(r"[^a-z0-9]+", "-", provider.casefold()).strip("-") or "captcha"
    prefix = "turnstile" if "turnstile" in provider_key else provider_key

    if error_message.startswith("Verification Failed:"):
        raw_codes = error_message.partition(":")[2].strip()
        try:
            parsed_codes = ast.literal_eval(raw_codes)
        except (SyntaxError, ValueError):
            parsed_codes = []

        if not isinstance(parsed_codes, (list, tuple, set)):
            parsed_codes = [parsed_codes]
        codes = sorted(
            {str(code).casefold() for code in parsed_codes if _SAFE_ERROR_CODE.fullmatch(str(code).casefold())}
        )
        suffix = "+".join(codes) if codes else "unknown"
        return f"{prefix}.verification.{suffix}"

    stable_prefixes = {
        "Turnstile Secret Key is Not Configured": "configuration.missing-secret",
        "API Request Failed:": "transport.api-request",
        "API Response Parsing Failed:": "response.invalid",
        "Unexpected Error:": "unexpected",
    }
    for display_prefix, stable_suffix in stable_prefixes.items():
        if error_message.startswith(display_prefix):
            return f"{prefix}.{stable_suffix}"

    digest = hashlib.sha256(error_message.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}.other.{digest}"


def _safe_extra_data(extra_data: Mapping[str, Any] | None) -> dict[str, str]:
    safe_data: dict[str, str] = {}
    for key, value in (extra_data or {}).items():
        normalized_key = str(key).casefold()
        if any(sensitive_name in normalized_key for sensitive_name in _SENSITIVE_EXTRA_NAMES):
            continue
        safe_data[str(key)] = str(value)[:500]
    return safe_data


def _sentry_extra_data(extra_data: Mapping[str, str]) -> dict[str, str]:
    sentry_data: dict[str, str] = {}
    for key, value in extra_data.items():
        if key.casefold() in {"remote_ip", "client_ip", "user_ip"}:
            sentry_data[f"{key}_hash"] = privacy_hash("captcha-ip", value)
        else:
            sentry_data[key] = value
    return sentry_data


def notify_captcha_error(
    error_message: str,
    request: HttpRequest | None = None,
    provider: str = "CAPTCHA",
    extra_data: Mapping[str, Any] | None = None,
    *,
    page: ContactPage | None = None,
    error_key: str | None = None,
) -> bool:

    stable_error_key = error_key or build_captcha_error_key(provider, error_message)
    safe_extra_data = _safe_extra_data(extra_data)

    if is_localhost(request):
        logger.warning(
            "CAPTCHA Error on Localhost: provider=%s error_key=%s error=%s extra=%s",
            provider,
            stable_error_key,
            error_message,
            safe_extra_data,
        )
        return False

    throttle_minutes = max(1, int(getattr(page, "error_message_throttling", 60)))
    scope_hash = get_page_scope_hash(page) if page is not None else privacy_hash("contact-form-page", "global")
    try:
        decision = acquire_security_window(
            kind=str(SecurityEventKind.CAPTCHA_NOTIFICATION),
            scope_hash=scope_hash,
            fingerprint=privacy_hash("captcha-error", provider, stable_error_key),
            duration=timedelta(minutes=throttle_minutes),
            limit=1,
        )
    except SecurityStateUnavailable as exc:
        logger.error(
            "Suppressed CAPTCHA notification because its throttle state is unavailable: exception_type=%s",
            type(exc).__name__,
        )
        return False

    if not decision.allowed:
        logger.info(
            "Suppressed repeated CAPTCHA notification: error_key=%s retry_after=%s",
            stable_error_key,
            decision.retry_after_seconds,
        )
        return False

    site_label = _get_site_label()
    subject = f"Problem with CAPTCHA on {site_label}" if site_label else "Problem with CAPTCHA"
    body = (
        f"There was a problem with CAPTCHA {_get_site_phrase()}. Please investigate.\n\n"
        f"Provider: {provider}\n"
        f"Error: {error_message}\n"
        f"Error Type: {stable_error_key}\n"
    )
    if safe_extra_data:
        body += "\nAdditional Information:\n"
        for key, value in safe_extra_data.items():
            body += f"  {key}: {value}\n"

    recipients = get_technical_recipients(page)
    if recipients:
        try:
            sent_count = send_mail(
                subject=subject,
                message=body,
                from_email=get_technical_from_email(),
                recipient_list=recipients,
                fail_silently=False,
            )
            if sent_count == 1:
                logger.info(
                    "CAPTCHA Technical Notification Sent: error_key=%s recipient_count=%s",
                    stable_error_key,
                    len(recipients),
                )
            else:
                logger.error(
                    "CAPTCHA Technical Notification Backend Returned Zero: error_key=%s",
                    stable_error_key,
                )
        except Exception as exc:
            logger.error(
                "Failed to Send CAPTCHA Technical Notification: error_key=%s exception_type=%s",
                stable_error_key,
                type(exc).__name__,
            )
    else:
        logger.warning(
            "CAPTCHA Error - No Technical Recipients: error_key=%s",
            stable_error_key,
        )

    if _is_sentry_configured():
        _report_to_sentry(
            f"CAPTCHA Error ({provider}): {error_message}",
            extra_data={
                "provider": provider,
                "site": site_label or "unknown",
                **_sentry_extra_data(safe_extra_data),
            },
            error_key=stable_error_key,
        )

    return True
