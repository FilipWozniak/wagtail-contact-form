from __future__ import absolute_import, unicode_literals

from django_recaptcha.fields import ReCaptchaField
from django_recaptcha.widgets import ReCaptchaV3
from .compat import FormBuilder


class ContactFormBuilder(FormBuilder):
    CAPTCHA_FIELD_NAME = "wagtailcaptcha"

    @property
    def formfields(self):
        fields = super(ContactFormBuilder, self).formfields
        fields[self.CAPTCHA_FIELD_NAME] = ReCaptchaField(label="", widget=ReCaptchaV3())
        return fields


def remove_captcha_field(form):
    if form.is_valid():
        form.fields.pop(ContactFormBuilder.CAPTCHA_FIELD_NAME, None)
        form.cleaned_data.pop(ContactFormBuilder.CAPTCHA_FIELD_NAME, None)
