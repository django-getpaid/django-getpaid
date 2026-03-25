from importlib import import_module

from django.conf import settings


def run_getpaid_validators(data: dict) -> dict:
    backend = data['backend']
    getpaid_settings = getattr(settings, 'GETPAID', {})
    global_validators = getpaid_settings.get('VALIDATORS', [])
    backend_settings = getattr(settings, 'GETPAID_BACKEND_SETTINGS', {})
    backend_validators = []

    backend_candidates = [backend]
    if '.' not in backend:
        backend_candidates.append(f'getpaid.backends.{backend}')

    for candidate in backend_candidates:
        validators = backend_settings.get(candidate, {}).get('VALIDATORS', [])
        if validators:
            backend_validators = validators
            break

    unique_validators = list(
        dict.fromkeys(global_validators + backend_validators)
    )
    for path in unique_validators:
        module_name, validator_name = path.rsplit('.', 1)
        module = import_module(module_name)
        validator = getattr(module, validator_name)
        data = validator(data)
    return data
