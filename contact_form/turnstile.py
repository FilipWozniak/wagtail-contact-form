from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe

from contact_form.utils import TURNSTILE_TEST_SITE_KEY

logger = logging.getLogger(__name__)


class TurnstileWidget(forms.Widget):
    template_name = "contact_form/widgets/turnstile.html"

    def __init__(
        self,
        site_key: str = "",
        theme: str = "auto",
        size: str = "normal",
        attrs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(attrs=attrs)
        self.site_key = site_key
        self.theme = theme
        self.size = size

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict:
        context = super().get_context(name, value, attrs)
        context["widget"].update({
            "site_key": self.site_key,
            "theme": self.theme,
            "size": self.size,
        })
        return context

    def render(
        self,
        name: str,
        value: Any,
        attrs: dict[str, Any] | None = None,
        renderer: Any = None,
    ) -> str:
        is_test_key = self.site_key == TURNSTILE_TEST_SITE_KEY
        if is_test_key:
            logger.info("Turnstile using TEST site key (localhost mode)")

        html = f"""
        <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
        <div class="cf-turnstile"
             data-sitekey="{self.site_key}"
             data-theme="{self.theme}"
             data-size="{self.size}"
             data-callback="onTurnstileSuccess"
             data-error-callback="onTurnstileError">
        </div>
        <input type="hidden" name="cf-turnstile-response" id="cf-turnstile-response" value="">
        <script>
            function onTurnstileSuccess(token) {{
                document.getElementById('cf-turnstile-response').value = token;
            }}
            function onTurnstileError(errorCode) {{
                console.error('Turnstile error:', errorCode);
            }}
        </script>
        """
        return mark_safe(html)

    def value_from_datadict(
        self, data: dict[str, Any], files: dict[str, Any], name: str
    ) -> str | None:
        return data.get("cf-turnstile-response")


class TurnstileField(forms.Field):
    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    def __init__(
        self,
        site_key: str = "",
        secret_key: str = "",
        theme: str = "auto",
        size: str = "normal",
        remote_ip: str | None = None,
        request: Any = None,
        **kwargs: Any,
    ) -> None:
        self.secret_key = secret_key
        self.remote_ip = remote_ip
        self.request = request
        kwargs["widget"] = TurnstileWidget(site_key=site_key, theme=theme, size=size)
        kwargs.setdefault("label", "")
        kwargs.setdefault("required", True)
        super().__init__(**kwargs)

    def validate(self, value: str | None) -> None:
        super().validate(value)

        if not value:
            raise ValidationError(
                "Please Complete the CAPTCHA Verification.",
                code="missing_turnstile",
            )

        success, error_info = self._verify_turnstile(value)
        if not success:
            self._notify_error(error_info)
            raise ValidationError(
                "CAPTCHA Verification Failed. Please Try Again.",
                code="invalid_turnstile",
            )

    def _notify_error(self, error_info: str) -> None:
        try:
            from contact_form.notifications import notify_captcha_error

            notify_captcha_error(
                error_message=error_info,
                request=self.request,
                provider="Cloudflare Turnstile",
                extra_data={"remote_ip": self.remote_ip or "unknown"},
            )
        except Exception as e:
            logger.debug("Failed to Send CAPTCHA Error Notification: %s", str(e))

    def _verify_turnstile(self, token: str) -> tuple[bool, str]:
        if not self.secret_key:
            return False, "Turnstile Secret Key is Not Configured"

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
            )

            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode("utf-8"))
                success = result.get("success", False)
                if not success:
                    error_codes = result.get("error-codes", [])
                    return False, f"Verification Failed: {error_codes}"
                return True, ""

        except urllib.error.URLError as e:
            return False, f"API Request Failed: {str(e)}"
        except json.JSONDecodeError as e:
            return False, f"API Response Parsing Failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected Error: {str(e)}"
