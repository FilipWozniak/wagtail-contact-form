from __future__ import annotations

from django.apps import AppConfig


class ContactFormConfig(AppConfig):
    default_auto_field: str = "django.db.models.BigAutoField"
    name: str = "contact_form"
    verbose_name: str = "Contact Form"

    def ready(self) -> None:
        try:
            from contact_form import settings  # noqa: F401
        except ImportError:
            pass
