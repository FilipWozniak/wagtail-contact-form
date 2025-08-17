import contextlib

import wagtail
from django.conf import settings
from django.db import models
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
)
from wagtail.contrib.forms.models import AbstractEmailForm, AbstractFormField
from wagtail.fields import RichTextField

from .forms import ContactFormBuilder, remove_captcha_field

with contextlib.suppress(ModuleNotFoundError):
    import cjkcms


class FormField(AbstractFormField):
    page = ParentalKey(
        "ContactPage",
        on_delete=models.CASCADE,
        related_name="form_fields",
    )


class ContactPage(AbstractEmailForm):

    template = "contact_form/contact_page.html"
    landing_page_template = "contact_form/contact_page_landing.html"

    form_builder = ContactFormBuilder

    intro = RichTextField(blank=True)
    thank_you_text = RichTextField(blank=True)

    content_panels = AbstractEmailForm.content_panels + [
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
    ]

    def process_form_submission(self, form):
        remove_captcha_field(form)
        return super(ContactPage, self).process_form_submission(form)

    def get_context(self, request, *args, **kwargs):
        context = super(ContactPage, self).get_context(request, *args, **kwargs)
        self.seo_pagetitle = self.seo_title
        self.seo_description = self.search_description

        package = "cjkcms"
        if package in settings.INSTALLED_APPS and wagtail.VERSION[0] >= 4:
            context["base_template"] = "cjkcms/pages/web_page.html"
        else:
            context["base_template"] = "base.html"
        return context
