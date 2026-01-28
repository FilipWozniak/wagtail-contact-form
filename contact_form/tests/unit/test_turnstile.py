from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from contact_form.turnstile import TurnstileField
from contact_form.turnstile import TurnstileWidget


class TestTurnstileWidget:
    def test_widget_initialization(self) -> None:
        widget = TurnstileWidget(site_key="test-site-key", theme="dark", size="compact")
        assert widget.site_key == "test-site-key"
        assert widget.theme == "dark"
        assert widget.size == "compact"

    def test_widget_default_values(self) -> None:
        widget = TurnstileWidget()
        assert widget.site_key == ""
        assert widget.theme == "auto"
        assert widget.size == "normal"

    def test_widget_render(self) -> None:
        widget = TurnstileWidget(site_key="test-key", theme="light", size="normal")
        html = widget.render("test_field", None)
        assert "test-key" in html
        assert 'data-theme="light"' in html
        assert 'data-size="normal"' in html
        assert "cf-turnstile" in html

    def test_widget_value_from_datadict(self) -> None:
        widget = TurnstileWidget()
        data = {"cf-turnstile-response": "test-token-value"}
        value = widget.value_from_datadict(data, {}, "wagtailcaptcha")
        assert value == "test-token-value"

    def test_widget_value_from_datadict_missing(self) -> None:
        widget = TurnstileWidget()
        value = widget.value_from_datadict({}, {}, "wagtailcaptcha")
        assert value is None


class TestTurnstileField:
    def test_field_initialization(self) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")
        assert field.secret_key == "test-secret-key"
        assert field.required is True
        assert field.label == ""

    def test_field_validation_empty_value(self) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")
        with pytest.raises(ValidationError) as exc_info:
            field.validate("")
        assert "required" in str(exc_info.value).lower()

    def test_field_validation_none_value(self) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")
        with pytest.raises(ValidationError) as exc_info:
            field.validate(None)
        assert "required" in str(exc_info.value).lower()

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_success(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = b'{"success": true}'
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")
        success, error = field._verify_turnstile("test-token")
        assert success is True
        assert error == ""

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_failure(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.read.return_value = (
            b'{"success": false, "error-codes": ["invalid-input-response"]}'
        )
        mock_response.__enter__ = lambda s: mock_response
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")
        success, error = field._verify_turnstile("invalid-token")
        assert success is False
        assert "invalid-input-response" in error

    def test_verify_turnstile_missing_secret_key(self) -> None:
        field = TurnstileField(site_key="test-site-key", secret_key="")
        success, error = field._verify_turnstile("test-token")
        assert success is False
        assert "not configured" in error.lower()

    @patch("contact_form.turnstile.urllib.request.urlopen")
    def test_verify_turnstile_network_error(self, mock_urlopen: MagicMock) -> None:
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("Network error")
        field = TurnstileField(site_key="test-site-key", secret_key="test-secret-key")
        success, error = field._verify_turnstile("test-token")
        assert success is False
        assert "API Request Failed" in error
