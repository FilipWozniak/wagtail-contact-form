from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from django.urls import include
from django.urls import path
from wagtail import hooks
from wagtail.models import Site

from contact_form import forms_admin_urls
from contact_form.models import ContactPage

if TYPE_CHECKING:
    from django.http import HttpRequest

logger = logging.getLogger(__name__)


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


@hooks.register("is_request_cacheable")
def prevent_contact_page_cache(request: HttpRequest, is_cacheable: bool) -> bool:

    if not is_cacheable or request.method not in {"GET", "HEAD"}:
        return is_cacheable

    try:
        site = Site.find_for_request(request)
        if site is None:
            return is_cacheable

        relative_path = request.path_info.lstrip("/")
        page_url_path = f"{site.root_page.url_path}{relative_path}"
        if not page_url_path.endswith("/"):
            page_url_path = f"{page_url_path}/"

        if ContactPage.objects.live().filter(url_path=page_url_path).exists():
            return False
    except Exception as exc:
        logger.debug(
            "Couldn't Determine Page Type in Request: %s",
            type(exc).__name__,
        )
        return False

    return is_cacheable
