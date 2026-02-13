"""FSM transition tests using getpaid-core's transitions library."""

import pytest
import swapper
from getpaid_core.fsm import create_payment_machine

from getpaid.status import PaymentStatus as ps

dummy = 'getpaid.backends.dummy'

Order = swapper.load_model('getpaid', 'Order')
Payment = swapper.load_model('getpaid', 'Payment')

pytestmark = pytest.mark.django_db


def _can_trigger(payment, name):
    """Check if trigger can fire without actually firing."""
    try:
        return payment.may_trigger(name)
    except AttributeError:
        return False


def test_fsm_direct_prepare(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    assert payment.status == ps.NEW
    payment.confirm_prepared()
    assert payment.status == ps.PREPARED


def test_fsm_check_available_transitions_from_new(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    assert payment.status == ps.NEW

    assert _can_trigger(payment, 'confirm_prepared')
    assert _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert not _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_failed(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.fail()
    assert payment.status == ps.FAILED

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert not _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert not _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_prepared(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_prepared()
    assert payment.status == ps.PREPARED

    assert not _can_trigger(payment, 'confirm_prepared')
    assert _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_locked(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_lock()
    assert payment.status == ps.PRE_AUTH

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert _can_trigger(payment, 'confirm_charge_sent')
    assert _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert _can_trigger(payment, 'release_lock')
    assert not _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert _can_trigger(payment, 'fail')


def test_fsm_check_available_transitions_from_partial(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_lock()
    payment.confirm_payment()
    assert payment.status == ps.PARTIAL

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert _can_trigger(payment, 'confirm_payment')
    # mark_as_paid has a guard -- may_trigger may return True
    # but actual trigger will raise MachineError if not fully paid
    assert _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'fail')
    assert _can_trigger(payment, 'mark_as_refunded')


def test_fsm_check_available_transitions_from_paid(payment_factory):
    payment = payment_factory()
    create_payment_machine(payment)
    payment.confirm_lock()
    payment.confirm_payment()
    # Need to set amount_paid for guard
    payment.amount_paid = payment.amount_required
    payment.mark_as_paid()
    assert payment.status == ps.PAID

    assert not _can_trigger(payment, 'confirm_prepared')
    assert not _can_trigger(payment, 'confirm_lock')
    assert not _can_trigger(payment, 'confirm_charge_sent')
    assert not _can_trigger(payment, 'confirm_payment')
    assert not _can_trigger(payment, 'mark_as_paid')
    assert not _can_trigger(payment, 'release_lock')
    assert _can_trigger(payment, 'start_refund')
    assert not _can_trigger(payment, 'cancel_refund')
    assert not _can_trigger(payment, 'confirm_refund')
    assert not _can_trigger(payment, 'mark_as_refunded')
    assert not _can_trigger(payment, 'fail')
