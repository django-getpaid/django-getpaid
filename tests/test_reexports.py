"""Tests that getpaid re-exports core types correctly."""



class TestEnumIsNotWrapper:
    """After the metaclass removal, PaymentStatus and FraudStatus must be
    the core StrEnum classes directly — not _EnumWrapper proxies."""

    def test_payment_status_is_core_enum(self):
        """getpaid.types.PaymentStatus IS getpaid_core.enums.PaymentStatus."""
        from getpaid_core.enums import PaymentStatus as CorePS

        from getpaid.types import PaymentStatus

        assert PaymentStatus is CorePS

    def test_fraud_status_is_core_enum(self):
        """getpaid.types.FraudStatus IS getpaid_core.enums.FraudStatus."""
        from getpaid_core.enums import FraudStatus as CoreFS

        from getpaid.types import FraudStatus

        assert FraudStatus is CoreFS

    def test_no_enum_wrapper_in_types_module(self):
        """The _EnumWrapper and _EnumWrapperMeta classes must not exist."""
        import getpaid.types as types_mod

        assert not hasattr(types_mod, '_EnumWrapper')
        assert not hasattr(types_mod, '_EnumWrapperMeta')

    def test_no_metaclass_in_getpaid_namespace(self):
        """No _EnumWrapperMeta should be importable from getpaid."""
        import getpaid

        assert not hasattr(getpaid, '_EnumWrapperMeta')

    def test_payment_status_is_str_enum_subclass(self):
        """PaymentStatus must be a StrEnum (or at least behave like one)."""
        from getpaid.types import PaymentStatus

        assert issubclass(PaymentStatus, str)
        assert PaymentStatus.NEW == 'new'
        assert PaymentStatus.PAID == 'paid'

    def test_fraud_status_is_str_enum_subclass(self):
        from getpaid.types import FraudStatus

        assert issubclass(FraudStatus, str)
        assert FraudStatus.UNKNOWN == 'unknown'
        assert FraudStatus.ACCEPTED == 'accepted'

    def test_choices_are_plain_tuples(self):
        """PAYMENT_STATUS_CHOICES and FRAUD_STATUS_CHOICES must be plain
        tuples of (value, label) — not classproperties on a wrapper."""
        from getpaid.types import FRAUD_STATUS_CHOICES, PAYMENT_STATUS_CHOICES

        assert isinstance(PAYMENT_STATUS_CHOICES, tuple)
        assert isinstance(FRAUD_STATUS_CHOICES, tuple)
        # Each entry is (str, str)
        for value, _label in PAYMENT_STATUS_CHOICES:
            assert isinstance(value, str)
        for value, _label in FRAUD_STATUS_CHOICES:
            assert isinstance(value, str)

    def test_choices_values_match_core_enum(self):
        """The first element of each choice tuple must equal the core
        enum member's .value."""
        from getpaid.types import PAYMENT_STATUS_CHOICES, PaymentStatus

        for member in PaymentStatus:
            matching = [c for c in PAYMENT_STATUS_CHOICES if c[0] == member.value]
            assert len(matching) == 1, f'No choice for {member.value!r}'

    def test_payment_status_new_works_as_django_default(self):
        """PaymentStatus.NEW must be usable as a Django CharField default.
        StrEnum members compare equal to their string value."""
        from getpaid.types import PaymentStatus

        # This is what Django does internally: stores the value
        assert PaymentStatus.NEW == 'new'
        assert str(PaymentStatus.NEW) == 'new'

    def test_status_identity_across_imports(self):
        """Importing PaymentStatus from getpaid, getpaid.types, or
        getpaid_core.enums must yield the same object."""
        from getpaid_core.enums import PaymentStatus as CorePS

        import getpaid
        from getpaid.types import PaymentStatus

        assert getpaid.PaymentStatus is PaymentStatus
        assert PaymentStatus is CorePS

    def test_fraud_status_identity_across_imports(self):
        from getpaid_core.enums import FraudStatus as CoreFS

        import getpaid
        from getpaid.types import FraudStatus

        assert getpaid.FraudStatus is FraudStatus
        assert FraudStatus is CoreFS

    def test_isinstance_check_works(self):
        """isinstance(PaymentStatus.NEW, PaymentStatus) must be True."""
        from getpaid.types import PaymentStatus

        assert isinstance(PaymentStatus.NEW, PaymentStatus)
        assert isinstance(PaymentStatus.PAID, PaymentStatus)

    def test_no_wrapper_module_attributes(self):
        """The types module should not contain any wrapper-related
        attributes beyond the re-exports and CHOICES constants."""
        import getpaid.types as mod

        wrapper_names = [
            name for name in dir(mod)
            if 'wrapper' in name.lower() or 'Wrapper' in name
        ]
        assert wrapper_names == [], f'Found wrapper artifacts: {wrapper_names}'


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
        """PAYMENT_STATUS_CHOICES must be a plain tuple of (value, label)."""
        from getpaid.types import PAYMENT_STATUS_CHOICES

        choices = PAYMENT_STATUS_CHOICES
        assert isinstance(choices, tuple)
        assert len(choices) == 9
        for value, _label in choices:
            assert isinstance(value, str)

    def test_fraud_status_has_choices(self):
        from getpaid.types import FRAUD_STATUS_CHOICES

        choices = FRAUD_STATUS_CHOICES
        assert isinstance(choices, tuple)
        assert len(choices) == 4

    def test_choices_in_getpaid_namespace(self):
        """getpaid package should re-export CHOICES constants."""
        import getpaid

        assert hasattr(getpaid, 'PAYMENT_STATUS_CHOICES')
        assert hasattr(getpaid, 'FRAUD_STATUS_CHOICES')
        assert isinstance(getpaid.PAYMENT_STATUS_CHOICES, tuple)
        assert isinstance(getpaid.FRAUD_STATUS_CHOICES, tuple)

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
        resp = ChargeResponse(
            amount_charged=Decimal(10),
            success=True,
            async_call=False,
        )
        assert resp.success is True

    def test_backend_method_enum(self):
        assert BackendMethod.GET == 'GET'
        assert BackendMethod.POST == 'POST'
        assert BackendMethod.REST == 'REST'

    def test_confirmation_method_enum(self):
        assert ConfirmationMethod.PUSH == 'PUSH'
        assert ConfirmationMethod.PULL == 'PULL'
