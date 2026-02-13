"""Tests that getpaid re-exports core types correctly."""

from decimal import Decimal

from getpaid_core.enums import FraudStatus as CoreFS
from getpaid_core.enums import PaymentStatus as CorePS

from getpaid.exceptions import (
    ChargeFailure,
    CommunicationError,
    GetPaidException,
    InvalidCallbackError,
    InvalidTransitionError,
    LockFailure,
    RefundFailure,
)
from getpaid.status import FraudStatus as StatusFS
from getpaid.status import PaymentStatus as StatusPS
from getpaid.types import (
    BackendMethod,
    BuyerInfo,
    ChargeResponse,
    ConfirmationMethod,
    FraudStatus,
    ItemInfo,
    PaymentStatus,
)


class TestEnumReExports:
    def test_payment_status_values_match_core(self):
        """PaymentStatus values must exactly match core."""
        assert PaymentStatus.NEW == CorePS.NEW
        assert PaymentStatus.PRE_AUTH == CorePS.PRE_AUTH
        assert PaymentStatus.PRE_AUTH == 'pre-auth'
        assert PaymentStatus.IN_CHARGE == CorePS.IN_CHARGE
        assert PaymentStatus.IN_CHARGE == 'charge_started'
        assert PaymentStatus.PARTIAL == CorePS.PARTIAL
        assert PaymentStatus.PARTIAL == 'partially_paid'

    def test_fraud_status_values_match_core(self):
        assert FraudStatus.UNKNOWN == CoreFS.UNKNOWN
        assert FraudStatus.ACCEPTED == CoreFS.ACCEPTED

    def test_payment_status_has_choices(self):
        """Django wrapper must provide .choices and .CHOICES."""
        choices = PaymentStatus.choices
        assert isinstance(choices, tuple)
        assert len(choices) == 9
        # Each choice is (value, label) tuple
        for value, _label in choices:
            assert isinstance(value, str)

    def test_fraud_status_has_choices(self):
        choices = FraudStatus.choices
        assert isinstance(choices, tuple)
        assert len(choices) == 4

    def test_choices_backward_compat(self):
        """CHOICES (uppercase) must equal choices."""
        assert PaymentStatus.choices == PaymentStatus.CHOICES
        assert FraudStatus.choices == FraudStatus.CHOICES

    def test_status_compat_module(self):
        """getpaid.status should re-export the same classes."""
        assert StatusPS is PaymentStatus
        assert StatusFS is FraudStatus

    def test_payment_status_members_all_present(self):
        """All core members must be present in Django enum."""
        for member in CorePS:
            assert hasattr(PaymentStatus, member.name)
            assert PaymentStatus[member.name].value == member.value

    def test_fraud_status_members_all_present(self):
        for member in CoreFS:
            assert hasattr(FraudStatus, member.name)
            assert FraudStatus[member.name].value == member.value


class TestExceptionReExports:
    def test_getpaid_exception_is_core(self):
        """Our GetPaidException should be the core one."""
        from getpaid_core.exceptions import (
            GetPaidException as CoreGPE,
        )

        assert GetPaidException is CoreGPE

    def test_charge_failure_is_communication_error(self):
        assert issubclass(ChargeFailure, CommunicationError)

    def test_lock_failure_is_communication_error(self):
        assert issubclass(LockFailure, CommunicationError)

    def test_refund_failure_is_communication_error(self):
        assert issubclass(RefundFailure, CommunicationError)

    def test_exception_accepts_context_kwarg(self):
        """Backward compat: context kwarg must work."""
        exc = GetPaidException('test', context={'key': 'val'})
        assert exc.context == {'key': 'val'}

    def test_invalid_callback_error(self):
        assert issubclass(InvalidCallbackError, GetPaidException)

    def test_invalid_transition_error(self):
        assert issubclass(InvalidTransitionError, GetPaidException)


class TestTypeReExports:
    def test_buyer_info_is_typed_dict(self):
        info: BuyerInfo = {'email': 'a@b.com'}
        assert 'email' in info

    def test_item_info(self):
        item: ItemInfo = {
            'name': 'x',
            'quantity': 1,
            'unit_price': Decimal(10),
        }
        assert item['name'] == 'x'

    def test_charge_response(self):
        resp: ChargeResponse = {
            'amount_charged': Decimal(10),
            'success': True,
            'async_call': False,
        }
        assert resp['success'] is True

    def test_backend_method_enum(self):
        assert BackendMethod.GET == 'GET'
        assert BackendMethod.POST == 'POST'
        assert BackendMethod.REST == 'REST'

    def test_confirmation_method_enum(self):
        assert ConfirmationMethod.PUSH == 'PUSH'
        assert ConfirmationMethod.PULL == 'PULL'
