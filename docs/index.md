# django-getpaid

**django-getpaid** is a multi-broker payment processing framework for Django.

## Features

- Multiple payment brokers at the same time
- Flexible plugin architecture via [getpaid-core](https://github.com/django-getpaid/getpaid-core)
- Asynchronous status updates — both push and pull
- REST-based broker API support
- Multiple currencies (one per payment)
- Global and per-plugin validators
- Swappable Payment and Order models (like Django's User model)
- Runtime FSM for payment status transitions (no django-fsm dependency)

```{toctree}
:maxdepth: 2
:caption: User Guide

getting-started
configuration
customization
migration-v2-to-v3
```

```{toctree}
:maxdepth: 2
:caption: Plugin Development

plugins
plugin-catalog
registry
```

```{toctree}
:maxdepth: 2
:caption: API Reference

api/index
```

```{toctree}
:maxdepth: 1
:caption: Project

roadmap
changelog
contributing
```

## Credits

Created by [Krzysztof Dorosz](https://github.com/cypreess).
Redesigned and rewritten by [Dominik Kozaczko](https://github.com/dekoza).

Development of version 2.0 sponsored by [SUNSCRAPERS](https://sunscrapers.com/).
