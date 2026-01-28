from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import include
from django.urls import path
from wagtail import hooks

from contact_form import forms_admin_urls

if TYPE_CHECKING:
    from django.http import HttpRequest


@hooks.register("register_admin_urls", order=-1)
def register_custom_forms_urls() -> list:
    return [
        path("forms/", include(forms_admin_urls)),
    ]


@hooks.register("construct_settings_menu")
def hide_captcha_settings_for_non_admins(request: HttpRequest, menu_items: list) -> None:
    from contact_form.settings import CaptchaSettings

    if not CaptchaSettings.is_user_administrator(request.user):
        menu_items[:] = [item for item in menu_items if item.name != "captchasettings"]
