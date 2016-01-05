default_app_config = 'getpaid.apps.Config'


def register_to_payment(*args, **kwargs):
    """
    Thin proxy for actual register_to_payment to prevent uncontrolled early loading of models directory.
    """
    from . import models
    return models.register_to_payment(*args, **kwargs)
