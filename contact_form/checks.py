from __future__ import annotations

import ipaddress
import math
from collections.abc import Iterable
from typing import Any

from django.conf import settings
from django.core import checks


_POSITIVE_SETTINGS: dict[str, int | float] = {
    "CONTACT_FORM_POST_LIMIT": 5,
    "CONTACT_FORM_POST_WINDOW_SECONDS": 600,
    "CONTACT_FORM_MINIMUM_COMPLETION_SECONDS": 3,
    "CONTACT_FORM_TOKEN_MAX_AGE_SECONDS": 7200,
    "CONTACT_FORM_DUPLICATE_WINDOW_SECONDS": 600,
}


@checks.register(checks.Tags.security)
def check_contact_form_security_settings(
    app_configs: Any = None,
    **kwargs: Any,
) -> list[checks.CheckMessage]:
    messages: list[checks.CheckMessage] = []

    for setting_name, default in _POSITIVE_SETTINGS.items():
        raw_value = getattr(settings, setting_name, default)
        try:
            numeric_value = float(raw_value)
            is_valid = math.isfinite(numeric_value) and numeric_value > 0
        except (TypeError, ValueError):
            is_valid = False
        if not is_valid:
            messages.append(
                checks.Error(
                    f"{setting_name} must be a positive number.",
                    id="contact_form.E001",
                )
            )

    minimum_age = getattr(settings, "CONTACT_FORM_MINIMUM_COMPLETION_SECONDS", 3)
    maximum_age = getattr(settings, "CONTACT_FORM_TOKEN_MAX_AGE_SECONDS", 7200)
    try:
        invalid_age_window = float(minimum_age) >= float(maximum_age)
    except (TypeError, ValueError):
        invalid_age_window = False
    if invalid_age_window:
        messages.append(
            checks.Error(
                "CONTACT_FORM_TOKEN_MAX_AGE_SECONDS must be greater than CONTACT_FORM_MINIMUM_COMPLETION_SECONDS.",
                id="contact_form.E002",
            )
        )

    raw_prefix_length = getattr(settings, "CONTACT_FORM_IPV6_PREFIX_LENGTH", 64)
    try:
        prefix_length = int(raw_prefix_length)
    except (TypeError, ValueError):
        prefix_length = 0
    if not 1 <= prefix_length <= 128:
        messages.append(
            checks.Error(
                "CONTACT_FORM_IPV6_PREFIX_LENGTH must be between 1 and 128.",
                id="contact_form.E003",
            )
        )

    configured_header = str(getattr(settings, "CONTACT_FORM_TRUSTED_CLIENT_IP_HEADER", "")).strip()
    configured_networks = getattr(settings, "CONTACT_FORM_TRUSTED_PROXY_NETWORKS", ())
    if isinstance(configured_networks, str) or not isinstance(configured_networks, Iterable):
        messages.append(
            checks.Error(
                "CONTACT_FORM_TRUSTED_PROXY_NETWORKS must be a list or tuple of CIDR networks.",
                id="contact_form.E004",
            )
        )
        configured_networks = ()

    invalid_networks: list[str] = []
    unrestricted_networks: list[str] = []
    for network in configured_networks:
        try:
            parsed_network = ipaddress.ip_network(str(network), strict=False)
        except ValueError:
            invalid_networks.append(str(network))
        else:
            if parsed_network.prefixlen == 0:
                unrestricted_networks.append(str(network))
    if invalid_networks:
        messages.append(
            checks.Error(
                "CONTACT_FORM_TRUSTED_PROXY_NETWORKS contains invalid CIDR values: " + ", ".join(invalid_networks),
                id="contact_form.E005",
            )
        )
    if unrestricted_networks:
        messages.append(
            checks.Error(
                "CONTACT_FORM_TRUSTED_PROXY_NETWORKS must not trust every address: " + ", ".join(unrestricted_networks),
                id="contact_form.E007",
            )
        )

    if configured_header and not configured_header.startswith("HTTP_"):
        messages.append(
            checks.Error(
                "CONTACT_FORM_TRUSTED_CLIENT_IP_HEADER must be a Django request.META header name beginning with HTTP_.",
                id="contact_form.E006",
            )
        )
    if configured_header and not configured_networks:
        messages.append(
            checks.Warning(
                "CONTACT_FORM_TRUSTED_CLIENT_IP_HEADER is configured without trusted "
                "proxy networks, so the header will be ignored.",
                id="contact_form.W001",
            )
        )

    return messages
