from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from collections.abc import Mapping
from typing import TYPE_CHECKING
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from contact_form.utils import TURNSTILE_TEST_SECRET_KEY
from contact_form.utils import TURNSTILE_TEST_SITE_KEY
from contact_form.utils import is_localhost

if TYPE_CHECKING:
    from django.http import HttpRequest

    from contact_form.models import ContactPage

logger = logging.getLogger(__name__)

TURNSTILE_ACTION = "contact_form"
TURNSTILE_RESPONSE_FIELD_NAME = "cf-turnstile-response"
TURNSTILE_TOKEN_MAX_LENGTH = 2048
TURNSTILE_VERIFY_TIMEOUT_SECONDS = 10
TURNSTILE_VERIFY_RESPONSE_MAX_BYTES = 65_536


def _normalize_hostname(hostname: str) -> str:
    candidate = hostname.strip()
    if not candidate:
        return ""

    try:
        parsed = urllib.parse.urlsplit(candidate if "://" in candidate else f"//{candidate}")
        normalized = (parsed.hostname or candidate).rstrip(".").lower()
        return normalized.encode("idna").decode("ascii")
    except (UnicodeError, ValueError):
        return ""


class TurnstileWidget(forms.Widget):
    template_name = "contact_form/widgets/turnstile.html"

    def __init__(
        self,
        site_key: str = "",
        theme: str = "auto",
        size: str = "normal",
        action: str = TURNSTILE_ACTION,
        attrs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(attrs=attrs)
        self.site_key = site_key
        self.theme = theme
        self.size = size
        self.action = action

    def get_context(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None,
    ) -> dict[str, Any]:
        context = super().get_context(name, value, attrs)
        context["widget"].update(
            {
                "site_key": self.site_key,
                "theme": self.theme,
                "size": self.size,
                "action": self.action,
                "response_field_name": TURNSTILE_RESPONSE_FIELD_NAME,
            }
        )
        return context

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> str:
        if self.site_key == TURNSTILE_TEST_SITE_KEY:
            logger.info("Turnstile in Localhost Mode")

        return super().render(name, value, attrs=attrs, renderer=renderer)

    def value_from_datadict(
        self,
        data: Mapping[str, Any],
        files: Mapping[str, Any],
        name: str,
    ) -> str | None:
        value = data.get(TURNSTILE_RESPONSE_FIELD_NAME)
        return value if isinstance(value, str) else None


class TurnstileField(forms.Field):
    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    default_error_messages = {
        "required": _("Please complete the CAPTCHA verification."),
        "invalid": _("CAPTCHA verification failed. Please try again."),
    }

    def __init__(
        self,
        site_key: str = "",
        secret_key: str = "",
        theme: str = "auto",
        size: str = "normal",
        remote_ip: str | None = None,
        request: HttpRequest | None = None,
        page: ContactPage | None = None,
        expected_hostnames: Iterable[str] | None = None,
        expected_action: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.secret_key = secret_key
        self.remote_ip = remote_ip
        self.request = request
        self.page = page
        self.expected_action = expected_action
        hostname_values = (expected_hostnames,) if isinstance(expected_hostnames, str) else expected_hostnames or ()
        self.expected_hostnames = frozenset(
            normalized for hostname in hostname_values if (normalized := _normalize_hostname(hostname))
        )
        self._uses_test_keys = (
            site_key == TURNSTILE_TEST_SITE_KEY
            and secret_key == TURNSTILE_TEST_SECRET_KEY
            and request is not None
            and is_localhost(request)
        )

        kwargs["widget"] = TurnstileWidget(
            site_key=site_key,
            theme=theme,
            size=size,
            action=expected_action or TURNSTILE_ACTION,
        )
        kwargs.setdefault("label", "")
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)

    def validate(self, value: str | None) -> None:
        super().validate(value)

        if not value:
            raise ValidationError(
                self.error_messages["required"],
                code="missing_turnstile",
            )

        success, error_info = self._verify_turnstile(value)
        if not success:
            self._notify_error(error_info)
            raise ValidationError(
                self.error_messages["invalid"],
                code="invalid_turnstile",
            )

    def _notify_error(self, error_info: str) -> None:
        try:
            from contact_form.notifications import notify_captcha_error

            extra_data: dict[str, str] = {
                "remote_ip": self.remote_ip or "unknown",
            }
            if self.expected_action:
                extra_data["expected_action"] = self.expected_action
            if self.expected_hostnames:
                extra_data["expected_hostnames"] = ", ".join(sorted(self.expected_hostnames))

            notify_captcha_error(
                error_message=error_info,
                request=self.request,
                page=self.page,
                provider="Cloudflare Turnstile",
                extra_data=extra_data,
            )
        except Exception as exc:
            logger.debug(
                "Failed to send CAPTCHA error notification: %s",
                str(exc),
            )

    def _verify_turnstile(self, token: str) -> tuple[bool, str]:
        if not self.secret_key:
            return False, "Turnstile Secret Key is Not Configured"

        if not isinstance(token, str) or not token:
            return False, "Verification Failed: ['missing-input-response']"

        if len(token) > TURNSTILE_TOKEN_MAX_LENGTH:
            return False, "Verification Failed: ['invalid-input-response']"

        try:
            verify_data: dict[str, str] = {
                "secret": self.secret_key,
                "response": token,
            }

            if self.remote_ip:
                verify_data["remoteip"] = self.remote_ip

            data = urllib.parse.urlencode(verify_data).encode("utf-8")
            request = urllib.request.Request(
                self.VERIFY_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

            with urllib.request.urlopen(
                request,
                timeout=TURNSTILE_VERIFY_TIMEOUT_SECONDS,
            ) as response:
                raw_response = response.read(TURNSTILE_VERIFY_RESPONSE_MAX_BYTES + 1)

            if len(raw_response) > TURNSTILE_VERIFY_RESPONSE_MAX_BYTES:
                return False, "API Response Parsing Failed: response-too-large"

            result = json.loads(raw_response.decode("utf-8"))
            if not isinstance(result, dict):
                return False, "API Response Parsing Failed: invalid-response-shape"

            if result.get("success") is not True:
                error_codes = result.get("error-codes", [])
                if not isinstance(error_codes, list):
                    error_codes = [str(error_codes)] if error_codes else []
                normalized_error_codes = [str(code) for code in error_codes]
                return False, f"Verification Failed: {normalized_error_codes}"

            if self._uses_test_keys:
                return True, ""

            if not self.expected_action:
                return False, "Verification Failed: ['action-not-configured']"

            if result.get("action") != self.expected_action:
                return False, "Verification Failed: ['action-mismatch']"

            if not self.expected_hostnames:
                return False, "Verification Failed: ['hostname-not-configured']"

            response_hostname = result.get("hostname")
            normalized_hostname = _normalize_hostname(response_hostname) if isinstance(response_hostname, str) else ""
            if normalized_hostname not in self.expected_hostnames:
                return False, "Verification Failed: ['hostname-mismatch']"

            return True, ""

        except urllib.error.HTTPError as exc:
            return False, f"API Request Failed: HTTP {exc.code}"
        except urllib.error.URLError as exc:
            return False, f"API Request Failed: {str(exc.reason)}"
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            return False, f"API Response Parsing Failed: {str(exc)}"
        except Exception as exc:
            return False, f"Unexpected Error: {str(exc)}"
