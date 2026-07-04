.PHONY: test test-unit test-integration test-e2e test-build test-down \
	test-local-workspace-paynow pip-audit

UNIT_TESTS = \
	tests/test_reexports.py \
	tests/test_callback_adapter.py \
	tests/test_deprecated_cleanup.py \
	tests/test_migration_checks.py \
	tests/test_database_settings.py

INTEGRATION_TESTS = \
	tests/test_abstracts.py \
	tests/test_registry.py \
	tests/test_forms.py \
	tests/test_views.py \
	tests/test_dummy_backend.py \
	tests/test_processor.py \
	tests/test_fsm.py \
	tests/test_integration.py

test-unit:
	DJANGO_SETTINGS_MODULE=tests.settings uv run pytest $(UNIT_TESTS) -x

test-integration: test-build
	docker compose -f compose.test.yml run --rm tests uv run pytest $(INTEGRATION_TESTS) -x

test-e2e: test-build
	docker compose -f compose.test.yml up -d testdb e2e-server
	@sleep 5
	DJANGO_ALLOW_ASYNC_UNSAFE=1 docker compose -f compose.test.yml run --rm tests uv run pytest tests/e2e/ -x
	docker compose -f compose.test.yml down

.PHONY: test-e2e-down
test-e2e-down:
	docker compose -f compose.test.yml down

test:
	$(MAKE) test-unit
	$(MAKE) test-integration
	$(MAKE) test-e2e

test-local-workspace-paynow:
	uv run \
		--with-editable ../python-getpaid-core \
		--with-editable ../python-getpaid-paynow \
		python -c "from pathlib import Path; import getpaid_core, getpaid_paynow; workspace = Path.cwd().resolve().parent; core_root = (workspace / 'python-getpaid-core').resolve(); paynow_root = (workspace / 'python-getpaid-paynow').resolve(); assert str(Path(getpaid_core.__file__).resolve()).startswith(str(core_root)); assert str(Path(getpaid_paynow.__file__).resolve()).startswith(str(paynow_root))"
	uv run \
		--with-editable ../python-getpaid-core \
		--with-editable ../python-getpaid-paynow \
		pytest tests/test_paynow_integration.py -q

test-build:
	docker compose -f compose.test.yml build

test-down:
	docker compose -f compose.test.yml down -v

pip-audit:
	uv run pip-audit --strict
