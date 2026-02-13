from collections.abc import Mapping


def update(d: dict, u: dict) -> dict:
    """
    Handy tool to recursively update dicts.
    """
    for k, v in u.items():
        existing = d.get(k)
        if isinstance(v, Mapping) and isinstance(existing, dict):
            update(existing, v)
        else:
            d[k] = v
    return d
