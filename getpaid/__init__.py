# flake8: noqa
try:
    import importlib.metadata as importlib_metadata
except ModuleNotFoundError:
    import importlib_metadata

from .types import FraudStatus, PaymentStatus

__version__ = importlib_metadata.version("django-getpaid")

default_app_config = "getpaid.apps.GetpaidConfig"
