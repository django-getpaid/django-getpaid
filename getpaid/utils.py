import collections


def update(d: dict, u: dict) -> dict:
    """
    Handy tool to recursively update dicts.
    """
    for k, v in u.items():
        if isinstance(v, collections.Mapping):
            d[k] = update(d.get(k, {}), v)
        else:
            d[k] = v
    return d
