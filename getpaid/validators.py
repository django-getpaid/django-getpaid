from importlib import import_module

from django.conf import settings


def run_getpaid_validators(data):
    backend = data["backend"]
    getpaid_settings = getattr(settings, "GETPAID", {})
    global_validators = getpaid_settings.get("VALIDATORS", [])
    backend_validators = (
        getpaid_settings.get("BACKENDS", {}).get(backend, {}).get("VALIDATORS", [])
    )
    for path in set(global_validators).union(backend_validators):
        module_name, validator_name = path.rsplit(".", 1)
        module = import_module(module_name)
        validator = getattr(module, validator_name)
        data = validator(data)
    return data
