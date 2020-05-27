import pytest
import swapper
from django.conf import settings
from django_fsm import can_proceed

from getpaid.status import PaymentStatus as ps

dummy = settings.GETPAID_DUMMY_SLUG

Order = swapper.load_model("getpaid", "Order")
Payment = swapper.load_model("getpaid", "Payment")

pytestmark = pytest.mark.django_db


def test_fsm_direct_prepare(payment_factory):
    payment = payment_factory()
    assert payment.status == ps.NEW
    payment.confirm_prepared()
    assert payment.status == ps.PREPARED


def test_fsm_check_available_transitions_from_new(payment_factory):
    payment = payment_factory()
    assert payment.status == ps.NEW

    assert can_proceed(payment.confirm_prepared)
    assert can_proceed(payment.confirm_lock)
    assert not can_proceed(payment.confirm_charge_sent)
    assert not can_proceed(payment.confirm_payment)
    assert not can_proceed(payment.mark_as_paid)
    assert not can_proceed(payment.release_lock)
    assert not can_proceed(payment.start_refund)
    assert not can_proceed(payment.cancel_refund)
    assert not can_proceed(payment.confirm_refund)
    assert not can_proceed(payment.mark_as_refunded)
    assert can_proceed(payment.fail)


def test_fsm_check_available_transitions_from_failed(payment_factory):
    payment = payment_factory()
    payment.fail()
    assert payment.status == ps.FAILED

    assert not can_proceed(payment.confirm_prepared)
    assert not can_proceed(payment.confirm_lock)
    assert not can_proceed(payment.confirm_charge_sent)
    assert not can_proceed(payment.confirm_payment)
    assert not can_proceed(payment.mark_as_paid)
    assert not can_proceed(payment.release_lock)
    assert not can_proceed(payment.start_refund)
    assert not can_proceed(payment.cancel_refund)
    assert not can_proceed(payment.confirm_refund)
    assert not can_proceed(payment.mark_as_refunded)
    assert not can_proceed(payment.fail)


def test_fsm_check_available_transitions_from_prepared(payment_factory):
    payment = payment_factory()
    payment.confirm_prepared()
    assert payment.status == ps.PREPARED

    assert not can_proceed(payment.confirm_prepared)
    assert can_proceed(payment.confirm_lock)
    assert not can_proceed(payment.confirm_charge_sent)
    assert can_proceed(payment.confirm_payment)
    assert not can_proceed(payment.mark_as_paid)
    assert not can_proceed(payment.release_lock)
    assert not can_proceed(payment.start_refund)
    assert not can_proceed(payment.cancel_refund)
    assert not can_proceed(payment.confirm_refund)
    assert not can_proceed(payment.mark_as_refunded)
    assert can_proceed(payment.fail)


def test_fsm_check_available_transitions_from_locked(payment_factory):
    payment = payment_factory()
    payment.confirm_lock()
    assert payment.status == ps.PRE_AUTH

    assert not can_proceed(payment.confirm_prepared)
    assert not can_proceed(payment.confirm_lock)
    assert can_proceed(payment.confirm_charge_sent)
    assert can_proceed(payment.confirm_payment)
    assert not can_proceed(payment.mark_as_paid)
    assert can_proceed(payment.release_lock)
    assert not can_proceed(payment.start_refund)
    assert not can_proceed(payment.cancel_refund)
    assert not can_proceed(payment.confirm_refund)
    assert not can_proceed(payment.mark_as_refunded)
    assert can_proceed(payment.fail)


def test_fsm_check_available_transitions_from_partial(payment_factory):
    payment = payment_factory()
    payment.confirm_lock()
    payment.confirm_payment()
    assert payment.status == ps.PARTIAL

    assert not can_proceed(payment.confirm_prepared)
    assert not can_proceed(payment.confirm_lock)
    assert not can_proceed(payment.confirm_charge_sent)
    assert can_proceed(payment.confirm_payment)
    assert can_proceed(payment.mark_as_paid)
    assert not can_proceed(payment.release_lock)
    assert can_proceed(payment.start_refund)
    assert not can_proceed(payment.cancel_refund)
    assert not can_proceed(payment.confirm_refund)
    assert not can_proceed(payment.fail)
    assert not can_proceed(payment.mark_as_refunded)  # condition not met

    payment.amount_refunded = payment.amount_required
    assert can_proceed(payment.mark_as_refunded)


def test_fsm_check_available_transitions_from_paid(payment_factory):
    payment = payment_factory()
    payment.confirm_lock()
    payment.confirm_payment()
    payment.mark_as_paid()
    assert payment.status == ps.PAID

    assert not can_proceed(payment.confirm_prepared)
    assert not can_proceed(payment.confirm_lock)
    assert not can_proceed(payment.confirm_charge_sent)
    assert not can_proceed(payment.confirm_payment)
    assert not can_proceed(payment.mark_as_paid)
    assert not can_proceed(payment.release_lock)
    assert can_proceed(payment.start_refund)
    assert not can_proceed(payment.cancel_refund)
    assert not can_proceed(payment.confirm_refund)
    assert not can_proceed(payment.mark_as_refunded)
    assert not can_proceed(payment.fail)
