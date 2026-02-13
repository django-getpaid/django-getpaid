# Contributor Guide

Contributions are welcome, and they are greatly appreciated! Every
little bit helps, and credit will always be given.

## Resources

- [Source Code](https://github.com/django-getpaid/django-getpaid)
- [Documentation](https://django-getpaid.readthedocs.io/)
- [Issue Tracker](https://github.com/django-getpaid/django-getpaid/issues)

## How to report a bug

Report bugs on the [Issue Tracker](https://github.com/django-getpaid/django-getpaid/issues).

When filing an issue, include:

- Operating system and Python version
- Django version
- django-getpaid version
- Steps to reproduce
- Expected vs actual behavior

## How to set up your development environment

You need Python 3.12+ and [uv](https://docs.astral.sh/uv/).

Clone and install:

```bash
git clone https://github.com/django-getpaid/django-getpaid.git
cd django-getpaid
uv sync
```

Run tests:

```bash
uv run pytest
```

Run linting:

```bash
uv run ruff check getpaid/ tests/
uv run ruff format --check getpaid/ tests/
```

## How to submit changes

1. Fork the repository and create a feature branch
2. Write tests for your changes
3. Ensure all tests pass: `uv run pytest`
4. Ensure linting passes: `uv run ruff check getpaid/ tests/`
5. Open a pull request

Your pull request needs to:

- Pass the test suite without errors
- Include tests for new functionality
- Update documentation if adding features
- Work for Python 3.12+ and Django 5.2+
