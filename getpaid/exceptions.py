class GetPaidException(Exception):
    def __init__(self, *args, **kwargs):
        self.context = kwargs.pop("context", None)
        super().__init__(*args)


class ChargeFailure(GetPaidException):
    pass


class LockFailure(GetPaidException):
    pass
