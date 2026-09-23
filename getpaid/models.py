import swapper

from .abstracts import AbstractOrder, AbstractPayment  # noqa
from .durable_models import (  # noqa: F401
    DurableOperation,
    DurablePaymentState,
    DurableRecordedMoneyEntry,
    DurableReplay,
)


class Payment(AbstractPayment):
    class Meta(AbstractPayment.Meta):
        swappable = swapper.swappable_setting('getpaid', 'Payment')
