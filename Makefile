.PHONY: test test-unit test-integration test-build test-down

UNIT_TESTS = \
	tests/test_reexports.py \
	tests/test_callback_adapter.py \
	tests/test_utils.py \
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

test:
	$(MAKE) test-unit
	$(MAKE) test-integration

test-build:
	docker compose -f compose.test.yml build

test-down:
	docker compose -f compose.test.yml down -v
