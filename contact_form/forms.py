from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from wagtail.contrib.forms.forms import FormBuilder

from contact_form.utils import get_captcha_keys_for_environment
from contact_form.utils import is_localhost

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from contact_form.models import ContactPage
    from contact_form.models import FormField

logger = logging.getLogger(__name__)


class CaptchaConfigurationField(forms.Field):
    default_error_messages = {
        "unavailable": _("The security check is temporarily unavailable. Please try again later."),
    }

    def __init__(
        self,
        *,
        provider: str,
        error_message: str,
        page: ContactPage | None,
        request: HttpRequest | None,
    ) -> None:
        self.provider = provider
        self.error_message = error_message
        self.page = page
        self.request = request
        super().__init__(
            label="",
            required=False,
            widget=forms.HiddenInput(),
        )

    def clean(self, value: Any) -> Any:
        try:
            from contact_form.notifications import notify_captcha_error

            notify_captcha_error(
                error_message=self.error_message,
                request=self.request,
                page=self.page,
                provider=self.provider,
                error_key=f"{self.provider.casefold().replace(' ', '-')}.configuration.unavailable",
            )
        except Exception as exc:
            logger.debug(
                "Failed to report unavailable CAPTCHA configuration: %s",
                type(exc).__name__,
            )
        raise ValidationError(
            self.error_messages["unavailable"],
            code="captcha_unavailable",
        )


def _get_turnstile_allowed_hostnames(
    request: HttpRequest | None,
) -> tuple[str, ...]:
    configured_hostnames = getattr(settings, "TURNSTILE_ALLOWED_HOSTNAMES", ())
    if isinstance(configured_hostnames, str):
        hostnames = tuple(hostname.strip() for hostname in configured_hostnames.split(",") if hostname.strip())
    elif isinstance(configured_hostnames, Iterable):
        hostnames = tuple(str(hostname).strip() for hostname in configured_hostnames if str(hostname).strip())
    else:
        hostnames = ()

    if hostnames or request is None:
        return hostnames

    discovered_hostnames: list[str] = []
    site = getattr(request, "site", None)
    site_hostname = getattr(site, "hostname", None)
    if isinstance(site_hostname, str) and site_hostname.strip():
        discovered_hostnames.append(site_hostname.strip())

    try:
        request_hostname = request.get_host()
    except DisallowedHost:
        request_hostname = ""

    if request_hostname and request_hostname not in discovered_hostnames:
        discovered_hostnames.append(request_hostname)

    return tuple(discovered_hostnames)


class ContactFormBuilder(FormBuilder):
    CAPTCHA_FIELD_NAME: str = "wagtailcaptcha"

    def __init__(
        self,
        fields: QuerySet[FormField],
        page: ContactPage | None = None,
        request: HttpRequest | None = None,
    ) -> None:
        super().__init__(fields)
        self.page = page
        self.request = request
        self._is_localhost = is_localhost(request) if request else False

    @property
    def formfields(self) -> dict[str, forms.Field]:
        fields = super().formfields
        captcha_field = self._get_captcha_field()
        if captcha_field:
            fields[self.CAPTCHA_FIELD_NAME] = captcha_field
        return fields

    def _get_captcha_field(self) -> forms.Field:
        captcha_provider = getattr(self.page, "captcha_provider", "recaptcha")

        if captcha_provider == "turnstile":
            return self._get_turnstile_field()
        else:
            return self._get_recaptcha_field()

    def _get_recaptcha_field(self) -> forms.Field:
        try:
            from django_recaptcha.fields import ReCaptchaField
            from django_recaptcha.widgets import ReCaptchaV3

            captcha_settings = self._get_captcha_settings()
            configured_keys: dict[str, str] = {"site_key": "", "secret_key": ""}

            if captcha_settings:
                recaptcha_config = captcha_settings.get_recaptcha_settings()
                configured_keys = {
                    "site_key": recaptcha_config.get("public_key", ""),
                    "secret_key": recaptcha_config.get("private_key", ""),
                }

            keys = get_captcha_keys_for_environment("recaptcha", self.request, configured_keys)
            site_key = keys["site_key"]
            secret_key = keys["secret_key"]

            if not site_key or not secret_key:
                logger.warning(
                    "reCAPTCHA keys not configured. "
                    "Please configure keys in Settings > CAPTCHA."
                )
                return CaptchaConfigurationField(
                    provider="Google reCAPTCHA",
                    error_message="reCAPTCHA Not Configured",
                    page=self.page,
                    request=self.request,
                )

            settings.RECAPTCHA_PUBLIC_KEY = site_key
            settings.RECAPTCHA_PRIVATE_KEY = secret_key

            if captcha_settings:
                recaptcha_config = captcha_settings.get_recaptcha_settings()
                if recaptcha_config.get("required_score"):
                    try:
                        settings.RECAPTCHA_REQUIRED_SCORE = float(recaptcha_config["required_score"])
                    except (ValueError, TypeError):
                        settings.RECAPTCHA_REQUIRED_SCORE = 0.85
                if recaptcha_config.get("domain"):
                    settings.RECAPTCHA_DOMAIN = recaptcha_config["domain"]

            return ReCaptchaField(label="", widget=ReCaptchaV3())
        except ImportError:
            logger.warning("Package django-recaptcha is Not Installed")
            return CaptchaConfigurationField(
                provider="Google reCAPTCHA",
                error_message="django-recaptcha Package Is Not Installed",
                page=self.page,
                request=self.request,
            )

    def _get_turnstile_field(self) -> forms.Field:
        try:
            from contact_form.security import get_client_ip
            from contact_form.turnstile import TURNSTILE_ACTION
            from contact_form.turnstile import TurnstileField

            captcha_settings = self._get_captcha_settings()
            configured_keys: dict[str, str] = {"site_key": "", "secret_key": ""}
            theme = "auto"
            size = "normal"

            if captcha_settings:
                turnstile_config = captcha_settings.get_turnstile_settings()
                configured_keys = {
                    "site_key": turnstile_config.get("site_key", ""),
                    "secret_key": turnstile_config.get("secret_key", ""),
                }
                theme = turnstile_config.get("theme", "auto")
                size = turnstile_config.get("size", "normal")

            if not configured_keys.get("site_key") or not configured_keys.get("secret_key"):
                configured_keys = {
                    "site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
                    "secret_key": getattr(settings, "TURNSTILE_SECRET_KEY", ""),
                }
                theme = getattr(settings, "TURNSTILE_THEME", theme)
                size = getattr(settings, "TURNSTILE_SIZE", size)

            keys = get_captcha_keys_for_environment("turnstile", self.request, configured_keys)
            site_key = keys["site_key"]
            secret_key = keys["secret_key"]

            if not site_key or not secret_key:
                logger.warning("Turnstile keys not configured.")
                return CaptchaConfigurationField(
                    provider="Cloudflare Turnstile",
                    error_message="Turnstile Keys Not Configured",
                    page=self.page,
                    request=self.request,
                )

            return TurnstileField(
                site_key=site_key,
                secret_key=secret_key,
                theme=theme,
                size=size,
                remote_ip=(get_client_ip(self.request) if self.request is not None else None),
                request=self.request,
                page=self.page,
                expected_hostnames=_get_turnstile_allowed_hostnames(self.request),
                expected_action=TURNSTILE_ACTION,
                label="",
            )

        except ImportError as e:
            logger.error("Failed to Import TurnstileField: %s", str(e))
            return CaptchaConfigurationField(
                provider="Cloudflare Turnstile",
                error_message="Turnstile Integration is Not Available",
                page=self.page,
                request=self.request,
            )

    def _get_captcha_settings(self) -> Any | None:
        try:
            from contact_form.settings import CaptchaSettings

            return CaptchaSettings.load()
        except Exception:
            return None


def remove_captcha_field(form: forms.Form) -> None:
    if form.is_valid():
        form.fields.pop(ContactFormBuilder.CAPTCHA_FIELD_NAME, None)
        form.cleaned_data.pop(ContactFormBuilder.CAPTCHA_FIELD_NAME, None)
