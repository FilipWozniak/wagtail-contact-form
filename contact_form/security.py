from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import math
import re
import secrets
import time
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum
from typing import TYPE_CHECKING
from typing import Any
from uuid import UUID

from django.conf import settings
from django.core import signing
from django.core.cache import cache
from django.core.serializers.json import DjangoJSONEncoder

if TYPE_CHECKING:
    from django import forms
    from django.http import HttpRequest

    from contact_form.models import ContactPage


FORM_TOKEN_FIELD_NAME = "_contact_form_token"
FORM_TOKEN_SALT = "contact_form.security.v1"
FORM_TOKEN_VERSION = 1
HONEYPOT_NAME_PATTERN = re.compile(r"^_contact_[a-f0-9]{16}$")
NONCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{20,128}$")

DEFAULT_POST_LIMIT = 5
DEFAULT_POST_WINDOW_SECONDS = 600
DEFAULT_MINIMUM_COMPLETION_SECONDS = 3
DEFAULT_TOKEN_MAX_AGE_SECONDS = 7200
DEFAULT_DUPLICATE_WINDOW_SECONDS = 600
DEFAULT_IPV6_PREFIX_LENGTH = 64

SECURITY_CACHE_KEY_PREFIX = "contact-form-security:v1"


class SecurityEventKind(str, Enum):
    CAPTCHA_NOTIFICATION = "captcha_notification"
    POST_RATE_LIMIT = "post_rate_limit"
    DUPLICATE_CONTENT = "duplicate_content"
    SUBMISSION_NONCE = "submission_nonce"

    def __str__(self) -> str:
        return self.value


class FormSecurityError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class SecurityStateUnavailable(RuntimeError):
    pass


class DuplicateContactSubmission(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SecurityWindowDecision:
    allowed: bool
    retry_after_seconds: int
    previous_count: int


@dataclass(frozen=True, slots=True)
class FormSecurityPayload:
    page_id: int
    translation_key: UUID
    issued_at: int
    nonce: str
    honeypot_name: str


@dataclass(frozen=True, slots=True)
class ValidatedSubmissionSecurity:
    nonce_hash: str
    submission_fingerprint: str


def get_positive_int_setting(name: str, default: int) -> int:
    raw_value = getattr(settings, name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def privacy_hash(*parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    secret = settings.SECRET_KEY.encode("utf-8")
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


def get_page_scope_hash(page: ContactPage) -> str:
    return privacy_hash("contact-form-page", page.translation_key)


def issue_form_security_token(page: ContactPage) -> tuple[str, str]:
    honeypot_name = f"_contact_{secrets.token_hex(8)}"
    payload: dict[str, str | int] = {
        "version": FORM_TOKEN_VERSION,
        "page_id": page.pk,
        "translation_key": str(page.translation_key),
        "issued_at": int(time.time()),
        "nonce": secrets.token_urlsafe(24),
        "honeypot_name": honeypot_name,
    }
    token = signing.dumps(payload, salt=FORM_TOKEN_SALT, compress=True)
    return token, honeypot_name


def validate_form_security_token(
    *,
    page: ContactPage,
    token: str,
    minimum_age_seconds: int | None = None,
    maximum_age_seconds: int | None = None,
) -> FormSecurityPayload:
    if not token:
        raise FormSecurityError("missing-token")

    minimum_age = minimum_age_seconds
    if minimum_age is None:
        minimum_age = get_positive_int_setting(
            "CONTACT_FORM_MINIMUM_COMPLETION_SECONDS",
            DEFAULT_MINIMUM_COMPLETION_SECONDS,
        )

    maximum_age = maximum_age_seconds
    if maximum_age is None:
        maximum_age = get_positive_int_setting(
            "CONTACT_FORM_TOKEN_MAX_AGE_SECONDS",
            DEFAULT_TOKEN_MAX_AGE_SECONDS,
        )

    try:
        raw_payload = signing.loads(
            token,
            salt=FORM_TOKEN_SALT,
            max_age=maximum_age,
        )
    except signing.SignatureExpired as exc:
        raise FormSecurityError("expired-token") from exc
    except signing.BadSignature as exc:
        raise FormSecurityError("invalid-token") from exc

    if not isinstance(raw_payload, dict):
        raise FormSecurityError("invalid-payload")

    try:
        version = int(raw_payload["version"])
        page_id = int(raw_payload["page_id"])
        translation_key = UUID(str(raw_payload["translation_key"]))
        issued_at = int(raw_payload["issued_at"])
        nonce = str(raw_payload["nonce"])
        honeypot_name = str(raw_payload["honeypot_name"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FormSecurityError("invalid-payload") from exc

    if version != FORM_TOKEN_VERSION:
        raise FormSecurityError("unsupported-token-version")
    if page_id != page.pk or translation_key != page.translation_key:
        raise FormSecurityError("wrong-page")
    if not NONCE_PATTERN.fullmatch(nonce):
        raise FormSecurityError("invalid-nonce")
    if not HONEYPOT_NAME_PATTERN.fullmatch(honeypot_name):
        raise FormSecurityError("invalid-honeypot")

    age_seconds = int(time.time()) - issued_at
    if age_seconds < 0:
        raise FormSecurityError("future-token")
    if age_seconds < minimum_age:
        raise FormSecurityError("submitted-too-quickly")
    if age_seconds > maximum_age:
        raise FormSecurityError("expired-token")

    return FormSecurityPayload(
        page_id=page_id,
        translation_key=translation_key,
        issued_at=issued_at,
        nonce=nonce,
        honeypot_name=honeypot_name,
    )


def is_honeypot_filled(request: HttpRequest, payload: FormSecurityPayload) -> bool:
    value = request.POST.get(payload.honeypot_name, "")
    return bool(str(value).strip())


def _trusted_proxy_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    configured = getattr(settings, "CONTACT_FORM_TRUSTED_PROXY_NETWORKS", ())
    if isinstance(configured, str):
        configured = ()
    for value in configured:
        try:
            networks.append(ipaddress.ip_network(str(value), strict=False))
        except ValueError:
            continue
    return tuple(networks)


def _is_trusted_proxy(address: str) -> bool:
    try:
        parsed_address = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(parsed_address in network for network in _trusted_proxy_networks())


def get_client_ip(request: HttpRequest) -> str | None:
    remote_address = str(request.META.get("REMOTE_ADDR", "")).strip()
    configured_header = str(getattr(settings, "CONTACT_FORM_TRUSTED_CLIENT_IP_HEADER", "")).strip()

    candidate = remote_address
    if configured_header and remote_address and _is_trusted_proxy(remote_address):
        forwarded_address = str(request.META.get(configured_header, "")).strip()
        if forwarded_address and "," not in forwarded_address:
            candidate = forwarded_address

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def _normalized_client_network(client_ip: str | None) -> str:
    if client_ip is None:
        return "unknown"

    parsed_address = ipaddress.ip_address(client_ip)
    if isinstance(parsed_address, ipaddress.IPv4Address):
        return f"{parsed_address}/32"

    prefix_length = get_positive_int_setting(
        "CONTACT_FORM_IPV6_PREFIX_LENGTH",
        DEFAULT_IPV6_PREFIX_LENGTH,
    )
    prefix_length = min(prefix_length, 128)
    network = ipaddress.ip_network(f"{parsed_address}/{prefix_length}", strict=False)
    return str(network)


def get_client_fingerprint(request: HttpRequest) -> str:
    return privacy_hash("contact-form-client", _normalized_client_network(get_client_ip(request)))


def _normalize_submission_value(value: Any) -> Any:
    if isinstance(value, str):
        return " ".join(value.split())
    if isinstance(value, dict):
        return {
            str(key): _normalize_submission_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple, set)):
        normalized = [_normalize_submission_value(item) for item in value]
        return sorted(normalized, key=str)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def get_submission_fingerprint(
    *,
    page: ContactPage,
    form: forms.Form,
    client_fingerprint: str,
) -> str:
    from contact_form.forms import ContactFormBuilder

    excluded_fields = {ContactFormBuilder.CAPTCHA_FIELD_NAME}
    normalized_data = {
        key: _normalize_submission_value(value)
        for key, value in sorted(form.cleaned_data.items())
        if key not in excluded_fields
    }
    serialized = json.dumps(
        normalized_data,
        cls=DjangoJSONEncoder,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return privacy_hash(
        "contact-form-submission",
        page.translation_key,
        client_fingerprint,
        serialized,
    )


def get_submission_nonce_hash(*, page: ContactPage, nonce: str) -> str:
    return privacy_hash("contact-form-nonce", page.translation_key, nonce)


def _security_cache_key(
    *,
    kind: str,
    scope_hash: str,
    fingerprint: str,
    bucket: int | None = None,
) -> str:
    parts = [str(kind), scope_hash, fingerprint]
    if bucket is not None:
        parts.append(str(bucket))
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return f"{SECURITY_CACHE_KEY_PREFIX}:{digest}"


def _reservation_key(
    *,
    kind: str,
    scope_hash: str,
    fingerprint: str,
) -> str:
    return _security_cache_key(
        kind=kind,
        scope_hash=scope_hash,
        fingerprint=fingerprint,
    )


def _reserve_once(
    *,
    kind: str,
    scope_hash: str,
    fingerprint: str,
    duration_seconds: int,
) -> SecurityWindowDecision:
    key = _reservation_key(
        kind=kind,
        scope_hash=scope_hash,
        fingerprint=fingerprint,
    )
    try:
        allowed = bool(cache.add(key, True, timeout=duration_seconds))
    except Exception as exc:
        raise SecurityStateUnavailable("CONTACT_FORM security cache is unavailable.") from exc
    return SecurityWindowDecision(
        allowed=allowed,
        retry_after_seconds=0 if allowed else duration_seconds,
        previous_count=0 if allowed else 1,
    )


def _release_reservation(
    *,
    kind: str,
    scope_hash: str,
    fingerprint: str,
) -> bool:
    key = _reservation_key(
        kind=kind,
        scope_hash=scope_hash,
        fingerprint=fingerprint,
    )
    try:
        return bool(cache.delete(key))
    except Exception as exc:
        raise SecurityStateUnavailable("CONTACT_FORM security cache is unavailable.") from exc


def is_submission_nonce_used(*, page: ContactPage, nonce_hash: str) -> bool:
    key = _reservation_key(
        kind=str(SecurityEventKind.SUBMISSION_NONCE),
        scope_hash=get_page_scope_hash(page),
        fingerprint=nonce_hash,
    )
    try:
        return cache.get(key) is not None
    except Exception as exc:
        raise SecurityStateUnavailable("CONTACT_FORM security cache is unavailable.") from exc


def acquire_security_window(
    *,
    kind: str,
    scope_hash: str,
    fingerprint: str,
    duration: timedelta,
    limit: int,
) -> SecurityWindowDecision:
    duration_seconds = max(1, math.ceil(duration.total_seconds()))
    if limit < 1 or duration.total_seconds() <= 0:
        raise ValueError("Security windows require a positive duration and limit.")

    if limit == 1:
        return _reserve_once(
            kind=kind,
            scope_hash=scope_hash,
            fingerprint=fingerprint,
            duration_seconds=duration_seconds,
        )

    now = int(time.time())
    bucket = now // duration_seconds
    retry_after_seconds = duration_seconds - (now % duration_seconds)
    key = _security_cache_key(
        kind=kind,
        scope_hash=scope_hash,
        fingerprint=fingerprint,
        bucket=bucket,
    )

    try:
        if cache.add(key, 1, timeout=duration_seconds + 1):
            count = 1
        else:
            try:
                count = int(cache.incr(key))
            except ValueError:
                if not cache.add(key, 1, timeout=duration_seconds + 1):
                    count = int(cache.incr(key))
                else:
                    count = 1
    except Exception as exc:
        raise SecurityStateUnavailable("CONTACT_FORM security cache is unavailable.") from exc

    return SecurityWindowDecision(
        allowed=count <= limit,
        retry_after_seconds=0 if count <= limit else max(1, retry_after_seconds),
        previous_count=max(0, count - 1),
    )


def release_duplicate_submission(
    *,
    page: ContactPage,
    submission_fingerprint: str,
) -> bool:
    return _release_reservation(
        kind=str(SecurityEventKind.DUPLICATE_CONTENT),
        scope_hash=get_page_scope_hash(page),
        fingerprint=submission_fingerprint,
    )


def release_submission_nonce(
    *,
    page: ContactPage,
    nonce_hash: str,
) -> bool:
    return _release_reservation(
        kind=str(SecurityEventKind.SUBMISSION_NONCE),
        scope_hash=get_page_scope_hash(page),
        fingerprint=nonce_hash,
    )


def consume_post_rate_limit(
    *,
    page: ContactPage,
    request: HttpRequest,
) -> tuple[SecurityWindowDecision, str]:
    client_fingerprint = get_client_fingerprint(request)
    limit = get_positive_int_setting("CONTACT_FORM_POST_LIMIT", DEFAULT_POST_LIMIT)
    window_seconds = get_positive_int_setting(
        "CONTACT_FORM_POST_WINDOW_SECONDS",
        DEFAULT_POST_WINDOW_SECONDS,
    )
    decision = acquire_security_window(
        kind=str(SecurityEventKind.POST_RATE_LIMIT),
        scope_hash=get_page_scope_hash(page),
        fingerprint=client_fingerprint,
        duration=timedelta(seconds=window_seconds),
        limit=limit,
    )
    return decision, client_fingerprint


def reserve_duplicate_submission(
    *,
    page: ContactPage,
    submission_fingerprint: str,
) -> SecurityWindowDecision:
    duration_seconds = get_positive_int_setting(
        "CONTACT_FORM_DUPLICATE_WINDOW_SECONDS",
        DEFAULT_DUPLICATE_WINDOW_SECONDS,
    )
    return _reserve_once(
        kind=str(SecurityEventKind.DUPLICATE_CONTENT),
        scope_hash=get_page_scope_hash(page),
        fingerprint=submission_fingerprint,
        duration_seconds=duration_seconds,
    )


def reserve_submission_nonce(
    *,
    page: ContactPage,
    nonce_hash: str,
) -> SecurityWindowDecision:
    maximum_age_seconds = get_positive_int_setting(
        "CONTACT_FORM_TOKEN_MAX_AGE_SECONDS",
        DEFAULT_TOKEN_MAX_AGE_SECONDS,
    )
    return _reserve_once(
        kind=str(SecurityEventKind.SUBMISSION_NONCE),
        scope_hash=get_page_scope_hash(page),
        fingerprint=nonce_hash,
        duration_seconds=maximum_age_seconds,
    )
