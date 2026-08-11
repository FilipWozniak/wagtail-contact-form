from __future__ import annotations

import json
import urllib.error
import urllib.parse
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from contact_form.turnstile import TURNSTILE_ACTION
from contact_form.turnstile import TURNSTILE_TEST_SECRET_KEY
from contact_form.turnstile import TURNSTILE_TEST_SITE_KEY
from contact_form.turnstile import TURNSTILE_TOKEN_MAX_LENGTH
from contact_form.turnstile import TurnstileField
from contact_form.turnstile import TurnstileWidget


def _mock_response(payload: dict[str, object] | list[object] | bytes) -> MagicMock:
    response = MagicMock()
    response.read.return_value = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    response.__enter__.return_value = response
    response.__exit__.return_value = False
    return response


class TestTurnstileWidget:
    def test_widget_initialization(self) -> None:
        widget = TurnstileWidget(
            site_key="test-site-key",
            theme="dark",
            size="compact",
            action="contact_form",
        )
        assert widget.site_key == "test-site-key"
        assert widget.theme == "dark"
        assert widget.size == "compact"
        assert widget.action == "contact_form"

    def test_widget_default_values(self) -> None:
        widget = TurnstileWidget()
        assert widget.site_key == ""
        assert widget.theme == "auto"
        assert widget.size == "normal"
        assert widget.action == TURNSTILE_ACTION

    def test_widget_render_uses_cloudflare_response_field_without_duplicate_input(
        self,
    ) -> None:
        widget = TurnstileWidget(site_key="test-key", theme="light", size="normal")

        html = widget.render("test_field", None, attrs={"id": "id_test_field"})

        assert 'data-sitekey="test-key"' in html
        assert 'data-theme="light"' in html
        assert 'data-size="normal"' in html
        assert f'data-action="{TURNSTILE_ACTION}"' in html
        assert 'data-response-field-name="cf-turnstile-response"' in html
        assert "data-turnstile-status" in html
        assert "<input" not in html
        assert "<script" not in html

    def test_widget_render_escapes_configuration_values(self) -> None:
        widget = TurnstileWidget(site_key='"><script>alert(1)</script>')

        html = widget.render("test_field", None)

        assert "<script>alert(1)</script>" not in html
        assert "&lt;script&gt;" in html

    def test_widget_value_from_datadict(self) -> None:
        widget = TurnstileWidget()
        data = {"cf-turnstile-response": "test-token-value"}
        value = widget.value_from_datadict(data, {}, "wagtailcaptcha")
        assert value == "test-token-value"

    def test_widget_value_from_datadict_missing(self) -> None:
        widget = TurnstileWidget()
        value = widget.value_from_datadict({}, {}, "wagtailcaptcha")
        assert value is None

    def test_widget_rejects_non_string_response(self) -> None:
        widget = TurnstileWidget()
        value = widget.value_from_datadict(
            {"cf-turnstile-response": ["one", "two"]},
            {},
            "wagtailcaptcha",
        )
        assert value is None


class TestTurnstileField:
    def test_field_initialization(self) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")
        assert field.secret_key == "test-secret-key"
        assert field.required is True
        assert field.label == ""

    @pytest.mark.parametrize("value", ["", None])
    def test_field_validation_empty_value(self, value: str | None) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")

        with pytest.raises(ValidationError) as exc_info:
            field.validate(value)

        assert exc_info.value.code == "required"
        assert "complete the CAPTCHA" in str(exc_info.value)

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_success(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "gsthr.org",
                "action": TURNSTILE_ACTION,
            }
        )
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            expected_hostnames=("gsthr.org",),
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("test-token")

        assert success is True
        assert error == ""

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_fails_closed_without_expected_action(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "gsthr.org",
                "action": TURNSTILE_ACTION,
            }
        )
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            expected_hostnames=("gsthr.org",),
        )

        success, error = field._verify_turnstile("test-token")

        assert success is False
        assert error == "Verification Failed: ['action-not-configured']"

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_fails_closed_without_expected_hostname(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "gsthr.org",
                "action": TURNSTILE_ACTION,
            }
        )
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("test-token")

        assert success is False
        assert error == "Verification Failed: ['hostname-not-configured']"

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_posts_remote_ip(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response({"success": True})
        field = TurnstileField(
            site_key="test-site-key",
            secret_key="test-secret-key",
            remote_ip="203.0.113.10",
        )

        field._verify_turnstile("test-token")

        request = mock_urlopen.call_args.args[0]
        posted_data = urllib.parse.parse_qs(request.data.decode("utf-8"))
        assert posted_data["remoteip"] == ["203.0.113.10"]

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_failure(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": False,
                "error-codes": ["invalid-input-response"],
            }
        )
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")

        success, error = field._verify_turnstile("invalid-token")

        assert success is False
        assert error == "Verification Failed: ['invalid-input-response']"

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_rejects_action_mismatch(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "gsthr.org",
                "action": "different_action",
            }
        )
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            expected_hostnames=("gsthr.org",),
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("test-token")

        assert success is False
        assert error == "Verification Failed: ['action-mismatch']"

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_rejects_hostname_mismatch(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "attacker.example",
                "action": TURNSTILE_ACTION,
            }
        )
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            expected_hostnames=("gsthr.org",),
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("test-token")

        assert success is False
        assert error == "Verification Failed: ['hostname-mismatch']"

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_normalizes_expected_hostname(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "gsthr.org",
                "action": TURNSTILE_ACTION,
            }
        )
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            expected_hostnames=("GSTHR.ORG.:443",),
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("test-token")

        assert success is True
        assert error == ""

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_documented_test_keys_bypass_context_checks(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "example.com",
                "metadata": {"result_with_testing_key": True},
            }
        )
        field = TurnstileField(
            site_key=TURNSTILE_TEST_SITE_KEY,
            secret_key=TURNSTILE_TEST_SECRET_KEY,
            request=MagicMock(get_host=MagicMock(return_value="gsthr.org.localhost:8000")),
            expected_hostnames=("gsthr.org.localhost",),
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("XXXX.DUMMY.TOKEN.XXXX")

        assert success is True
        assert error == ""

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_documented_test_keys_do_not_bypass_checks_on_production_host(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "example.com",
            }
        )
        field = TurnstileField(
            site_key=TURNSTILE_TEST_SITE_KEY,
            secret_key=TURNSTILE_TEST_SECRET_KEY,
            request=MagicMock(get_host=MagicMock(return_value="gsthr.org")),
            expected_hostnames=("gsthr.org",),
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("XXXX.DUMMY.TOKEN.XXXX")

        assert success is False
        assert error == "Verification Failed: ['action-mismatch']"

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_partial_test_key_pair_does_not_bypass_context_checks(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": True,
                "hostname": "example.com",
            }
        )
        field = TurnstileField(
            site_key="production-site-key",
            secret_key=TURNSTILE_TEST_SECRET_KEY,
            expected_hostnames=("gsthr.org",),
            expected_action=TURNSTILE_ACTION,
        )

        success, error = field._verify_turnstile("XXXX.DUMMY.TOKEN.XXXX")

        assert success is False
        assert error == "Verification Failed: ['action-mismatch']"

    def test_malformed_expected_hostname_is_ignored_safely(self) -> None:
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            expected_hostnames=("[not-an-ip",),
            expected_action=TURNSTILE_ACTION,
        )

        assert field.expected_hostnames == frozenset()

    @patch("contact_form.notifications.notify_captcha_error")
    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_validation_passes_page_to_error_notification(
        self,
        mock_urlopen: MagicMock,
        mock_notify: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response(
            {
                "success": False,
                "error-codes": ["invalid-input-response"],
            }
        )
        page = MagicMock()
        request = MagicMock()
        field = TurnstileField(
            site_key="production-site-key",
            secret_key="production-secret-key",
            request=request,
            page=page,
        )

        with pytest.raises(ValidationError):
            field.validate("invalid-token")

        mock_notify.assert_called_once()
        assert mock_notify.call_args.kwargs["page"] is page
        assert mock_notify.call_args.kwargs["request"] is request
        assert mock_notify.call_args.kwargs["error_message"] == "Verification Failed: ['invalid-input-response']"

    def test_verify_turnstile_missing_secret_key(self) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="")
        success, error = field._verify_turnstile("test-token")
        assert success is False
        assert "not configured" in error.lower()

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_rejects_oversized_token_without_api_request(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")

        success, error = field._verify_turnstile("x" * (TURNSTILE_TOKEN_MAX_LENGTH + 1))

        assert success is False
        assert error == "Verification Failed: ['invalid-input-response']"
        mock_urlopen.assert_not_called()

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_rejects_invalid_response_shape(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        mock_urlopen.return_value = _mock_response([{"success": True}])
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")

        success, error = field._verify_turnstile("test-token")

        assert success is False
        assert error == "API Response Parsing Failed: invalid-response-shape"

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_network_error(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")

        success, error = field._verify_turnstile("test-token")

        assert success is False
        assert error == "API Request Failed: Network error"
