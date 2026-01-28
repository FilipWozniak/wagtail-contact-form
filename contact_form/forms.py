from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.conf import settings
from wagtail.contrib.forms.forms import FormBuilder

from contact_form.utils import get_captcha_keys_for_environment
from contact_form.utils import is_localhost

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from contact_form.models import ContactPage
    from contact_form.models import FormField

logger = logging.getLogger(__name__)


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

    def _get_captcha_field(self) -> forms.Field | None:
        captcha_provider = getattr(self.page, "captcha_provider", "recaptcha")

        if captcha_provider == "turnstile":
            return self._get_turnstile_field()
        else:
            return self._get_recaptcha_field()

    def _get_recaptcha_field(self) -> forms.Field | None:
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
                settings.RECAPTCHA_PUBLIC_KEY = keys["site_key"]
                settings.RECAPTCHA_PRIVATE_KEY = keys["secret_key"]
                if recaptcha_config.get("required_score"):
                    try:
                        settings.RECAPTCHA_REQUIRED_SCORE = float(
                            recaptcha_config["required_score"]
                        )
                    except (ValueError, TypeError):
                        settings.RECAPTCHA_REQUIRED_SCORE = 0.85
                if recaptcha_config.get("domain"):
                    settings.RECAPTCHA_DOMAIN = recaptcha_config["domain"]
            elif self._is_localhost:
                keys = get_captcha_keys_for_environment("recaptcha", self.request, None)
                settings.RECAPTCHA_PUBLIC_KEY = keys["site_key"]
                settings.RECAPTCHA_PRIVATE_KEY = keys["secret_key"]
            return ReCaptchaField(label="", widget=ReCaptchaV3())
        except ImportError:
            logger.warning("Package django-recaptcha is Not Installed")
            return None

    def _get_turnstile_field(self) -> forms.Field | None:
        try:
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
            else:
                configured_keys = {
                    "site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
                    "secret_key": getattr(settings, "TURNSTILE_SECRET_KEY", ""),
                }
                theme = getattr(settings, "TURNSTILE_THEME", "auto")
                size = getattr(settings, "TURNSTILE_SIZE", "normal")

            keys = get_captcha_keys_for_environment("turnstile", self.request, configured_keys)
            site_key = keys["site_key"]
            secret_key = keys["secret_key"]

            if not site_key or not secret_key:
                logger.warning("Turnstile Keys Not Configured")
                return None

            return TurnstileField(
                site_key=site_key,
                secret_key=secret_key,
                theme=theme,
                size=size,
                request=self.request,
                label="",
            )

        except ImportError as e:
            logger.error("Failed to Import TurnstileField: %s", str(e))
            return None

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
