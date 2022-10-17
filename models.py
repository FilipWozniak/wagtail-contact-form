import contextlib
import importlib

from django.db import models

from modelcluster.fields import ParentalKey
from wagtail.admin.edit_handlers import (
    FieldPanel,
    FieldRowPanel,
    InlinePanel,
    MultiFieldPanel,
)
from wagtail.core.fields import RichTextField
from wagtail.contrib.forms.models import AbstractFormField, AbstractEmailForm

from wagtailcaptcha.models import WagtailCaptchaEmailForm

# from packaging import version

with contextlib.suppress(ModuleNotFoundError):
    import cjkcms
import wagtail


class FormField(AbstractFormField):
    page = ParentalKey(
        "ContactPage",
        on_delete=models.CASCADE,
        related_name="form_fields",
    )


class ContactPage(WagtailCaptchaEmailForm):
    template = "contact/contact_page.html"
    # This is the default path.
    # If ignored, Wagtail adds _landing.html to your template name
    landing_page_template = "contact/contact_page_landing.html"

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

    def get_context(self, request, *args, **kwargs):
        context = super(ContactPage, self).get_context(request, *args, **kwargs)
        package_name = "cjkcms"

        package_cjkcms = importlib.util.find_spec(package_name)
        if package_cjkcms is None:
            print("Not Installed: " + package_name)
            context["base_template"] = "base.html"
        else:
            if wagtail.VERSION >= (4, 0, 0):
                context["base_template"] = "cjkcms/pages/web_page.html"
            else:
                context["base_template"] = "base.html"
        return context
