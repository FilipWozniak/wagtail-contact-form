from __future__ import annotations

import contextlib
from typing import Any
from typing import ClassVar

import wagtail
from django.conf import settings
from django.db import models
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel
from wagtail.admin.panels import FieldRowPanel
from wagtail.admin.panels import InlinePanel
from wagtail.admin.panels import MultiFieldPanel
from wagtail.contrib.forms.models import AbstractEmailForm
from wagtail.contrib.forms.models import AbstractFormField
from wagtail.fields import RichTextField

from contact_form.forms import ContactFormBuilder
from contact_form.forms import remove_captcha_field

with contextlib.suppress(ModuleNotFoundError):
    pass


class CaptchaProvider(models.TextChoices):
    RECAPTCHA = "recaptcha", "Google reCAPTCHA"
    TURNSTILE = "turnstile", "Cloudflare Turnstile"


class FormField(AbstractFormField):
    page: ParentalKey = ParentalKey(
        "ContactPage",
        on_delete=models.CASCADE,
        related_name="form_fields",
    )


class ContactPage(AbstractEmailForm):
    template: ClassVar[str] = "contact_form/contact_page.html"
    landing_page_template: ClassVar[str] = "contact_form/contact_page_landing.html"
    form_builder: type[ContactFormBuilder] = ContactFormBuilder
    intro: RichTextField = RichTextField(blank=True)
    thank_you_text: RichTextField = RichTextField(blank=True)

    captcha_provider: models.CharField = models.CharField(
        max_length=20,
        choices=CaptchaProvider.choices,
        default=CaptchaProvider.RECAPTCHA,
        verbose_name="CAPTCHA Provider",
        help_text=mark_safe(
            'Please remember to <a href="/backend/settings/contact_form/captchasettings/1/" '
            'target="_blank">configure the settings</a>.'
        ),
    )

    content_panels: ClassVar[list] = AbstractEmailForm.content_panels + [
        FieldPanel("intro"),
        InlinePanel("form_fields", label="Form Fields"),
        FieldPanel("thank_you_text"),
        MultiFieldPanel(
            [
                FieldRowPanel(
                    [
                        FieldPanel("from_address", classname="col6"),
                        FieldPanel("to_address", classname="col6"),
                    ]
                ),
                FieldPanel("subject"),
            ],
            heading="Email Settings",
        ),
        MultiFieldPanel(
            [
                FieldPanel("captcha_provider"),
            ],
            heading="Provider",
        ),
    ]

    def get_form_class_for_request(self, request: HttpRequest | None = None) -> type:
        fb = self.form_builder(self.form_fields.all(), page=self, request=request)
        return fb.get_form_class()

    def get_form_class(self) -> type:
        request = getattr(self, "_current_request", None)
        return self.get_form_class_for_request(request)

    def get_form(
        self,
        form_data: dict[str, Any] | None = None,
        form_files: dict[str, Any] | None = None,
        page: Any = None,
        user: Any = None,
        request: HttpRequest | None = None,
    ) -> Any:
        if request:
            self._current_request = request
        return super().get_form(form_data, form_files, page, user)

    def serve(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        self._current_request = request
        return super().serve(request, *args, **kwargs)

    def process_form_submission(self, form: Any) -> Any:
        remove_captcha_field(form)
        return super(ContactPage, self).process_form_submission(form)

    def get_context(self, request: HttpRequest, *args: Any, **kwargs: Any) -> dict[str, Any]:
        context = super(ContactPage, self).get_context(request, *args, **kwargs)
        self.seo_pagetitle = self.seo_title
        self.seo_description = self.search_description

        package = "cjkcms"
        if package in settings.INSTALLED_APPS and wagtail.VERSION[0] >= 4:
            context["base_template"] = "cjkcms/pages/web_page.html"
        else:
            context["base_template"] = "base.html"

        context["captcha_provider"] = self.captcha_provider
        return context
