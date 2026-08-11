from __future__ import annotations

import logging
from typing import Any
from typing import ClassVar

import wagtail
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.http import HttpRequest
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.utils.cache import patch_cache_control
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from modelcluster.fields import ParentalKey
from wagtail.admin.panels import FieldPanel
from wagtail.admin.panels import FieldRowPanel
from wagtail.admin.panels import InlinePanel
from wagtail.admin.panels import MultiFieldPanel
from wagtail.contrib.forms.models import AbstractForm
from wagtail.contrib.forms.models import AbstractEmailForm
from wagtail.contrib.forms.models import AbstractFormField
from wagtail.contrib.forms.models import validate_to_address
from wagtail.fields import RichTextField
from wagtail.models import TranslatableMixin

from contact_form.forms import ContactFormBuilder
from contact_form.forms import remove_captcha_field
from contact_form.views import CustomSubmissionsListView

logger = logging.getLogger(__name__)


class ContactFormEmailError(RuntimeError):
    """Raise Error"""


class CaptchaProvider(models.TextChoices):
    RECAPTCHA = "recaptcha", "Google reCAPTCHA"
    TURNSTILE = "turnstile", "Cloudflare Turnstile"


FORM_FIELD_CHOICES = (
    ("singleline", "Single Line Text"),
    ("multiline", "Multi Line Text"),
    ("email", "Email"),
    ("number", "Number"),
    ("url", "URL"),
    ("checkbox", "Checkbox"),
    ("checkboxes", "Checkboxes"),
    ("dropdown", "Dropdown"),
    ("multiselect", "Multiple Select"),
    ("radio", "Radio Buttons"),
    ("date", "Date"),
    ("datetime", "Date/ Time"),
    ("hidden", "Hidden Field"),
)


class FormField(TranslatableMixin, AbstractFormField):
    page: ParentalKey = ParentalKey(
        "ContactPage",
        on_delete=models.CASCADE,
        related_name="form_fields",
    )

    label = models.CharField(
        verbose_name="Label",
        max_length=255,
    )
    field_type = models.CharField(
        verbose_name="Field Type",
        max_length=16,
        choices=FORM_FIELD_CHOICES,
    )
    help_text = models.CharField(
        verbose_name="Help Text",
        max_length=255,
        blank=True,
    )
    default_value = models.TextField(
        verbose_name="Default Value",
        blank=True,
        help_text="Comma or new line separated values supported for checkboxes.",
    )

    class Meta:
        ordering = ["sort_order"]
        constraints = [
            models.UniqueConstraint(
                fields=("translation_key", "locale"),
                name="contact_form_unique_field_translation",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if getattr(self, "locale_id", None) is None and self.page_id:
            setattr(self, "locale_id", self.page.locale_id)
        super().save(*args, **kwargs)


class ContactPage(AbstractEmailForm):
    class Meta:
        verbose_name = "Contact Page"
        verbose_name_plural = "Contact Pages"

    template: ClassVar[str] = "contact_form/contact_page.html"
    landing_page_template: ClassVar[str] = "contact_form/contact_page_landing.html"
    form_builder: type[ContactFormBuilder] = ContactFormBuilder
    submissions_list_view_class = CustomSubmissionsListView
    intro: RichTextField = RichTextField(blank=True)
    thank_you_text: RichTextField = RichTextField(
        blank=True,
        verbose_name="Thank You Message",
    )
    from_address = models.EmailField(
        verbose_name="Address from",
        max_length=255,
        blank=True,
    )
    to_address = models.CharField(
        verbose_name="Address to",
        max_length=255,
        blank=True,
        help_text="The form submissions will be emailed to these addresses. "
        "Please separate multiple recipients by comma.",
        validators=[validate_to_address],
    )

    technical_to_address = models.CharField(
        verbose_name="Address to (Technical)",
        max_length=255,
        blank=True,
        default="",
        help_text="The error messages will be emailed to these addresses. "
        "Please separate multiple recipients by comma.",
        validators=[validate_to_address],
    )
    error_message_throttling = models.PositiveIntegerField(
        verbose_name="Error Message Throttling (in Minutes)",
        default=60,
        validators=[MinValueValidator(1)],
        help_text="The error messages of the same type will not be sent more "
        "frequently than the value specified below.",
    )

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
        MultiFieldPanel(
            [
                FieldPanel("technical_to_address"),
                FieldPanel("error_message_throttling"),
            ],
            heading="Error Handling",
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
        return super().get_form(
            form_data,
            form_files,
            page=page,
            user=user,
        )

    def serve(self, request: HttpRequest, *args: Any, **kwargs: Any) -> Any:
        self._current_request = request

        if request.method != "POST":
            form = self.get_form(page=self, user=request.user)
            return self._protect_contact_response(self._render_contact_form(request, form, *args, **kwargs))

        from contact_form.security import DuplicateContactSubmission
        from contact_form.security import FormSecurityError
        from contact_form.security import SecurityStateUnavailable
        from contact_form.security import ValidatedSubmissionSecurity
        from contact_form.security import consume_post_rate_limit
        from contact_form.security import get_submission_fingerprint
        from contact_form.security import get_submission_nonce_hash
        from contact_form.security import is_submission_nonce_used
        from contact_form.security import is_honeypot_filled
        from contact_form.security import validate_form_security_token

        try:
            rate_decision, client_fingerprint = consume_post_rate_limit(
                page=self,
                request=request,
            )
        except SecurityStateUnavailable:
            form = self.get_form(page=self, user=request.user)
            response = self._render_contact_form(
                request,
                form,
                *args,
                security_error=_("The form is temporarily unavailable. Please try again later."),
                status=503,
                **kwargs,
            )
            return self._protect_contact_response(response)

        if not rate_decision.allowed:
            form = self.get_form(page=self, user=request.user)
            response = self._render_contact_form(
                request,
                form,
                *args,
                security_error=_("You submitted the form too frequently. Please wait and try again."),
                status=429,
                **kwargs,
            )
            response["Retry-After"] = str(rate_decision.retry_after_seconds)
            return self._protect_contact_response(response)

        try:
            token_payload = validate_form_security_token(
                page=self,
                token=str(request.POST.get("_contact_form_token", "")),
            )
        except FormSecurityError:
            form = self.get_form(page=self, user=request.user)
            response = self._render_contact_form(
                request,
                form,
                *args,
                security_error=_("We could not verify this form. Please reload the page and try again."),
                status=400,
                **kwargs,
            )
            return self._protect_contact_response(response)

        if is_honeypot_filled(request, token_payload):
            return self._protect_contact_response(self.render_landing_page(request, None, *args, **kwargs))

        nonce_hash = get_submission_nonce_hash(
            page=self,
            nonce=token_payload.nonce,
        )
        try:
            nonce_was_used = is_submission_nonce_used(
                page=self,
                nonce_hash=nonce_hash,
            )
        except SecurityStateUnavailable:
            form = self.get_form(page=self, user=request.user)
            response = self._render_contact_form(
                request,
                form,
                *args,
                security_error=_("The form is temporarily unavailable. Please try again later."),
                status=503,
                **kwargs,
            )
            return self._protect_contact_response(response)

        if nonce_was_used:
            return self._protect_contact_response(self.render_landing_page(request, None, *args, **kwargs))

        form = self.get_form(
            request.POST,
            request.FILES,
            page=self,
            user=request.user,
            request=request,
        )
        if form.is_valid():
            form._contact_form_security = ValidatedSubmissionSecurity(
                nonce_hash=nonce_hash,
                submission_fingerprint=get_submission_fingerprint(
                    page=self,
                    form=form,
                    client_fingerprint=client_fingerprint,
                ),
            )
            try:
                form_submission = self.process_form_submission(form)
            except DuplicateContactSubmission:
                form_submission = None
            except ContactFormEmailError as exc:
                cause = exc.__cause__ or exc
                logger.error(
                    "Error with Sending an Email exception_type=%s",
                    type(cause).__name__,
                )
                response = self._render_contact_form(
                    request,
                    form,
                    *args,
                    security_error=_("The form is temporarily unavailable. Please try again later."),
                    status=503,
                    **kwargs,
                )
                return self._protect_contact_response(response)
            return self._protect_contact_response(
                self.render_landing_page(
                    request,
                    form_submission,
                    *args,
                    **kwargs,
                )
            )

        return self._protect_contact_response(self._render_contact_form(request, form, *args, **kwargs))

    def process_form_submission(self, form: Any) -> Any:
        from contact_form.security import DuplicateContactSubmission
        from contact_form.security import SecurityStateUnavailable
        from contact_form.security import ValidatedSubmissionSecurity
        from contact_form.security import release_duplicate_submission
        from contact_form.security import release_submission_nonce
        from contact_form.security import reserve_duplicate_submission
        from contact_form.security import reserve_submission_nonce

        submission_security = getattr(form, "_contact_form_security", None)
        if not isinstance(submission_security, ValidatedSubmissionSecurity):
            raise RuntimeError("Validated CONTACT_FORM security context is required.")

        captcha_name = ContactFormBuilder.CAPTCHA_FIELD_NAME
        captcha_field = form.fields.get(captcha_name)
        captcha_value_exists = captcha_name in form.cleaned_data
        captcha_value = form.cleaned_data.get(captcha_name)
        nonce_reserved = False
        duplicate_reserved = False
        captcha_removed = False

        try:
            nonce_decision = reserve_submission_nonce(
                page=self,
                nonce_hash=submission_security.nonce_hash,
            )
            if not nonce_decision.allowed:
                raise DuplicateContactSubmission
            nonce_reserved = True

            duplicate_decision = reserve_duplicate_submission(
                page=self,
                submission_fingerprint=submission_security.submission_fingerprint,
            )
            if not duplicate_decision.allowed:
                raise DuplicateContactSubmission
            duplicate_reserved = True

            remove_captcha_field(form)
            captcha_removed = True

            with transaction.atomic():
                submission = AbstractForm.process_form_submission(self, form)
                if self.to_address:
                    try:
                        self.send_mail(form)
                    except Exception as exc:
                        raise ContactFormEmailError from exc
        except DuplicateContactSubmission:
            raise
        except Exception:
            if captcha_removed:
                if captcha_field is not None:
                    form.fields[captcha_name] = captcha_field
                if captcha_value_exists:
                    form.cleaned_data[captcha_name] = captcha_value

            if duplicate_reserved:
                try:
                    release_duplicate_submission(
                        page=self,
                        submission_fingerprint=submission_security.submission_fingerprint,
                    )
                except SecurityStateUnavailable as exc:
                    logger.warning(
                        "Couldn't release duplicate-submission cache state: exception_type=%s",
                        type(exc).__name__,
                    )
            if nonce_reserved:
                try:
                    release_submission_nonce(
                        page=self,
                        nonce_hash=submission_security.nonce_hash,
                    )
                except SecurityStateUnavailable as exc:
                    logger.warning(
                        "Couldn't release submission-nonce cache state: exception_type=%s",
                        type(exc).__name__,
                    )
            raise

        return submission

    def _render_contact_form(
        self,
        request: HttpRequest,
        form: Any,
        *args: Any,
        security_error: Any | None = None,
        status: int = 200,
        **kwargs: Any,
    ) -> TemplateResponse:
        context = self.get_context(request, *args, **kwargs)
        context["form"] = form
        if security_error:
            context["security_error"] = security_error
        return TemplateResponse(
            request,
            self.get_template(request),
            context,
            status=status,
        )

    def _protect_contact_response(self, response: HttpResponse) -> HttpResponse:
        request = getattr(self, "_current_request", None)
        if request is not None:
            setattr(request, "_wagtailcache_skip", True)
        patch_cache_control(
            response,
            private=True,
            no_cache=True,
            no_store=True,
            must_revalidate=True,
            max_age=0,
        )
        return response

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
        from contact_form.security import issue_form_security_token

        security_token, honeypot_name = issue_form_security_token(self)
        context["form_security_token"] = security_token
        context["form_honeypot_name"] = honeypot_name
        return context


try:
    from wagtail_localize.fields import SynchronizedField
    from wagtail_localize.fields import TranslatableField
except ModuleNotFoundError:
    pass
else:
    FormField.translatable_fields = [
        SynchronizedField("clean_name", overridable=False),
        TranslatableField("label"),
        SynchronizedField("field_type", overridable=False),
        SynchronizedField("required", overridable=False),
        TranslatableField("choices"),
        TranslatableField("default_value"),
        TranslatableField("help_text"),
        SynchronizedField("sort_order", overridable=False),
    ]
    ContactPage.override_translatable_fields = [
        SynchronizedField("to_address", overridable=True),
        SynchronizedField("technical_to_address", overridable=True),
        SynchronizedField("captcha_provider", overridable=True),
        SynchronizedField("error_message_throttling", overridable=True),
    ]
