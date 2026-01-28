from __future__ import annotations

from unittest.mock import MagicMock

from contact_form.utils import RECAPTCHA_TEST_SECRET_KEY
from contact_form.utils import RECAPTCHA_TEST_SITE_KEY
from contact_form.utils import TURNSTILE_TEST_SECRET_KEY
from contact_form.utils import TURNSTILE_TEST_SITE_KEY
from contact_form.utils import get_captcha_keys_for_environment
from contact_form.utils import is_localhost


class TestLocalhostDetection:
    def test_localhost_detected(self) -> None:
        assert is_localhost(host="localhost") is True
        assert is_localhost(host="localhost:8000") is True

    def test_localhost_with_subdomain_detected(self) -> None:
        assert is_localhost(host="gphnetwork.org.localhost") is True
        assert is_localhost(host="gphnetwork.org.localhost:8000") is True
        assert is_localhost(host="test.localhost:3000") is True

    def test_127_0_0_1_detected(self) -> None:
        assert is_localhost(host="127.0.0.1") is True
        assert is_localhost(host="127.0.0.1:8000") is True

    def test_0_0_0_0_detected(self) -> None:
        assert is_localhost(host="0.0.0.0") is True
        assert is_localhost(host="0.0.0.0:8000") is True

    def test_ipv6_localhost_detected(self) -> None:
        assert is_localhost(host="[::1]") is True
        assert is_localhost(host="[::1]:8000") is True

    def test_production_domain_not_localhost(self) -> None:
        assert is_localhost(host="example.com") is False
        assert is_localhost(host="www.example.com") is False
        assert is_localhost(host="gphnetwork.org") is False

    def test_request_host_detection(self) -> None:
        request = MagicMock()
        request.get_host.return_value = "localhost:8000"
        assert is_localhost(request=request) is True
        request.get_host.return_value = "example.com"
        assert is_localhost(request=request) is False

    def test_empty_host_returns_false(self) -> None:
        assert is_localhost(host="") is False
        assert is_localhost(host=None) is False
        assert is_localhost() is False


class TestCaptchaTestKeys:
    def test_recaptcha_test_keys_on_localhost(self) -> None:
        request = MagicMock()
        request.get_host.return_value = "localhost:8000"
        keys = get_captcha_keys_for_environment("recaptcha", request, None)
        assert keys["site_key"] == RECAPTCHA_TEST_SITE_KEY
        assert keys["secret_key"] == RECAPTCHA_TEST_SECRET_KEY

    def test_turnstile_test_keys_on_localhost(self) -> None:
        request = MagicMock()
        request.get_host.return_value = "localhost:8000"
        keys = get_captcha_keys_for_environment("turnstile", request, None)
        assert keys["site_key"] == TURNSTILE_TEST_SITE_KEY
        assert keys["secret_key"] == TURNSTILE_TEST_SECRET_KEY

    def test_test_keys_always_used_on_localhost_even_with_configured_keys(self) -> None:
        request = MagicMock()
        request.get_host.return_value = "localhost:8000"
        configured = {"site_key": "prod-site-key", "secret_key": "prod-secret-key"}
        keys = get_captcha_keys_for_environment("turnstile", request, configured)
        assert keys["site_key"] == TURNSTILE_TEST_SITE_KEY
        assert keys["secret_key"] == TURNSTILE_TEST_SECRET_KEY

    def test_configured_keys_on_production(self) -> None:
        request = MagicMock()
        request.get_host.return_value = "example.com"
        configured = {"site_key": "prod-site-key", "secret_key": "prod-secret-key"}
        keys = get_captcha_keys_for_environment("turnstile", request, configured)
        assert keys["site_key"] == "prod-site-key"
        assert keys["secret_key"] == "prod-secret-key"

    def test_empty_keys_on_production_without_config(self) -> None:
        request = MagicMock()
        request.get_host.return_value = "example.com"
        keys = get_captcha_keys_for_environment("turnstile", request, None)
        assert keys["site_key"] == ""
        assert keys["secret_key"] == ""

    def test_subdomain_localhost_uses_test_keys(self) -> None:
        request = MagicMock()
        request.get_host.return_value = "gphnetwork.org.localhost:8000"
        configured = {"site_key": "prod-key", "secret_key": "prod-secret"}
        keys = get_captcha_keys_for_environment("turnstile", request, configured)
        assert keys["site_key"] == TURNSTILE_TEST_SITE_KEY
        assert keys["secret_key"] == TURNSTILE_TEST_SECRET_KEY
