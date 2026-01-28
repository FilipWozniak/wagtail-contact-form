from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.mail import send_mail

from contact_form.utils import is_localhost

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)


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


def _get_admin_email() -> str | None:
    admin_email = getattr(settings, "WAGTAILADMIN_NOTIFICATION_FROM_EMAIL", None)
    if not admin_email:
        admin_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    if not admin_email:
        admins = getattr(settings, "ADMINS", [])
        if admins and len(admins) > 0:
            admin_email = admins[0][1] if len(admins[0]) > 1 else None

    return admin_email if admin_email else None


def _is_sentry_configured() -> bool:
    try:
        import sentry_sdk

        client = sentry_sdk.get_client()
        return client.is_active()
    except ImportError:
        return False
    except Exception:
        return False


def _report_to_sentry(error_message: str, extra_data: dict | None = None) -> None:
    try:
        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            scope.set_tag("component", "captcha")
            if extra_data:
                for key, value in extra_data.items():
                    scope.set_extra(key, value)
            sentry_sdk.capture_message(error_message, level="error")
    except ImportError:
        pass
    except Exception as e:
        logger.debug("Failed to Report to Sentry: %s", str(e))


def notify_captcha_error(
    error_message: str,
    request: HttpRequest | None = None,
    provider: str = "CAPTCHA",
    extra_data: dict | None = None,
) -> None:
    site_phrase = _get_site_phrase()
    site_label = _get_site_label()

    full_message = f"CAPTCHA Error ({provider}): {error_message}"

    if is_localhost(request):
        logger.warning("=" * 60)
        logger.warning("CAPTCHA ERROR (localhost)")
        logger.warning("=" * 60)
        logger.warning("Provider: %s", provider)
        logger.warning("Error: %s", error_message)
        if extra_data:
            for key, value in extra_data.items():
                logger.warning("%s: %s", key, value)
        logger.warning("=" * 60)
        return

    admin_email = _get_admin_email()

    if site_label:
        subject = f"Problem with CAPTCHA on {site_label}"
    else:
        subject = "Problem with CAPTCHA"

    body = (
        f"There was a problem with CAPTCHA {site_phrase}. "
        "Please investigate.\n\n"
        f"Provider: {provider}\n"
        f"Error: {error_message}\n"
    )

    if extra_data:
        body += "\nAdditional Information:\n"
        for key, value in extra_data.items():
            body += f"  {key}: {value}\n"

    if admin_email:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=admin_email,
                recipient_list=[admin_email],
                fail_silently=True,
            )
            logger.info("CAPTCHA Error Notification Email Sent to %s", admin_email)
        except Exception as e:
            logger.error("Failed to Send CAPTCHA Error Email: %s", str(e))
    else:
        logger.warning("CAPTCHA Error Occurred: %s", error_message)

    if _is_sentry_configured():
        _report_to_sentry(
            full_message,
            extra_data={
                "provider": provider,
                "site": site_label or "unknown",
                **(extra_data or {}),
            },
        )
        logger.info("CAPTCHA Error Reported to Sentry")
