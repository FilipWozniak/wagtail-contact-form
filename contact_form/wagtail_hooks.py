from __future__ import annotations

from typing import TYPE_CHECKING

from django.urls import path
from wagtail import hooks
from wagtail.contrib.forms.views import DeleteSubmissionsView
from wagtail.contrib.forms.views import get_submissions_list_view

from contact_form.views import CustomFormPagesListView

if TYPE_CHECKING:
    from django.http import HttpRequest


@hooks.register("register_admin_urls", order=-1)
def register_custom_forms_urls() -> list:
    return [
        path("forms/", CustomFormPagesListView.as_view(), name="wagtailforms:index"),
        path(
            "forms/results/",
            CustomFormPagesListView.as_view(results_only=True),
            name="wagtailforms:index_results",
        ),
        path(
            "forms/submissions/<int:page_id>/",
            get_submissions_list_view,
            name="wagtailforms:list_submissions",
        ),
        path(
            "forms/submissions/<int:page_id>/results/",
            get_submissions_list_view,
            {"results_only": True},
            name="wagtailforms:list_submissions_results",
        ),
        path(
            "forms/submissions/<int:page_id>/delete/",
            DeleteSubmissionsView.as_view(),
            name="wagtailforms:delete_submissions",
        ),
    ]


@hooks.register("construct_settings_menu")
def hide_captcha_settings_for_non_admins(request: HttpRequest, menu_items: list) -> None:
    from contact_form.settings import CaptchaSettings

    if not CaptchaSettings.is_user_administrator(request.user):
        menu_items[:] = [item for item in menu_items if item.name != "captchasettings"]
