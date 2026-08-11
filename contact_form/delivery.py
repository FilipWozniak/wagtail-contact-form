from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from email.utils import make_msgid
from typing import TYPE_CHECKING
from typing import Any
from typing import Iterable
from typing import Literal

from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.mail import get_connection
from django.db.models import F
from django.db.models import Q
from django.utils import timezone

if TYPE_CHECKING:
    from wagtail.contrib.forms.models import FormSubmission

    from contact_form.models import ContactEmailDelivery

logger = logging.getLogger(__name__)

DEFAULT_EMAIL_TIMEOUT_SECONDS = 10.0
DEFAULT_STALE_SENDING_MINUTES = 15

PENDING: Literal["pending"] = "pending"
SENDING: Literal["sending"] = "sending"
SENT: Literal["sent"] = "sent"
FAILED: Literal["failed"] = "failed"
UNKNOWN: Literal["unknown"] = "unknown"

DeliveryStatus = Literal["pending", "sending", "sent", "failed", "unknown"]

_DEFAULT_RETRYABLE_STATUSES = (PENDING, FAILED)
_SEND_STARTED_MESSAGE = (
    "The email backend raised an exception after delivery started; "
    "delivery may have succeeded and requires manual review."
)
_CONNECTION_FAILED_MESSAGE = "The configured email connection could not be opened."
_MESSAGE_NOT_SENT_MESSAGE = "The email backend reported that no message was sent."
_MESSAGE_BUILD_FAILED_MESSAGE = "The stored email delivery could not be prepared."
_STALE_SENDING_MESSAGE = (
    "The sending process exceeded its safety window or ended unexpectedly; "
    "delivery may have succeeded and requires manual review."
)


@dataclass(frozen=True, slots=True)
class DeliveryAttemptResult:
    """The durable outcome of one requested delivery attempt."""

    delivery_id: int
    status: DeliveryStatus
    attempted: bool
    sent_count: int = 0


def parse_recipient_addresses(addresses: str | Iterable[str]) -> list[str]:

    candidates = addresses.split(",") if isinstance(addresses, str) else addresses
    recipients: list[str] = []
    seen: set[str] = set()

    for candidate in candidates:
        address = str(candidate).strip()
        normalized_address = address.casefold()
        if not address or normalized_address in seen:
            continue
        recipients.append(address)
        seen.add(normalized_address)

    return recipients


def create_email_delivery(
    *,
    submission: FormSubmission,
    recipients: str | Iterable[str],
    subject: str,
    body: str,
    from_address: str | None,
    submission_nonce_hash: str,
) -> ContactEmailDelivery:

    recipient_list = parse_recipient_addresses(recipients)
    if not recipient_list:
        raise ValueError("At least one email recipient is required.")
    if not submission_nonce_hash:
        raise ValueError("A submission nonce hash is required.")

    delivery_model = _get_delivery_model()
    resolved_from_address = from_address or settings.DEFAULT_FROM_EMAIL

    return delivery_model.objects.create(
        submission=submission,
        status=PENDING,
        recipients=recipient_list,
        subject=subject,
        body=body,
        from_address=resolved_from_address,
        message_id=make_msgid(),
        submission_nonce_hash=submission_nonce_hash,
    )


def attempt_email_delivery(
    delivery: ContactEmailDelivery | int,
    *,
    retry_unknown: bool = False,
) -> DeliveryAttemptResult:

    _exclude_delivery_logger_from_sentry()
    delivery_id = _get_delivery_id(delivery)
    delivery_model = _get_delivery_model()
    retryable_statuses = list(_DEFAULT_RETRYABLE_STATUSES)
    if retry_unknown:
        retryable_statuses.append(UNKNOWN)

    attempt_started_at = timezone.now()
    claimed_count = delivery_model.objects.filter(
        pk=delivery_id,
        status__in=retryable_statuses,
    ).update(
        status=SENDING,
        attempt_count=F("attempt_count") + 1,
        last_error_type="",
        last_error_message="",
        started_at=attempt_started_at,
        sent_at=None,
        updated_at=attempt_started_at,
    )

    if claimed_count == 0:
        current_status = delivery_model.objects.values_list("status", flat=True).get(pk=delivery_id)
        return DeliveryAttemptResult(
            delivery_id=delivery_id,
            status=_coerce_status(current_status),
            attempted=False,
        )

    claimed_delivery = delivery_model.objects.select_related("submission").get(pk=delivery_id)
    claim_started_at = claimed_delivery.started_at or attempt_started_at

    try:
        message = _build_message(
            claimed_delivery,
            claim_started_at=claim_started_at,
        )
    except Exception as error:
        error_type = _safe_exception_type(error)
        final_status = _finish_attempt(
            delivery_id,
            claim_started_at=claim_started_at,
            status=FAILED,
            error_type=error_type,
            error_message=_MESSAGE_BUILD_FAILED_MESSAGE,
        )
        _report_delivery_problem(
            delivery_id=delivery_id,
            submission_id=claimed_delivery.submission_id,
            phase="message_build",
            exception_type=error_type,
            resulting_status=final_status,
        )
        return DeliveryAttemptResult(delivery_id, final_status, attempted=True)

    connection: Any | None = None
    try:
        connection = get_connection(
            fail_silently=False,
            timeout=_get_email_timeout_seconds(),
        )
        connection.open()
    except Exception as error:
        error_type = _safe_exception_type(error)
        final_status = _finish_attempt(
            delivery_id,
            claim_started_at=claim_started_at,
            status=FAILED,
            error_type=error_type,
            error_message=_CONNECTION_FAILED_MESSAGE,
        )
        _report_delivery_problem(
            delivery_id=delivery_id,
            submission_id=claimed_delivery.submission_id,
            phase="connection_open",
            exception_type=error_type,
            resulting_status=final_status,
        )
        _close_connection_safely(
            connection,
            delivery_id=delivery_id,
            submission_id=claimed_delivery.submission_id,
        )
        return DeliveryAttemptResult(delivery_id, final_status, attempted=True)

    try:
        sent_count = int(connection.send_messages([message]))
    except Exception as error:
        error_type = _safe_exception_type(error)
        final_status = _finish_attempt(
            delivery_id,
            claim_started_at=claim_started_at,
            status=UNKNOWN,
            error_type=error_type,
            error_message=_SEND_STARTED_MESSAGE,
        )
        _report_delivery_problem(
            delivery_id=delivery_id,
            submission_id=claimed_delivery.submission_id,
            phase="message_send",
            exception_type=error_type,
            resulting_status=final_status,
        )
        _close_connection_safely(
            connection,
            delivery_id=delivery_id,
            submission_id=claimed_delivery.submission_id,
        )
        return DeliveryAttemptResult(delivery_id, final_status, attempted=True)

    if sent_count > 0:
        final_status = _finish_attempt(
            delivery_id,
            claim_started_at=claim_started_at,
            status=SENT,
            sent_at=timezone.now(),
        )
    else:
        final_status = _finish_attempt(
            delivery_id,
            claim_started_at=claim_started_at,
            status=FAILED,
            error_type="EmailBackendReturnedZero",
            error_message=_MESSAGE_NOT_SENT_MESSAGE,
        )
        _report_delivery_problem(
            delivery_id=delivery_id,
            submission_id=claimed_delivery.submission_id,
            phase="message_send",
            exception_type="EmailBackendReturnedZero",
            resulting_status=final_status,
        )

    _close_connection_safely(
        connection,
        delivery_id=delivery_id,
        submission_id=claimed_delivery.submission_id,
    )
    return DeliveryAttemptResult(
        delivery_id=delivery_id,
        status=final_status,
        attempted=True,
        sent_count=sent_count,
    )


def attempt_email_delivery_after_commit(
    delivery: ContactEmailDelivery | int,
) -> DeliveryAttemptResult | None:

    delivery_id: int | None = None
    try:
        delivery_id = _get_delivery_id(delivery)
        return attempt_email_delivery(delivery_id)
    except Exception as error:
        exception_type = _safe_exception_type(error)
        submission_id = _get_submission_id_safely(delivery_id)
        try:
            _report_delivery_problem(
                delivery_id=delivery_id,
                submission_id=submission_id,
                phase="delivery_state",
                exception_type=exception_type,
                resulting_status=None,
            )
        except Exception:
            pass
        return None


def mark_stale_sending_deliveries_unknown(
    *,
    stale_after: timedelta | None = None,
) -> int:

    safety_window = stale_after if stale_after is not None else _get_stale_sending_window()
    if safety_window.total_seconds() <= 0:
        raise ValueError("The stale sending safety window must be positive.")

    now = timezone.now()
    cutoff = now - safety_window
    delivery_model = _get_delivery_model()
    updated_count = (
        delivery_model.objects.filter(status=SENDING)
        .filter(Q(started_at__lte=cutoff) | Q(started_at__isnull=True))
        .update(
            status=UNKNOWN,
            last_error_type="StaleSendingAttempt",
            last_error_message=_STALE_SENDING_MESSAGE,
            sent_at=None,
            updated_at=now,
        )
    )
    if updated_count:
        logger.warning(
            "Marked %s stale contact form email delivery attempt(s) as unknown.",
            updated_count,
        )
    return int(updated_count)


def _get_delivery_model() -> Any:
    return apps.get_model("contact_form", "ContactEmailDelivery")


def _get_submission_id_safely(delivery_id: int | None) -> int | None:
    if delivery_id is None:
        return None

    try:
        submission_id = (
            _get_delivery_model().objects.filter(pk=delivery_id).values_list("submission_id", flat=True).first()
        )
    except Exception:
        return None
    return int(submission_id) if submission_id is not None else None


def _get_delivery_id(delivery: ContactEmailDelivery | int) -> int:
    if isinstance(delivery, int):
        return delivery

    delivery_id = getattr(delivery, "pk", None)
    if delivery_id is None:
        raise ValueError("The email delivery must be saved before it can be attempted.")
    return int(delivery_id)


def _get_email_timeout_seconds() -> float:
    configured_timeout = getattr(
        settings,
        "CONTACT_FORM_EMAIL_TIMEOUT_SECONDS",
        getattr(settings, "EMAIL_TIMEOUT", DEFAULT_EMAIL_TIMEOUT_SECONDS),
    )
    if configured_timeout is None:
        return DEFAULT_EMAIL_TIMEOUT_SECONDS

    try:
        timeout = float(configured_timeout)
    except (TypeError, ValueError):
        logger.warning(
            "Ignoring invalid contact form email timeout; using the finite default of %.1f seconds.",
            DEFAULT_EMAIL_TIMEOUT_SECONDS,
        )
        return DEFAULT_EMAIL_TIMEOUT_SECONDS

    if not math.isfinite(timeout) or timeout <= 0:
        logger.warning(
            "Ignoring non-positive contact form email timeout; using the finite default of %.1f seconds.",
            DEFAULT_EMAIL_TIMEOUT_SECONDS,
        )
        return DEFAULT_EMAIL_TIMEOUT_SECONDS
    return timeout


def _get_stale_sending_window() -> timedelta:
    raw_minutes = getattr(
        settings,
        "CONTACT_FORM_EMAIL_STALE_SENDING_MINUTES",
        DEFAULT_STALE_SENDING_MINUTES,
    )
    try:
        minutes = float(raw_minutes)
    except (TypeError, ValueError):
        minutes = float(DEFAULT_STALE_SENDING_MINUTES)

    if not math.isfinite(minutes) or minutes <= 0:
        minutes = float(DEFAULT_STALE_SENDING_MINUTES)
    return timedelta(minutes=minutes)


def _build_message(
    delivery: ContactEmailDelivery,
    *,
    claim_started_at: datetime,
) -> EmailMultiAlternatives:
    recipients = delivery.recipients
    if not isinstance(recipients, list) or not recipients:
        raise ValueError("The stored recipient list is invalid.")
    if any(not isinstance(address, str) or not address.strip() for address in recipients):
        raise ValueError("The stored recipient list is invalid.")

    message_id = str(delivery.message_id).strip()
    if not message_id:
        message_id = make_msgid()
        delivery_model = _get_delivery_model()
        delivery_model.objects.filter(
            pk=delivery.pk,
            status=SENDING,
            started_at=claim_started_at,
        ).update(
            message_id=message_id,
            updated_at=timezone.now(),
        )

    return EmailMultiAlternatives(
        subject=delivery.subject,
        body=delivery.body,
        from_email=delivery.from_address or None,
        to=recipients,
        headers={
            "Message-ID": message_id,
            "X-Contact-Submission-ID": str(delivery.submission_id),
            "Auto-Submitted": "auto-generated",
        },
    )


def _finish_attempt(
    delivery_id: int,
    *,
    claim_started_at: datetime,
    status: DeliveryStatus,
    error_type: str = "",
    error_message: str = "",
    sent_at: Any | None = None,
) -> DeliveryStatus:
    delivery_model = _get_delivery_model()
    updated_count = delivery_model.objects.filter(
        pk=delivery_id,
        status=SENDING,
        started_at=claim_started_at,
    ).update(
        status=status,
        last_error_type=error_type,
        last_error_message=error_message,
        sent_at=sent_at,
        updated_at=timezone.now(),
    )
    if updated_count:
        return status

    current_status = delivery_model.objects.values_list("status", flat=True).get(pk=delivery_id)
    return _coerce_status(current_status)


def _close_connection_safely(
    connection: Any | None,
    *,
    delivery_id: int,
    submission_id: int,
) -> None:
    if connection is None:
        return

    try:
        connection.close()
    except Exception as error:
        exception_type = _safe_exception_type(error)
        _report_delivery_problem(
            delivery_id=delivery_id,
            submission_id=submission_id,
            phase="connection_close",
            exception_type=exception_type,
            resulting_status=None,
            level="warning",
        )


def _report_delivery_problem(
    *,
    delivery_id: int | None,
    submission_id: int | None,
    phase: str,
    exception_type: str,
    resulting_status: DeliveryStatus | None,
    level: Literal["warning", "error"] = "error",
) -> None:

    _exclude_delivery_logger_from_sentry()
    log_method = logger.warning if level == "warning" else logger.error
    try:
        log_method(
            "Contact Form Email Delivery Problem: delivery_id=%s submission_id=%s phase=%s "
            "exception_type=%s resulting_status=%s",
            delivery_id if delivery_id is not None else "unknown",
            submission_id if submission_id is not None else "unknown",
            phase,
            exception_type,
            resulting_status or "unchanged",
        )
    except Exception:
        pass

    try:
        import sentry_sdk

        client = sentry_sdk.get_client()
        scope = sentry_sdk.Scope()
        scope.set_client(client)
        scope.set_tag("component", "contact_form_email")
        scope.set_tag("delivery_phase", phase)
        scope.set_tag("delivery_status", resulting_status or "unchanged")
        scope.set_tag("exception_type", exception_type)
        scope.fingerprint = ["contact-form-email", phase, exception_type]
        if delivery_id is not None:
            scope.set_extra("delivery_id", delivery_id)
        if submission_id is not None:
            scope.set_extra("submission_id", submission_id)
        client.capture_event(
            event={
                "message": "Contact Form Email Delivery Failed",
                "level": level,
            },
            scope=scope,
        )
    except ImportError:
        return
    except Exception as reporting_error:
        try:
            logger.debug(
                "Unable to Report Contact Form Email Delivery Problem to Sentry: exception_type=%s",
                _safe_exception_type(reporting_error),
            )
        except Exception:
            pass


def _exclude_delivery_logger_from_sentry() -> None:

    try:
        from sentry_sdk.integrations.logging import ignore_logger

        ignore_logger(logger.name)
    except Exception:
        pass


def _safe_exception_type(error: Exception) -> str:
    return type(error).__name__[:255]


def _coerce_status(status: Any) -> DeliveryStatus:
    if status not in {PENDING, SENDING, SENT, FAILED, UNKNOWN}:
        raise ValueError(f"Unsupported Contact Email Delivery Status: {status!r}")
    return status
