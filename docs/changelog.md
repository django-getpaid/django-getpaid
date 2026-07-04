# Changelog

## v3.2.0 (2026-07-04)

### Important upgrade notes

- **`external_id` schema change (new migration)**: `Payment.external_id`
  is now nullable (`null=True, default=None`) instead of defaulting to an
  empty string. The old `unique=True` + `default=''` combination made the
  *second* payment ever created fail with `IntegrityError` (empty strings
  collide; `NULL`s do not). Empty strings are normalized to `NULL` in
  `save()`/`clean()` and by a data migration. **Run `manage.py migrate`
  after upgrading.** If you use a custom (swapped) Payment model, run
  `makemigrations` for your app as well.
- **Row-level locking on payment state changes**: the paywall callback
  view, `Payment.fetch_and_update_status()` and the admin charge/release/
  refund actions now run inside `transaction.atomic()` and lock the
  payment row with `select_for_update()`, serializing concurrent webhook
  and status updates. If you call these from your own long-running
  transactions, be aware of the new locking semantics.

### Fixes

- Dependency floors raised to `python-getpaid-core>=3.1.0` and
  `python-getpaid-paynow>=3.1.0` (dev); dropped git-branch `uv` sources so
  both resolve from PyPI.
- The example `orders` app was missing migrations for the unique
  `external_id` field and the "single non-failed payment per order"
  constraint; they are now generated and `makemigrations --check` passes
  for all apps.
- Callback error handling: malformed JSON payloads now return HTTP 400
  (previously 500), and duplicate/late provider callbacks that raise
  `InvalidTransitionError` are acknowledged with HTTP 200 and an
  "already processed" body (providers retry on non-2xx). Verification
  failures still return HTTP 403.
- Admin actions (`charge_payment`, `release_lock_action`, `start_refund`)
  no longer silently swallow errors: failures are logged with tracebacks
  and both success and failure counts are reported via admin messages
  (errors use `messages.ERROR`). Hardcoded status strings were replaced
  with `PaymentStatus` enum values.
- `make test-unit` no longer references the nonexistent
  `tests/test_utils.py` (which aborted the whole CI pipeline), and the
  public-API version tests are now dynamic (source `__version__` vs
  installed metadata; dependency floors parsed from `pyproject.toml`).
- E2E tests now skip with a clear reason when the dockerized e2e server
  is not reachable instead of timing out.

### Features

- Default `getpaid/payment_success.html` and `getpaid/payment_failed.html`
  templates (plus a minimal `getpaid/base.html`) are now shipped with the
  package; they are block-based and easy to override per project.
- `CreatePaymentView.validate_order(request, order)`: overridable
  ownership hook called before creating a payment. By default, when the
  order exposes a `user`/`owner` attribute it must match `request.user`
  (403 otherwise); models without such attributes are allowed but a
  security warning is logged once. The order queryset used by
  `PaymentMethodForm` can be scoped via
  `CreatePaymentView.get_order_queryset()` / the form's
  `order_queryset` kwarg.
- New Django system checks: `getpaid.E001`/`getpaid.E002` validate that
  `GETPAID_ORDER_MODEL` is set and resolvable, `getpaid.E003` validates
  that `GETPAID_BACKEND_SETTINGS` is a dict. The Order model is now
  loaded lazily in `getpaid.forms`.

### Packaging / CI

- `.plans/` and `.sisyphus/` are excluded from the sdist.
- The release workflow now runs only after the CI workflow succeeds on
  `main` (`workflow_run` trigger) instead of on every push.
- The example project now includes `django.contrib.staticfiles` and
  `STATIC_URL`, and only configures backends that are actually installed.

## v3.0.1 (2026-06-05)

### Fixes

- **Python 3.14 compatibility**: `PaymentStatus` and `FraudStatus` in
  `getpaid/types.py` no longer subclass core enums directly. Python 3.14's
  `EnumType._check_for_existing_members_` rejects any enum subclassing of an
  existing enum with members, regardless of naming. The wrappers now use
  composition via a metaclass (`_EnumWrapperMeta`) and mixin (`_EnumWrapper`)
  to delegate class-level attribute access and instance behavior to the
  composed core enum while preserving `.choices`/`.CHOICES` for Django model
  fields. All existing imports, comparisons, and bracket access patterns
  remain unchanged.

---

## v3.0.0 (2026-06-04)

Major stable release — multi-broker payment processing framework for Django.

### Breaking Changes

- **Complete rewrite** as thin adapter over `python-getpaid-core` v3
- **Removed django-fsm dependency** — `FSMField` replaced with plain `CharField`,
  runtime FSM via `transitions` library
- **Requires Python 3.12+** (was 3.6+)
- **Requires Django 5.2+** (was 2.2+)
- `can_proceed()` replaced by `may_trigger()`
- django-fsm signals (`pre_transition`, `post_transition`) replaced by
  Django's standard `post_save` signal

### Features

- `python-getpaid-core` as core dependency (framework-agnostic payment processing)
- FSM-removal migrations (convert FSMField to CharField)
- Runtime payment state machine via `create_payment_machine()`
- `DjangoPluginRegistry` wrapping getpaid-core's `PluginRegistry`
- `BaseProcessor` (in `getpaid.processor`) wrapping getpaid-core's `BaseProcessor`

### Unchanged

- All `PaymentStatus` and `FraudStatus` enum values — existing database
  data is fully compatible

See the {doc}`migration-v2-to-v3` for a step-by-step upgrade guide.

---

## v3.0.0a4 (2026-03-25)

- Harden payment creation flow validation and registry wrapping.
- Add Docker-backed integration coverage and CI execution for the web adapter.

---

## v3.0.0a3 (2026-03-20)

- Align the Django adapter with the semantic `getpaid-core` v3 contract.
- Fix callback adaptation for processors that verify `data`, `headers`, and
  `raw_body` separately.
- Persist `provider_data` on payments and refresh alpha-release docs.

---

## v3.0.0a1 (2026-02-13)

First alpha release of the v3 line — complete rewrite as a thin adapter
over [getpaid-core](https://github.com/django-getpaid/python-getpaid-core).

### Breaking Changes

- **Complete rewrite** as thin adapter over getpaid-core
- **Removed django-fsm dependency** — `FSMField` replaced with plain
  `CharField`, runtime FSM via `transitions` library
- **Requires Python 3.12+** (was 3.6+)
- **Requires Django 5.2+** (was 2.2+)
- `can_proceed()` replaced by `may_trigger()`
- django-fsm signals (`pre_transition`, `post_transition`) replaced by
  Django's standard `post_save` signal

### Added

- getpaid-core as core dependency (framework-agnostic payment processing)
- FSM-removal migrations (convert FSMField to CharField)
- Runtime payment state machine via `create_payment_machine()`
- `DjangoPluginRegistry` wrapping getpaid-core's `PluginRegistry`
- `BaseProcessor` (in `getpaid.processor`) wrapping getpaid-core's `BaseProcessor`

### Unchanged

- All `PaymentStatus` and `FraudStatus` enum values — existing database
  data is fully compatible

See the {doc}`migration-v2-to-v3` for a step-by-step upgrade guide.

---

## v2.99.0 (unreleased)

- Switch the test and CI matrix to Django 5.2-6.0 on Python 3.10-3.14 and
  update `tox.ini` to run under tox 4.

## v2.3.1 (development)

- Drop support for Python <3.7
- Add Python 3.10 to test matrix
- Add Django 4.0 to test matrix

## v2.3.0 (2021-06-18)

- Refactor abstract models to another file to fix confused migrations.
- Update docs to cover potential issue with migrations.

## v2.2.2 (2021-06-03)

- Fix classproperty bug for Django >= 3.1
- Add Python 3.9 and Django 3.2 to test matrix

## v2.2.1 (2020-05-26)

- Fix choices for internal statuses

## v2.2.0 (2020-05-03)

- Add template tag
- Add helper for REST integration

## v2.1.0 (2020-04-30)

- Definitions for all internal data types and statuses
- Full type hinting
- Fixed bugs (thanks to [Kacper Pikulski](https://github.com/pikulak)!)

## v2.0.0 (2020-04-18)

- **BREAKING:** Complete redesign of internal APIs.
- Supports only Django 2.2+ and Python 3.6+
- Payment and Order became swappable models - like Django's User model
- Payment acts as customizable interface to PaymentProcessor instances
- Payment statuses guarded with django-fsm
- Broker plugins separated from main repo - easier updates

---

## v1.x (Legacy)

### v1.8.0 (2018-07-24)

- Updated project structure thanks to cookiecutter-djangopackage
- New plugin: pay_rest - New PayU API
- Updated following plugins:
  - payu - legacy API still works on new URL
- Dropped support for following plugins:
  - epaydk (API no longer functional)
  - moip (will be moved to separate package)
  - transferuj.pl (API no longer functional)
  - przelewy24.pl (API needs update, but no sandbox available anymore)
- Dropped support for Django <= 1.10
- Provide support for Django 2.0

### v1.7.5

- Fixed przelewy24 params (py3 support)

### v1.7.4

- Added default apps config `getpaid.apps.Config`
- Fixed and refactoring for `utils.get_domain`, `build_absolute_uri`,
  `settings.GETPAID_SITE_DOMAIN`
- Refactored `register_to_payment`
- Refactored `build_absolute_uri`
- Refactored and fixes in transferuj backend
  - `payment.paid_on` uses local TIMEZONE now as opposed to UTC
  - changed params
  - add post method to SuccessView and FailureView
- Added test models factories
- Dropped support for Django <=1.6

### v1.7.3

- Refactored Dotpay
- Moved all existing tests to test_project and added more/refactored
- Fixed `utils.import_module`
- Fixed Payu and tests (py3 support)
- Updated docs

### v1.7.2

- Updated coveragerc and travis.yml
- Added missing migration for Payment.status

### v1.7.1

- Added coveragerc
- Updated README
- Added `settings.GETPAID_ORDER_MODEL`
- Added epay.dk support
- Added initial django migration

### v1.7.0

- Refactoring to support for py3 (3.4)
- Change imports to be relative - fixes #43
- Add USD to supported currencies in Paymill backend (thanks lauris)
- Fix a few typos

### v1.6.0

- Adding paymill backend
- PEP 8 improvements
- Adding support for django 1.5 in test project (+ tests)
- Fixed issue on `utils.import_name` to allow packages without parents
- Adding dependency to pytz for przelewy24 backend
- Refactoring of PayU backend (xml->txt api, better logging) and adding
  support for non-auto payment accepting

### v1.5.1

- Fixing packaging that causes errors with package installation

### v1.5.0

- Adding new backend - Przelewy24.pl (thanks to IssueStand.com funding)
- Fixing packaging package data (now using only MANIFEST.in)

### v1.4.0

- Cleaned version 1.3 from minor issues before implementing new backends
- Brazilian backend moip
- Updated PL translation
- Added brazilian portuguese translation
- Storing payment external id and description in the database (warning:
  database migration needed!)
- Transferuj backend can now predefine interface language when redirecting
- POST method supported on redirect to payment

### v1.3.0

- Logotypes support in new payment form
- Fixing packaging

### v1.2

- Dotpay backend added
- Hooks for backends to accept email and user name
- Refactoring

### v1.1

- PayU backend added
- Lots of documentation
- Refactoring

### v1.0

- First stable version
