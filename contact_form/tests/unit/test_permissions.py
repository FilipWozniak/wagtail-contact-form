from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from contact_form.settings import CaptchaSettings
from contact_form.wagtail_hooks import hide_captcha_settings_for_non_admins

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


@pytest.mark.django_db
class TestCaptchaSettingsPermissions:
    @pytest.fixture
    def admin_user(self) -> AbstractUser:
        User = get_user_model()
        return User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin_password",
        )

    @pytest.fixture
    def admin_group_user(self) -> AbstractUser:
        User = get_user_model()
        user = User.objects.create_user(
            username="admingroup",
            email="admingroup@example.com",
            password="admin_password",
        )
        admin_group, _ = Group.objects.get_or_create(name="Administrators")
        user.groups.add(admin_group)
        return user

    @pytest.fixture
    def regular_user(self) -> AbstractUser:
        User = get_user_model()
        return User.objects.create_user(
            username="regular",
            email="regular@example.com",
            password="regular_password",
        )

    @pytest.fixture
    def editor_user(self) -> AbstractUser:
        User = get_user_model()
        user = User.objects.create_user(
            username="editor",
            email="editor@example.com",
            password="editor_password",
        )
        editor_group, _ = Group.objects.get_or_create(name="Editors")
        user.groups.add(editor_group)
        return user

    def test_superuser_is_administrator(self, admin_user: AbstractUser) -> None:
        assert CaptchaSettings.is_user_administrator(admin_user) is True

    def test_admin_group_user_is_administrator(self, admin_group_user: AbstractUser) -> None:
        assert CaptchaSettings.is_user_administrator(admin_group_user) is True

    def test_regular_user_is_not_administrator(self, regular_user: AbstractUser) -> None:
        assert CaptchaSettings.is_user_administrator(regular_user) is False

    def test_editor_user_is_not_administrator(self, editor_user: AbstractUser) -> None:
        assert CaptchaSettings.is_user_administrator(editor_user) is False

    def test_anonymous_user_is_not_administrator(self) -> None:
        anonymous = MagicMock()
        anonymous.is_authenticated = False
        assert CaptchaSettings.is_user_administrator(anonymous) is False

    def test_none_user_is_not_administrator(self) -> None:
        assert CaptchaSettings.is_user_administrator(None) is False

    def test_user_has_permission_for_superuser(self, admin_user: AbstractUser) -> None:
        request = MagicMock()
        request.user = admin_user
        assert CaptchaSettings.user_has_permission(request) is True

    def test_user_has_permission_for_admin_group(self, admin_group_user: AbstractUser) -> None:
        request = MagicMock()
        request.user = admin_group_user
        assert CaptchaSettings.user_has_permission(request) is True

    def test_user_has_no_permission_for_regular_user(self, regular_user: AbstractUser) -> None:
        request = MagicMock()
        request.user = regular_user
        assert CaptchaSettings.user_has_permission(request) is False


@pytest.mark.django_db
class TestCaptchaSettingsMenuHook:
    @pytest.fixture
    def admin_user(self) -> AbstractUser:
        User = get_user_model()
        return User.objects.create_superuser(
            username="hookadmin",
            email="hookadmin@example.com",
            password="admin_password",
        )

    @pytest.fixture
    def regular_user(self) -> AbstractUser:
        User = get_user_model()
        return User.objects.create_user(
            username="hookregular",
            email="hookregular@example.com",
            password="regular_password",
        )

    def test_captcha_settings_visible_for_admin(self, admin_user: AbstractUser) -> None:
        request = MagicMock()
        request.user = admin_user
        captcha_item = MagicMock()
        captcha_item.name = "captchasettings"
        other_item = MagicMock()
        other_item.name = "other-settings"
        menu_items = [captcha_item, other_item]
        hide_captcha_settings_for_non_admins(request, menu_items)
        item_names = [item.name for item in menu_items]
        assert "captchasettings" in item_names
        assert len(menu_items) == 2

    def test_captcha_settings_hidden_for_regular_user(self, regular_user: AbstractUser) -> None:
        request = MagicMock()
        request.user = regular_user
        captcha_item = MagicMock()
        captcha_item.name = "captchasettings"
        other_item = MagicMock()
        other_item.name = "other-settings"
        menu_items = [captcha_item, other_item]
        hide_captcha_settings_for_non_admins(request, menu_items)
        item_names = [item.name for item in menu_items]
        assert "captchasettings" not in item_names
        assert "other-settings" in item_names
        assert len(menu_items) == 1

    def test_other_settings_preserved_for_non_admin(self, regular_user: AbstractUser) -> None:
        request = MagicMock()
        request.user = regular_user
        captcha_item = MagicMock()
        captcha_item.name = "captchasettings"
        seo_item = MagicMock()
        seo_item.name = "seo-settings"
        general_item = MagicMock()
        general_item.name = "general-settings"
        menu_items = [captcha_item, seo_item, general_item]
        hide_captcha_settings_for_non_admins(request, menu_items)
        item_names = [item.name for item in menu_items]
        assert "captchasettings" not in item_names
        assert "seo-settings" in item_names
        assert "general-settings" in item_names
        assert len(menu_items) == 2
