import pytest
import swapper

from getpaid.status import FraudStatus as fs
from getpaid.status import PaymentStatus as ps

pytestmark = pytest.mark.django_db

Payment = swapper.load_model('getpaid', 'Payment')


def test_payment_status_values_available(payment_factory):
    payment = payment_factory()
    assert payment.status == ps.NEW
    assert ps.PREPARED == 'prepared'
    assert ps.PRE_AUTH == 'pre-auth'
    assert ps.PAID == 'paid'


def test_flag_as_fraud_sets_rejected(payment_factory):
    payment = payment_factory()

    payment.flag_as_fraud(message='Suspicious IP')
    payment.save()

    assert payment.fraud_status == fs.REJECTED
    assert payment.fraud_message == 'Suspicious IP'


def test_flag_as_legit_sets_accepted(payment_factory):
    payment = payment_factory()

    payment.flag_as_legit(message='Verified buyer')
    payment.save()

    assert payment.fraud_status == fs.ACCEPTED
    assert payment.fraud_message == 'Verified buyer'


def test_flag_for_check_sets_check(payment_factory):
    payment = payment_factory()

    payment.flag_for_check(message='Needs review')
    payment.save()

    assert payment.fraud_status == fs.CHECK
    assert payment.fraud_message == 'Needs review'
