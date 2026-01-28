from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

from django.db import models
from django.forms.widgets import PasswordInput
from wagtail.admin.panels import FieldPanel
from wagtail.admin.panels import ObjectList
from wagtail.admin.panels import TabbedInterface
from wagtail.contrib.settings.models import BaseGenericSetting
from wagtail.contrib.settings.models import register_setting

if TYPE_CHECKING:
    from django.http import HttpRequest


class TurnstileTheme(models.TextChoices):
    AUTO = "auto", "Auto"
    LIGHT = "light", "Light"
    DARK = "dark", "Dark"


class TurnstileSize(models.TextChoices):
    NORMAL = "normal", "Normal"
    COMPACT = "compact", "Compact"


class CaptchaSettingsPermissionMixin:
    @classmethod
    def is_user_administrator(cls, user: object) -> bool:
        if not user or not hasattr(user, "is_authenticated"):
            return False
        if not user.is_authenticated:
            return False
        if getattr(user, "is_superuser", False):
            return True
        if hasattr(user, "groups"):
            return user.groups.filter(name="Administrators").exists()
        return False


@register_setting(icon="lock")
class CaptchaSettings(CaptchaSettingsPermissionMixin, BaseGenericSetting):
    class Meta:
        verbose_name = "CAPTCHA"
        verbose_name_plural = "CAPTCHA"

    # Google reCAPTCHA
    recaptcha_public_key = models.CharField(max_length=255, blank=True, default="", verbose_name="Public Key")
    recaptcha_private_key = models.CharField(max_length=255, blank=True, default="", verbose_name="Private Key")
    recaptcha_required_score = models.CharField(max_length=10, blank=True, default="0.85", verbose_name="Required Score")
    recaptcha_domain = models.CharField(max_length=255, blank=True, default="www.recaptcha.net", verbose_name="Domain")

    # Cloudflare Turnstile
    turnstile_site_key = models.CharField(max_length=255, blank=True, default="", verbose_name="Site Key")
    turnstile_secret_key = models.CharField(max_length=255, blank=True, default="", verbose_name="Secret Key")
    turnstile_theme = models.CharField(max_length=10, choices=TurnstileTheme.choices, default=TurnstileTheme.AUTO, verbose_name="Theme")
    turnstile_size = models.CharField(max_length=10, choices=TurnstileSize.choices, default=TurnstileSize.NORMAL, verbose_name="Widget Size")

    edit_handler: ClassVar[TabbedInterface] = TabbedInterface([
        ObjectList([
            FieldPanel("recaptcha_public_key", widget=PasswordInput(attrs={"placeholder": "Leave empty to keep current value"})),
            FieldPanel("recaptcha_private_key", widget=PasswordInput(attrs={"placeholder": "Leave empty to keep current value"})),
            FieldPanel("recaptcha_required_score"),
            FieldPanel("recaptcha_domain"),
        ], heading="Google reCAPTCHA"),
        ObjectList([
            FieldPanel("turnstile_site_key", widget=PasswordInput(attrs={"placeholder": "Leave empty to keep current value"})),
            FieldPanel("turnstile_secret_key", widget=PasswordInput(attrs={"placeholder": "Leave empty to keep current value"})),
            FieldPanel("turnstile_theme"),
            FieldPanel("turnstile_size"),
        ], heading="Cloudflare Turnstile"),
    ])

    SENSITIVE_FIELDS: ClassVar[list[str]] = [
        "recaptcha_public_key",
        "recaptcha_private_key",
        "turnstile_site_key",
        "turnstile_secret_key",
    ]

    @classmethod
    def user_has_permission(cls, request: HttpRequest) -> bool:
        return cls.is_user_administrator(request.user)

    def __str__(self) -> str:
        return "CAPTCHA Settings"

    def get_recaptcha_settings(self) -> dict[str, str]:
        return {
            "public_key": self.recaptcha_public_key,
            "private_key": self.recaptcha_private_key,
            "required_score": self.recaptcha_required_score,
            "domain": self.recaptcha_domain,
        }

    def get_turnstile_settings(self) -> dict[str, str]:
        return {
            "site_key": self.turnstile_site_key,
            "secret_key": self.turnstile_secret_key,
            "theme": self.turnstile_theme,
            "size": self.turnstile_size,
        }

    def save(self, *args: Any, **kwargs: Any) -> None:
        if self.pk:
            try:
                existing = CaptchaSettings.objects.get(pk=self.pk)
                for field_name in self.SENSITIVE_FIELDS:
                    current_value = getattr(self, field_name, "")
                    if not current_value:
                        existing_value = getattr(existing, field_name, "")
                        setattr(self, field_name, existing_value)
            except CaptchaSettings.DoesNotExist:
                pass

        super().save(*args, **kwargs)
