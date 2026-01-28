from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from wagtail.models import Site

from contact_form.forms import ContactFormBuilder
from contact_form.models import CaptchaProvider
from contact_form.models import ContactPage
from contact_form.settings import CaptchaSettings
from contact_form.turnstile import TurnstileField

if TYPE_CHECKING:
    pass


@pytest.mark.django_db
class TestCaptchaSettings:
    def test_captcha_settings_creation(self) -> None:
        settings = CaptchaSettings.objects.create(
            recaptcha_public_key="test-public-key",
            recaptcha_private_key="test-private-key",
            recaptcha_required_score="0.85",
            recaptcha_domain="www.recaptcha.net",
            turnstile_site_key="test-turnstile-site-key",
            turnstile_secret_key="test-turnstile-secret-key",
            turnstile_theme="dark",
            turnstile_size="compact",
        )
        assert settings.recaptcha_public_key == "test-public-key"
        assert settings.recaptcha_private_key == "test-private-key"
        assert settings.recaptcha_required_score == "0.85"
        assert settings.recaptcha_domain == "www.recaptcha.net"
        assert settings.turnstile_site_key == "test-turnstile-site-key"
        assert settings.turnstile_secret_key == "test-turnstile-secret-key"
        assert settings.turnstile_theme == "dark"
        assert settings.turnstile_size == "compact"

    def test_captcha_settings_defaults(self) -> None:
        settings = CaptchaSettings.objects.create()
        assert settings.recaptcha_required_score == "0.85"
        assert settings.recaptcha_domain == "www.recaptcha.net"
        assert settings.recaptcha_public_key == ""
        assert settings.recaptcha_private_key == ""
        assert settings.turnstile_site_key == ""
        assert settings.turnstile_secret_key == ""
        assert settings.turnstile_theme == "auto"
        assert settings.turnstile_size == "normal"

    def test_get_recaptcha_settings(self) -> None:
        settings = CaptchaSettings.objects.create(
            recaptcha_public_key="test-public",
            recaptcha_private_key="test-private",
            recaptcha_required_score="0.90",
            recaptcha_domain="www.google.com",
        )
        config = settings.get_recaptcha_settings()
        assert config["public_key"] == "test-public"
        assert config["private_key"] == "test-private"
        assert config["required_score"] == "0.90"
        assert config["domain"] == "www.google.com"

    def test_get_turnstile_settings(self) -> None:
        settings = CaptchaSettings.objects.create(
            turnstile_site_key="test-site-key",
            turnstile_secret_key="test-secret-key",
            turnstile_theme="light",
            turnstile_size="compact",
        )
        config = settings.get_turnstile_settings()
        assert config["site_key"] == "test-site-key"
        assert config["secret_key"] == "test-secret-key"
        assert config["theme"] == "light"
        assert config["size"] == "compact"

    def test_str_representation(self) -> None:
        settings = CaptchaSettings.objects.create()
        assert str(settings) == "CAPTCHA Settings"

    def test_save_preserves_existing_sensitive_values_when_empty(self) -> None:
        settings = CaptchaSettings.objects.create(
            turnstile_site_key="original-site-key",
            turnstile_secret_key="original-secret-key",
        )
        settings.turnstile_site_key = ""
        settings.turnstile_secret_key = ""
        settings.save()
        settings.refresh_from_db()
        assert settings.turnstile_site_key == "original-site-key"
        assert settings.turnstile_secret_key == "original-secret-key"

    def test_save_updates_sensitive_values_when_new_value_provided(self) -> None:
        settings = CaptchaSettings.objects.create(
            turnstile_site_key="original-site-key",
            turnstile_secret_key="original-secret-key",
        )
        settings.turnstile_site_key = "new-site-key"
        settings.turnstile_secret_key = "new-secret-key"
        settings.save()
        settings.refresh_from_db()
        assert settings.turnstile_site_key == "new-site-key"
        assert settings.turnstile_secret_key == "new-secret-key"


@pytest.mark.django_db
class TestCaptchaProviderField:
    @pytest.fixture
    def contact_page(self) -> ContactPage:
        page = ContactPage(
            title="Contact Us",
            intro="Test intro",
            thank_you_text="Thank you!",
            from_address="test@example.com",
            to_address="admin@example.com",
            subject="Test Subject",
        )
        home_page = Site.objects.filter(is_default_site=True)[0].root_page
        home_page.add_child(instance=page)
        page.save()
        return page

    def test_default_captcha_provider_is_recaptcha(self, contact_page: ContactPage) -> None:
        assert contact_page.captcha_provider == CaptchaProvider.RECAPTCHA

    def test_can_set_captcha_provider_to_turnstile(self, contact_page: ContactPage) -> None:
        contact_page.captcha_provider = CaptchaProvider.TURNSTILE
        contact_page.save()
        contact_page.refresh_from_db()
        assert contact_page.captcha_provider == CaptchaProvider.TURNSTILE

    def test_captcha_provider_choices(self) -> None:
        choices = CaptchaProvider.choices
        assert ("recaptcha", "Google reCAPTCHA") in choices
        assert ("turnstile", "Cloudflare Turnstile") in choices

    def test_captcha_provider_in_page_context(self, contact_page: ContactPage) -> None:
        request = MagicMock()
        context = contact_page.get_context(request)
        assert "captcha_provider" in context
        assert context["captcha_provider"] == CaptchaProvider.RECAPTCHA


@pytest.mark.django_db
class TestContactFormBuilder:
    @pytest.fixture
    def contact_page(self) -> ContactPage:
        page = ContactPage(
            title="Contact Us",
            intro="Test intro",
            thank_you_text="Thank you!",
            from_address="test@example.com",
            to_address="admin@example.com",
            subject="Test Subject",
        )
        home_page = Site.objects.filter(is_default_site=True)[0].root_page
        home_page.add_child(instance=page)
        page.save()
        return page

    @patch("contact_form.forms.ContactFormBuilder._get_captcha_settings")
    def test_form_builder_with_recaptcha(
        self, mock_get_settings: MagicMock, contact_page: ContactPage
    ) -> None:
        mock_settings = MagicMock()
        mock_settings.get_recaptcha_settings.return_value = {
            "public_key": "test-public-key",
            "private_key": "test-private-key",
            "required_score": "0.85",
            "domain": "www.recaptcha.net",
        }
        mock_get_settings.return_value = mock_settings
        contact_page.captcha_provider = CaptchaProvider.RECAPTCHA
        builder = ContactFormBuilder(contact_page.form_fields.all(), page=contact_page)
        fields = builder.formfields
        assert ContactFormBuilder.CAPTCHA_FIELD_NAME in fields

    @patch("contact_form.forms.ContactFormBuilder._get_captcha_settings")
    def test_form_builder_with_turnstile(
        self, mock_get_settings: MagicMock, contact_page: ContactPage
    ) -> None:
        mock_settings = MagicMock()
        mock_settings.get_turnstile_settings.return_value = {
            "site_key": "test-site-key",
            "secret_key": "test-secret-key",
            "theme": "auto",
            "size": "normal",
        }
        mock_get_settings.return_value = mock_settings
        contact_page.captcha_provider = CaptchaProvider.TURNSTILE
        contact_page.save()
        builder = ContactFormBuilder(contact_page.form_fields.all(), page=contact_page)
        fields = builder.formfields
        assert ContactFormBuilder.CAPTCHA_FIELD_NAME in fields
        captcha_field = fields[ContactFormBuilder.CAPTCHA_FIELD_NAME]
        assert isinstance(captcha_field, TurnstileField)

    def test_form_builder_captcha_field_name(self) -> None:
        assert ContactFormBuilder.CAPTCHA_FIELD_NAME == "wagtailcaptcha"
