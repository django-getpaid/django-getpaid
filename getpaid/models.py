import swapper

from .abstracts import AbstractOrder, AbstractPayment  # noqa


class Payment(AbstractPayment):
    class Meta(AbstractPayment.Meta):
        swappable = swapper.swappable_setting("getpaid", "Payment")
