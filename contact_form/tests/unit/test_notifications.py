from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

from contact_form.notifications import _get_admin_email
from contact_form.notifications import _get_site_label
from contact_form.notifications import _get_site_phrase
from contact_form.notifications import _is_sentry_configured
from contact_form.notifications import _report_to_sentry
from contact_form.notifications import notify_captcha_error


class TestGetSiteLabel:
    @patch("contact_form.notifications.settings")
    def test_returns_website_short_name(self, mock_settings: MagicMock) -> None:
        mock_settings.WEBSITE_SHORT_NAME = "MySite"
        mock_settings.WEBSITE_FULL_NAME = None
        mock_settings.BASE_URL = None
        mock_settings.WAGTAILADMIN_BASE_URL = None
        mock_settings.WAGTAIL_SITE_NAME = None
        delattr(mock_settings, "WEBSITE_FULL_NAME")
        delattr(mock_settings, "BASE_URL")
        delattr(mock_settings, "WAGTAILADMIN_BASE_URL")
        delattr(mock_settings, "WAGTAIL_SITE_NAME")
        assert _get_site_label() == "MySite"

    @patch("contact_form.notifications.settings")
    def test_returns_website_full_name_as_fallback(self, mock_settings: MagicMock) -> None:
        mock_settings.WEBSITE_SHORT_NAME = None
        mock_settings.WEBSITE_FULL_NAME = "My Full Site Name"
        delattr(mock_settings, "WEBSITE_SHORT_NAME")
        assert _get_site_label() == "My Full Site Name"

    @patch("contact_form.notifications.settings")
    def test_returns_none_when_no_settings(self, mock_settings: MagicMock) -> None:
        del mock_settings.WEBSITE_SHORT_NAME
        del mock_settings.WEBSITE_FULL_NAME
        del mock_settings.BASE_URL
        del mock_settings.WAGTAILADMIN_BASE_URL
        del mock_settings.WAGTAIL_SITE_NAME
        assert _get_site_label() is None


class TestGetSitePhrase:
    @patch("contact_form.notifications._get_site_label")
    def test_returns_phrase_with_site_label(self, mock_get_site_label: MagicMock) -> None:
        mock_get_site_label.return_value = "MySite"
        assert _get_site_phrase() == "on the MySite website"

    @patch("contact_form.notifications._get_site_label")
    def test_returns_generic_phrase_without_site_label(
        self, mock_get_site_label: MagicMock
    ) -> None:
        mock_get_site_label.return_value = None
        assert _get_site_phrase() == "on the website"


class TestGetAdminEmail:
    @patch("contact_form.notifications.settings")
    def test_returns_wagtailadmin_notification_email(self, mock_settings: MagicMock) -> None:
        mock_settings.WAGTAILADMIN_NOTIFICATION_FROM_EMAIL = "admin@example.com"
        assert _get_admin_email() == "admin@example.com"

    @patch("contact_form.notifications.settings")
    def test_returns_default_from_email_as_fallback(self, mock_settings: MagicMock) -> None:
        mock_settings.WAGTAILADMIN_NOTIFICATION_FROM_EMAIL = None
        mock_settings.DEFAULT_FROM_EMAIL = "default@example.com"
        delattr(mock_settings, "WAGTAILADMIN_NOTIFICATION_FROM_EMAIL")
        assert _get_admin_email() == "default@example.com"

    @patch("contact_form.notifications.settings")
    def test_returns_first_admin_email_as_fallback(self, mock_settings: MagicMock) -> None:
        mock_settings.WAGTAILADMIN_NOTIFICATION_FROM_EMAIL = None
        mock_settings.DEFAULT_FROM_EMAIL = None
        mock_settings.ADMINS = [("Admin Name", "firstadmin@example.com")]
        delattr(mock_settings, "WAGTAILADMIN_NOTIFICATION_FROM_EMAIL")
        delattr(mock_settings, "DEFAULT_FROM_EMAIL")
        assert _get_admin_email() == "firstadmin@example.com"

    @patch("contact_form.notifications.settings")
    def test_returns_none_when_no_email_configured(self, mock_settings: MagicMock) -> None:
        del mock_settings.WAGTAILADMIN_NOTIFICATION_FROM_EMAIL
        del mock_settings.DEFAULT_FROM_EMAIL
        mock_settings.ADMINS = []
        assert _get_admin_email() is None


class TestIsSentryConfigured:
    def test_returns_false_when_sentry_not_installed(self) -> None:
        with patch.dict("sys.modules", {"sentry_sdk": None}):
            assert _is_sentry_configured() is False

    def test_returns_true_when_sentry_active(self) -> None:
        mock_sentry = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = True
        mock_sentry.get_client.return_value = mock_client
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            assert _is_sentry_configured() is True

    def test_returns_false_when_sentry_not_active(self) -> None:
        mock_sentry = MagicMock()
        mock_client = MagicMock()
        mock_client.is_active.return_value = False
        mock_sentry.get_client.return_value = mock_client
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            assert _is_sentry_configured() is False


class TestReportToSentry:
    def test_reports_message_to_sentry(self) -> None:
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=False)
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            _report_to_sentry("Test Error Message", {"key": "value"})
        mock_sentry.capture_message.assert_called_once()
        call_args = mock_sentry.capture_message.call_args
        assert call_args[0][0] == "Test Error Message"
        assert call_args[1]["level"] == "error"

    def test_sets_component_tag(self) -> None:
        mock_sentry = MagicMock()
        mock_scope = MagicMock()
        mock_sentry.push_scope.return_value.__enter__ = MagicMock(return_value=mock_scope)
        mock_sentry.push_scope.return_value.__exit__ = MagicMock(return_value=False)
        with patch.dict("sys.modules", {"sentry_sdk": mock_sentry}):
            _report_to_sentry("Test Error Message")
        mock_scope.set_tag.assert_called_once_with("component", "captcha")


class TestNotifyCaptchaError:
    @patch("contact_form.notifications.logger")
    @patch("contact_form.notifications.is_localhost")
    def test_logs_to_console_on_localhost(
        self, mock_is_localhost: MagicMock, mock_logger: MagicMock
    ) -> None:
        mock_is_localhost.return_value = True
        request = MagicMock()
        notify_captcha_error("Test Error", request=request, provider="Turnstile")
        assert mock_logger.warning.call_count >= 4
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("CAPTCHA ERROR" in str(call) for call in warning_calls)
        assert any("Turnstile" in str(call) for call in warning_calls)
        assert any("Test Error" in str(call) for call in warning_calls)

    @patch("contact_form.notifications.send_mail")
    @patch("contact_form.notifications._get_admin_email")
    @patch("contact_form.notifications._is_sentry_configured")
    @patch("contact_form.notifications.is_localhost")
    def test_sends_email_on_production(
        self,
        mock_is_localhost: MagicMock,
        mock_sentry_configured: MagicMock,
        mock_get_admin_email: MagicMock,
        mock_send_mail: MagicMock,
    ) -> None:
        mock_is_localhost.return_value = False
        mock_sentry_configured.return_value = False
        mock_get_admin_email.return_value = "admin@example.com"
        notify_captcha_error("Test Error", provider="Turnstile")
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args[1]
        assert "CAPTCHA" in call_kwargs["subject"]
        assert call_kwargs["from_email"] == "admin@example.com"
        assert call_kwargs["recipient_list"] == ["admin@example.com"]
        assert "Turnstile" in call_kwargs["message"]
        assert "Test Error" in call_kwargs["message"]

    @patch("contact_form.notifications._report_to_sentry")
    @patch("contact_form.notifications.send_mail")
    @patch("contact_form.notifications._get_admin_email")
    @patch("contact_form.notifications._is_sentry_configured")
    @patch("contact_form.notifications.is_localhost")
    def test_reports_to_sentry_when_configured(
        self,
        mock_is_localhost: MagicMock,
        mock_sentry_configured: MagicMock,
        mock_get_admin_email: MagicMock,
        mock_send_mail: MagicMock,
        mock_report_to_sentry: MagicMock,
    ) -> None:
        mock_is_localhost.return_value = False
        mock_sentry_configured.return_value = True
        mock_get_admin_email.return_value = "admin@example.com"
        notify_captcha_error("Test Error", provider="Turnstile", extra_data={"token": "abc123"})
        mock_report_to_sentry.assert_called_once()
        call_args = mock_report_to_sentry.call_args
        assert "Turnstile" in call_args[0][0]
        assert "Test Error" in call_args[0][0]
        assert call_args[1]["extra_data"]["provider"] == "Turnstile"

    @patch("contact_form.notifications.logger")
    @patch("contact_form.notifications._get_admin_email")
    @patch("contact_form.notifications._is_sentry_configured")
    @patch("contact_form.notifications.is_localhost")
    def test_logs_warning_when_no_admin_email(
        self,
        mock_is_localhost: MagicMock,
        mock_sentry_configured: MagicMock,
        mock_get_admin_email: MagicMock,
        mock_logger: MagicMock,
    ) -> None:
        mock_is_localhost.return_value = False
        mock_sentry_configured.return_value = False
        mock_get_admin_email.return_value = None
        notify_captcha_error("Test Error", provider="Turnstile")
        mock_logger.warning.assert_called()
        warning_call = str(mock_logger.warning.call_args)
        assert "Test Error" in warning_call

    @patch("contact_form.notifications.logger")
    @patch("contact_form.notifications.is_localhost")
    def test_includes_extra_data_in_localhost_log(
        self, mock_is_localhost: MagicMock, mock_logger: MagicMock
    ) -> None:
        mock_is_localhost.return_value = True
        notify_captcha_error(
            "Test Error",
            provider="Turnstile",
            extra_data={"token_prefix": "abc", "user_ip": "1.2.3.4"},
        )
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("token_prefix" in str(call) for call in warning_calls)
        assert any("user_ip" in str(call) for call in warning_calls)

    @patch("contact_form.notifications.send_mail")
    @patch("contact_form.notifications._get_admin_email")
    @patch("contact_form.notifications._get_site_label")
    @patch("contact_form.notifications._is_sentry_configured")
    @patch("contact_form.notifications.is_localhost")
    def test_includes_site_label_in_email_subject(
        self,
        mock_is_localhost: MagicMock,
        mock_sentry_configured: MagicMock,
        mock_get_site_label: MagicMock,
        mock_get_admin_email: MagicMock,
        mock_send_mail: MagicMock,
    ) -> None:
        mock_is_localhost.return_value = False
        mock_sentry_configured.return_value = False
        mock_get_site_label.return_value = "MySite"
        mock_get_admin_email.return_value = "admin@example.com"
        notify_captcha_error("Test Error", provider="Turnstile")
        call_kwargs = mock_send_mail.call_args[1]
        assert "MySite" in call_kwargs["subject"]
