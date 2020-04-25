class GetPaidException(Exception):
    def __init__(self, *args, **kwargs):
        self.context = kwargs.pop("context", None)
        super().__init__(*args)


class CommunicationError(GetPaidException):
    pass


class ChargeFailure(CommunicationError):
    pass


class LockFailure(CommunicationError):
    pass


class RefundFailure(CommunicationError):
    pass


class CredentialsError(GetPaidException):
    pass
