__version__ = '1.8.0-rc1'
default_app_config = 'getpaid.apps.GetpaidConfig'


def register_to_payment(*args, **kwargs):
    """
    Thin proxy for actual register_to_payment to prevent uncontrolled early loading of models directory.
    """
    from . import models
    return models.register_to_payment(*args, **kwargs)
