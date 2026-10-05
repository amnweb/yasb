"""What the footer tells you about a subscription in trouble.

    python -m pytest tests/cloud/test_footer_reason.py -q

A past_due subscription carries one reason code, `payment_past_due`, for three states: still
writable, read-only, and closed. Reading the code alone would tell someone whose payment is
only being retried that their backups had stopped.
"""

from core.cloud.models import Access
from core.cloud.ui.window import _reason


def test_a_retrying_payment_names_the_problem_without_claiming_backups_stopped():
    access = Access(can_read=True, can_write=True, reason="payment_past_due")

    assert _reason(access) == "Payment failed", "still writable, so nothing may be described as blocked"


def test_a_lapsed_payment_says_the_subscription_ended_once_writes_stop():
    access = Access(can_read=True, can_write=False, reason="payment_past_due")

    assert _reason(access) == "Subscription ended"


def test_the_end_of_the_download_window_is_not_still_called_paused():
    access = Access(can_read=False, can_write=False, reason="payment_past_due")

    assert _reason(access) == "Subscription expired"


def test_an_expired_subscription_reads_the_same_however_it_lapsed():
    assert _reason(Access(reason="subscription_expired")) == "Subscription expired"


def test_never_having_subscribed_is_not_an_expiry():
    assert _reason(Access(reason="no_subscription")) == "No active subscription"
