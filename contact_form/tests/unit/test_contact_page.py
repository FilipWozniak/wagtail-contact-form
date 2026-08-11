from __future__ import annotations

import smtplib
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.core import mail
from django.test import RequestFactory
from wagtail.contrib.forms.models import FormSubmission
from wagtail.models import Locale
from wagtail.models import Site

from contact_form.models import CaptchaProvider
from contact_form.models import ContactPage
from contact_form.models import FormField
from contact_form.settings import CaptchaSettings
from contact_form.wagtail_hooks import prevent_contact_page_cache


@pytest.fixture
def form_submission_data() -> dict[str, str]:
    return {
        "full_name": "John Doe",
        "e_mail_address": "john@example.com",
        "message": "This is a test message.",
    }


def create_standard_fields(page: ContactPage) -> None:
    FormField.objects.create(
        page=page,
        sort_order=1,
        label="Full Name",
        field_type="singleline",
        required=True,
    )
    FormField.objects.create(
        page=page,
        sort_order=2,
        label="E-Mail Address",
        field_type="email",
        required=True,
    )
    FormField.objects.create(
        page=page,
        sort_order=3,
        label="Message",
        field_type="multiline",
        required=True,
    )


def securely_post_form(
    *,
    client: Any,
    page: ContactPage,
    data: dict[str, str],
    issued_at: float = 100.0,
    submitted_at: float = 104.0,
    honeypot_value: str = "",
    captcha_token: str | None = "valid-test-token",
) -> tuple[Any, dict[str, str]]:
    with patch("contact_form.security.time.time") as mocked_time:
        mocked_time.return_value = issued_at
        form_page_response = client.get(page.url)
        post_data = {
            **data,
            "_contact_form_token": form_page_response.context["form_security_token"],
            form_page_response.context["form_honeypot_name"]: honeypot_value,
        }
        if captcha_token is not None:
            post_data["cf-turnstile-response"] = captcha_token
        mocked_time.return_value = submitted_at
        response = client.post(page.url, post_data)
    return response, post_data


@pytest.mark.django_db
class TestContactPage:
    @pytest.fixture
    def contact_page(self) -> ContactPage:
        page = ContactPage(
            title="Contact Us",
            intro=("We're here to help and answer any questions you might have. We look forward to hearing from you."),
            thank_you_text="Thank you for your submission!",
            from_address="forms@example.com",
            to_address="normal@example.com",
            technical_to_address="technical@example.com",
            subject="Message from the Website (Contact Form)",
        )
        home_page = Site.objects.get(is_default_site=True).root_page
        home_page.add_child(instance=page)
        return page

    @pytest.fixture
    def contact_page_with_fields(self, contact_page: ContactPage) -> ContactPage:
        create_standard_fields(contact_page)
        contact_page.captcha_provider = CaptchaProvider.TURNSTILE
        contact_page.save(update_fields=("captcha_provider",))
        CaptchaSettings.objects.update_or_create(
            defaults={
                "turnstile_site_key": "configured-site-key",
                "turnstile_secret_key": "configured-secret-key",
            }
        )
        return contact_page

    @pytest.fixture
    def verified_turnstile(self) -> Any:
        with patch(
            "contact_form.turnstile.TurnstileField._verify_turnstile",
            return_value=(True, ""),
        ) as verifier:
            yield verifier

    def test_contact_page_get_is_private_and_contains_security_fields(
        self,
        client: Any,
        contact_page: ContactPage,
    ) -> None:
        response = client.get(contact_page.url)
        assert response.status_code == 200
        assert "private" in response["Cache-Control"]
        assert "no-store" in response["Cache-Control"]
        assert response.context["form_security_token"]
        assert response.context["form_honeypot_name"].startswith("_contact_")
        assert response.context["form_honeypot_name"].encode() in response.content

    def test_contact_page_is_excluded_from_wagtail_shared_cache(
        self,
        rf: RequestFactory,
        contact_page: ContactPage,
    ) -> None:
        request = rf.get(contact_page.url)

        assert prevent_contact_page_cache(request, True) is False

    def test_cache_hook_fails_closed_when_page_lookup_is_unavailable(
        self,
        rf: RequestFactory,
    ) -> None:
        request = rf.get("/contact-us/")

        with patch("contact_form.wagtail_hooks.Site.find_for_request", side_effect=RuntimeError):
            assert prevent_contact_page_cache(request, True) is False

    def test_contact_page_error_handling_defaults_and_panel_order(
        self,
        contact_page: ContactPage,
    ) -> None:
        assert contact_page.technical_to_address == "technical@example.com"
        assert contact_page.error_message_throttling == 60
        headings = [panel.heading for panel in contact_page.content_panels if getattr(panel, "heading", None)]
        assert headings.index("Error Handling") == headings.index("Provider") + 1

    def test_create_form_fields_assigns_parent_locale(
        self,
        contact_page: ContactPage,
    ) -> None:
        create_standard_fields(contact_page)
        fields = list(contact_page.form_fields.all())
        assert [field.label for field in fields] == [
            "Full Name",
            "E-Mail Address",
            "Message",
        ]
        assert all(field.locale_id == contact_page.locale_id for field in fields)
        assert all(field.translation_key for field in fields)

    def test_translation_can_override_provider_and_form_field_labels(
        self,
        contact_page: ContactPage,
    ) -> None:
        create_standard_fields(contact_page)
        polish_locale = Locale.objects.create(language_code="pl")

        translated_page = contact_page.copy_for_translation(
            polish_locale,
            copy_parents=True,
        ).specific
        translated_page.captcha_provider = CaptchaProvider.TURNSTILE
        translated_fields = list(translated_page.form_fields.all())
        translated_fields[0].label = "Imię i Nazwisko"
        translated_fields[0].save(update_fields=("label",))
        translated_page.save_revision().publish()

        contact_page.refresh_from_db()
        translated_page.refresh_from_db()
        source_fields = list(contact_page.form_fields.all())
        translated_fields = list(translated_page.form_fields.all())
        assert contact_page.captcha_provider == CaptchaProvider.RECAPTCHA
        assert translated_page.captcha_provider == CaptchaProvider.TURNSTILE
        assert source_fields[0].label == "Full Name"
        assert translated_fields[0].label == "Imię i Nazwisko"
        assert translated_fields[0].locale_id == polish_locale.pk
        assert translated_fields[0].translation_key == source_fields[0].translation_key

    def test_custom_base_template(
        self,
        client: Any,
        contact_page: ContactPage,
    ) -> None:
        response = client.get(contact_page.url)
        assert "base.html" in [template.name for template in response.templates]

    def test_turnstile_validation_error_is_visible(
        self,
        client: Any,
        contact_page: ContactPage,
        form_submission_data: dict[str, str],
    ) -> None:
        contact_page.captcha_provider = "turnstile"
        contact_page.save(update_fields=["captcha_provider"])
        CaptchaSettings.objects.update_or_create(
            defaults={
                "turnstile_site_key": "configured-site-key",
                "turnstile_secret_key": "configured-secret-key",
            }
        )
        create_standard_fields(contact_page)

        response, _post_data = securely_post_form(
            client=client,
            page=contact_page,
            data=form_submission_data,
            captcha_token=None,
        )

        assert response.status_code == 200
        assert b"Please complete the CAPTCHA verification." in response.content
        assert b"data-turnstile-status" in response.content
