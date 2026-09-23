# Durable Django storage (next-major development)

**Status: unreleased development prerequisite, not a released 3.x API.**

`getpaid.durable_repository.DjangoDurablePaymentRepository` implements the
next-major `getpaid_core.durable.DurablePaymentRepository` contract. This work
was developed against core revision `f5a8aa4`, including the separate
`getpaid_core.recorded_money` API. Published core **3.2.0 does not contain
these contracts**. Installing the released dependencies does not enable this
adapter. There is no version bump, release, automatic flow selection, or unsafe
fallback in this change.

Core owns all financial validation, semantic hashes, reservations, submission
claims, outcomes, observations and audited resolution. See core's
`docs/durable-storage.md` and `docs/adr/0001-durable-money-operations.md` at that
revision. This adapter only supplies Django storage. It calls no provider and
retries neither provider commands nor database failures.

The existing legacy repository and model/flow entrypoints now **refuse durable
roots** through a shared persisted-ownership guard (see below). Their ordinary
non-durable payment semantics are unchanged. Importing normal Django models,
legacy repositories and flows does not import unreleased core modules. Only
explicit durable imports require them.

## Public API

```python
from getpaid.durable_repository import DjangoDurablePaymentRepository

repository = DjangoDurablePaymentRepository(using="default")
```

`model_class=None` resolves `GETPAID_PAYMENT_MODEL` through swapper. An explicitly
supplied model must be that same configured class: the migration's foreign key
cannot point at a different model selected per repository instance. `using`
defaults to `"default"`; every query, lock and transaction uses that alias.
Payment identities are canonical strings of existing payment primary keys,
including UUID, integer or string keys. No operation creates a root payment.

The following are async methods. Every one also has a public synchronous twin
named `<method>_sync`, with identical arguments and return value.

| Method | Return |
|---|---|
| `get_payment_facts(payment_id)` | `PaymentFacts`; missing/uninitialized raises `KeyError` |
| `record_money(payment_id, command, *, now)` | Core `RecordedMoneyPlan`; atomically initialize/append/update, or exact replay without writes |
| `get_recorded_money_history(payment_id)` | Complete commit-ordered `tuple[RecordedMoneyEntry, ...]` under the root lock; missing/uninitialized raises `KeyError`, wrong source raises `InvalidTransitionError` |
| `reserve_operation(payment_id, intent)` | `OperationRecord`, including identical-intent retries |
| `claim_submission(payment_id, operation_id, *, expected_attempt, now, retry_until=None, idempotency_scope=None)` | `SubmissionPlan` |
| `apply_observation(payment_id, update)` | `ObservationPlan`, including retained conflicts when `applied=False` |
| `record_operation_outcome(payment_id, operation_id, outcome, *, response_attempt=None)` | `OutcomePlan` |
| `record_operation_failure(payment_id, operation_id, evidence)` | `OperationRecord` with retained recovery evidence |
| `resolve_operation(payment_id, operation_id, resolution, *, expected_operation, expected_facts)` | `OutcomePlan` with audit and all related operations |
| `get_operation(payment_id, operation_id)` | `OperationRecord` or `None` |
| `list_unresolved_operations()` | Tuple of active, flagged, or response-pending records, including terminal records |
| `list_payments_requiring_reconciliation()` | Tuple of flagged facts, including payments with no operation |
| `migrate_payment(payment_id)` | Core `MigrationPlan`, seeded once from locked stored legacy fields |
| `seed(facts)` | Core `MigrationPlan`, seeded once from explicit `PaymentFacts` for a controlled import/test fixture |

`seed` runs core's migration validation too. It preserves supplied facts and may
add a reconciliation flag; it never clears an existing requirement. Both
initializers refuse an already-initialized root with `ValueError`. Neither is an
update, reset, durable-history import, or repair API. Both reject a persisted
recorded-money backend; `seed` also rejects supplied recorded-money facts even
when the persisted backend differs. Use `record_money_sync` instead. They create no operation
identities or trusted replay evidence. Do not use `seed` to bypass review of
ambiguous legacy data or to import an existing durable aggregate without its
operation/replay history.

Core validation/conflict exceptions propagate. A stale reviewed resolution
raises `StateConflictError`; review again, do not blindly retry that decision.
An identical decision ID/content is an acknowledgement retry even if newer
facts now exist. The application authorizes operators and establishes that
submission producers are quiescent before retiring pending responses. Query and
callback outcomes leave `response_attempt=None`; only a submitting producer
acknowledges its own claimed attempt.

Storage/encoding errors propagate and roll back the complete local mutation.
They never imply provider rejection or authorize resubmission. Backend limits
on indexed identity size still apply; an oversized identity can fail a write,
not be silently shortened. Invalid primary-key representations may raise the
configured Django field's validation exception before lookup.

## Recorded money: source ownership and initialization

Core's `docs/recorded-money.md` at `f5a8aa4` owns the command fields, evidence,
correction rules, replay semantics and projection. This adapter does not duplicate
that arithmetic, invoke a provider, reserve an operation, or fabricate confirmation
events. Callers supply an authenticated/authorized `RecordedMoneyCommand` and an
aware integration clock `now`; use core's public `project_recorded_money(history)`
for effective receipt/repayment views. Currency precision, application allocation,
credit rules and authorization remain application responsibilities.

`record_money_sync(payment_id, command, *, now)` addresses an **existing payment
row**. Under the same root lock and transaction used by provider storage, it reloads
current facts, **all** recorded entries ordered by insertion primary key, **all**
provider operations, and **all** provider replay records. The core planner receives
those histories, never caller-provided facts, a filtered history or a precomputed
plan. A history whose receipt/correction entries net to zero is still retained.
Provider history on a recorded root causes core refusal, including on replay.

The first command may initialize durable state only from the locked, persisted
legacy/root fields through `LegacyPaymentState` and core's migration conversion.
The root must already have `backend=RECORDED_MONEY_BACKEND`, zero paid/refunded/
authorized totals, no external handle, provider metadata, fraud or reconciliation
evidence, and NEW/PREPARED status. Core validates the resulting facts against empty
history before any write. Nonzero fields are never reset to manufacture a clean
source. This initializes new roots; it does not import historic cash or convert a
provider durable root. After initialization, retries read durable facts/history,
not retired root amounts/backend/status.

On `plan.applied=True`, the repository inserts the complete versioned entry and
writes new facts in one transaction. On replay, it inserts/updates nothing and
returns core's plan with the original entry and **current** facts. A first-command
refusal leaves no durable initialization. A failed evidence/facts write or enclosing
application transaction rolls back both, including initialization. As with other
methods, a result remains provisional until the outermost transaction commits.

Every provider mutation (reservation, submission claim, outcome, failure,
observation, resolution) rejects recorded-money facts at its common private
boundary **before provider planners run**, including no-op observations and
zero-summary roots. Payment identity, backend and required amount cannot change
through repository updates. There is no public fact-replacement/repair method.

## Transaction boundary and supported database

**PostgreSQL READ COMMITTED is the supported multi-worker storage configuration.**
Each mutation starts/joins `transaction.atomic(using=...)`, checks isolation,
locks the existing payment with `select_for_update(of=("self",))`, then loads
the durable facts and complete retained operation history. Locking the root
before dependent reads/inserts serializes even two reservations against an
initially empty operation table. Joins introduced by a custom manager do not
lock the joined order. The planners' entire results commit together: facts,
operations, related cancellation targets, audit and replay evidence.

REPEATABLE READ and SERIALIZABLE are refused with `NotSupportedError`: merely
locking an unchanged root does not refresh a transaction's older snapshot of
its dependent records. Other database vendors are refused. SQLite is accepted
for development/semantic tests only; its `select_for_update` is a no-op and
**must not be used to claim concurrent money-movement safety**.

`atomic()` is a synchronous context manager for same-database application writes:

```python
def commit_authenticated_observation(payment_id, normalized_update):
    with repository.atomic():
        plan = repository.apply_observation_sync(payment_id, normalized_update)
        # Application-owned writes here must use repository.using too.
        # Base them on the committed plan, not a stale payment instance.
        return plan
```

The returned plan is provisional until any enclosing transaction commits.
Keep provider I/O **outside** this block. Establish a consistent lock order when
combining application aggregates. Cross-database transactions are not provided.

Async methods are `sync_to_async(..., thread_sensitive=True)` wrappers around
local synchronous storage work only. To compose from an async application,
wrap the entire synchronous application function once with that same bridge.
Do not open a transaction in one thread and await repository methods in another;
Django transactions are connection/thread-local. Do not hold a transaction
around `DurablePaymentFlow`'s provider dispatch.

## Storage schema and ownership

Migration `getpaid.0010` adds three ordinary tables, using swappable dependencies
rather than a dependency on an example application:

| Model/table | Authoritative content and constraints |
|---|---|
| `DurablePaymentState` / `getpaid_durablepaymentstate` | One-to-one `payment` with `PROTECT`; versioned `facts` JSON contains **all** `PaymentFacts` fields. Indexed `reconciliation_required` is an atomically maintained discovery projection. |
| `DurableOperation` / `getpaid_durableoperation` | `payment` references the durable state with `PROTECT`; database uniqueness on `(payment, operation_id)`. Versioned `record` JSON contains **all** `OperationRecord` fields; indexed `unresolved` is a discovery projection. |
| `DurableReplay` / `getpaid_durablereplay` | `payment` references the durable state with `PROTECT`; database uniqueness on `(payment, backend, event_identity)`; core's `content_digest` is stored unchanged. Insert-only repository path, no conflict-upsert. |

Generated migration `getpaid.0012` (after `0011`) adds
`DurableRecordedMoneyEntry` / `getpaid_durablerecordedmoneyentry`: insertion `id`,
`payment` FK to `DurablePaymentState` with `PROTECT`, `command_id` text, and `record`
JSON containing the complete core `RecordedMoneyEntry`. Database constraint
`getpaid_recorded_money_identity` makes `(payment, command_id)` unique. Reads order
by insertion PK, **not** business time, audit time or command ID. Entries are
append-only through the public API; originals and corrections remain together.

**The durable facts are the only authoritative financial representation after
cutover. Legacy payment amounts, status, backend, handles and metadata remain
retired snapshots, not maintained compatibility projections.** The adapter does
not update those fields or legacy timestamp fields. Existing legacy screens,
admin displays, instance helpers and reports therefore are not durable readers;
integrations must switch their financial reads to this repository. Legacy
callback routing and callback/PULL parser inputs are not rewired here either:
callers must supply current durable handles/facts, not retired root fields.
Root payment
and order rows still provide application identity/context. Do not infer current
money from them after cutover, or save a previously loaded instance.

**The legacy single-payment constraint is also a consumer of retired state.**
`AbstractPayment.Meta.constraints` declares
`getpaid_unique_non_failed_payment_per_order`, whose predicate reads the root's
legacy `status`. A payment that fails through the durable path can still retain
NEW/PREPARED there; inserting its replacement then raises `IntegrityError`, even
when all application readers use durable facts. Before enabling replacement
payments, the integration must explicitly replace that constraint and its
single-payment enforcement strategy for its concrete payment model. Preserve
the intended rule under concurrent creation using current durable state and an
appropriate order-level database lock; simply dropping uniqueness is not an
alternative enforcement strategy. An integration deliberately permitting
multiple receipt payments per settlement context must document that different
rule and remove the legacy single-payment validation as well. This adapter
neither changes the constraint automatically nor updates legacy status to keep
it satisfied.

Operation projections may change under core planners; the whole row is **not
append-only**. Their `conflicting_outcomes`, `recovery_evidence` and `resolutions`
are retained evidence, and facts retain `observation_conflicts`. Repository
writers additionally reject removal of previously retained evidence. Pending
response attempts are preserved or retired only by the relevant core plan.
Replay bookkeeping is never merged into `provider_data`.

All four models have read-only public managers/querysets and instances. Normal
`save`, `save_base`, `delete`, creation, updates, bulk writes, conflict-upserts,
`get_or_create` and `update_or_create` are refused with
`DurableStorageReadOnlyError`; their async counterparts are refused too. Root
payment/order deletion through normal Django collection is protected by foreign
keys. The repository alone uses a private writer to persist planner results.
These are **ordinary ORM guards**, not a security boundary against database
administrators, raw SQL, private ORM bypasses, or schema migrations. Restrict
such access operationally. There is no public evidence deletion/archive API.

### Legacy-use guard and cutover limits

`AbstractPayment.save`/`save_base` (and inherited async saves), legacy repository
reads used for dispatch (`get_by_id`/`list_by_order` and sync twins), processor
resolution in the flow adapter, and paywall callback handling now check persisted
durable ownership. Callbacks check **before verification/dispatch**, even when an
explicit `processor=` bypasses resolution. The lookup uses the model's DB alias
(or the explicit save alias), not a cached related object or stale backend field.
It refuses all durable roots with `DurableStorageReadOnlyError`; it imports no
upcoming core API. Brand-new payment creation, historical migration models, the
configured swappable payment and ordinary non-durable payments remain usable.

This is an ordinary entrypoint guard, **not an atomic check-before-network
protocol**. Quiesce and drain old writers **before** cutover; no guard can undo I/O
already dispatched or prevent a caller deliberately bypassing these entrypoints.
Normal root queryset/metadata updates are not authoritative durable writes and are
not prevented. Raw SQL, private ORM, arbitrary custom managers/overrides, database
administrators and schema migrations are outside these guarantees. Legacy views,
callback routing and parser inputs still need explicit durable integration.

### Encoding and retention

Codec version 1 is tagged JSON, with an explicit allowlist of record types and
fields. It preserves finite Decimal text (including scale), enums, tuples versus
lists, nested JSON mappings, and aware datetimes including microseconds, offset,
`fold`, and a `ZoneInfo` key or fixed timezone name. Custom arbitrary `tzinfo`
implementations are refused rather than serialized unsafely. A timezone-rule
change that disagrees with a stored offset fails closed for investigation.
Unknown versions, missing fields, changed core dataclass schemas (including added
optional fields) and changed derived idempotency keys fail closed. The same version
1 allowlist includes `RecordedMoneyCommand`, `RecordedMoneyEntry`,
`RecordedMoneyKind`, and `RecordingCorrectionReason`, preserving every field,
Decimal scale, UTC business instant, recorded/effective timestamps, target/reason,
actor/note, and original/correction evidence references. There is no separate money
codec. There is no pickle, eval, raw-result serialization, repr fallback,
implicit empty-history default, truncation, expiry or archival.

Every normalized conflict field, recovery field and resolution field survives
read-back, including audit identity/actor/reason/references/time/outcome/payment
acknowledgement. Semantic hashes remain core-owned. Metadata cannot forge typed
values because mapping contents are encoded separately from codec tags. Treat
metadata and evidence as access-controlled application data, not log payloads.

Retain compact history for the payment's supported lifetime. Older experimental
storage/digests need an explicit offline upgrade using original normalized
evidence; this initial adapter provides no such upgrader. Never discard history
or demote trusted replay to plugin metadata. Local retention does not extend a
provider's idempotency window.

## Coordinated cutover and recovery

1. Back up root payments and any existing controlled evidence. Apply the additive
   schema migration to the same alias that owns the configured payment model.
   Applying schema alone does not enable durable writes or migrate any data.
2. Stop **all** legacy writers for the selected payments: callbacks, pollers,
   commands, jobs and unconditional-save workers. Drain their in-flight work.
   Old and durable writers cannot safely coexist against the same payment.
3. For provider roots, call `migrate_payment_sync(str(payment.pk))` for each selected stored root.
   Read `MigrationPlan.findings`. Amounts, status and metadata are preserved;
   legacy `applied_event_ids` remains readable **untrusted metadata**. No
   historical operation IDs are invented. Nonfinite source amounts refuse
   migration; repair source data under controlled review first. For new recorded-money
   roots, instead call `record_money_sync` with the first truthful command under the
   initialization rules above; do not use either generic initializer.
4. Ambiguous balances/statuses and unidentifiable pending legacy work stay
   reconciliation-required and new-command-blocked. Observations remain
   available. Payments without a durable operation cannot be repaired through
   `resolve_operation`; an application-owned audited repair/import procedure is
   still required. This adapter does not provide a generic flag-clearing escape.
5. Switch readers to durable facts and replace any legacy-state-dependent
   creation constraints/validation, including the single-payment constraint
   described above. Explicitly construct the next-major core durable flow with
   suitable upgraded processors. Start only those writers.
   Use both discovery methods to find unresolved work; supply scheduling,
   authorization and provider evidence in the integration.

Do not restart legacy writers or unapply this migration after durable writes.
Downgrading by dropping the tables irreversibly loses operation/replay/audit
history. A rollback needs a coordinated backup/restore and review of any remote
provider effects since the backup; a database restore cannot undo them. Keep
writers stopped if evidence or cutover state is uncertain.

## Development verification

Use a local core checkout at the pinned revision through a **temporary** uv
override. Do not add an absolute path dependency, change core's version, or
claim this works with released core. From this repository:

```bash
# Set CORE_CHECKOUT to your independent python-getpaid-core checkout.
DEV=(uv run --no-default-groups --with "$CORE_CHECKOUT"
     --with pytest --with pytest-django --with pytest-asyncio
     --with pytest-factoryboy --with httpx)
set -o pipefail
timeout 600s "${DEV[@]}" pytest tests/test_reexports.py \
  tests/test_durable_repository.py tests/test_durable_storage_guards.py \
  tests/test_durable_codec.py tests/test_recorded_money.py \
  tests/test_durable_legacy_guard.py tests/test_repository_async.py \
  tests/test_legacy_import_boundary.py tests/test_migration_checks.py -q \
  2>&1 | tee /tmp/getpaid-durable-sqlite.log
timeout 600s "${DEV[@]}" pytest --ds=tests.settings_durable \
  tests/test_durable_custom_model.py -q 2>&1 | tee /tmp/getpaid-durable-custom.log
```

`test_durable_repository.py` invokes core's complete `run_conformance_suite` against actual
adapter-backed tables. Its factory resets the isolated test database between
checks and uses a valid UUID for core's fixture identity. This is not an
in-memory repository or a substitute for process races.

For PostgreSQL, start **only** `testdb` from `compose.test.yml` with a unique
compose project name. Do not build the existing browser-oriented test image.
Point `TEST_DATABASE_URL` at that isolated database (not a development or
production database), and run:

```bash
timeout 1800s "${DEV[@]}" --with 'psycopg[binary]' --with pytest-timeout pytest \
  tests/test_durable_postgres.py tests/test_recorded_money.py \
  tests/test_durable_repository.py tests/test_durable_storage_guards.py \
  tests/test_durable_legacy_guard.py --timeout=300 -q \
  2>&1 | tee /tmp/getpaid-durable-postgres.log
```

Give the command an outer timeout of at least 1800 seconds. Process tests use
spawned workers and independent connections, plus a PostgreSQL blocking-lock
probe. They cover empty-history reservations, duplicate submission claims,
stale/full captures, duplicate/conflicting event identities and concurrent
retained disputes. Recorded-money tests additionally cover exact concurrent replay,
competing receipts, corrections and repayments, root-lock serialization of initial
empty history, outer application rollback and injected facts-write failure. Run the
custom-model test under PostgreSQL too to exercise swappable migrations, joined
managers, legacy guards and an independent `storage` alias:

```bash
timeout 1800s "${DEV[@]}" --with 'psycopg[binary]' --with pytest-timeout pytest \
  tests/test_durable_custom_model.py --ds=tests.settings_durable \
  --timeout=300 -q 2>&1 | tee /tmp/getpaid-durable-custom-postgres.log
```

Repeat the selections with `--with 'Django>=5.2,<5.3'` and
`--with 'Django>=6.0,<6.1'` in the uv argument list. Verification used Django
5.2.17 and 6.0.6: each passed 180 selected SQLite tests, two custom-model SQLite
tests, 144 PostgreSQL tests and two custom/alias PostgreSQL tests. PostgreSQL
17.11 Alpine was used with a local image override; the repository's default compose image is PostgreSQL 16, not separately
certified by that run. SQLite runs skip the PostgreSQL tests explicitly.

Check migration drift for `tests.settings`, `tests.settings_default_payment`,
`tests.settings_durable`, and `example.settings`. Keep these probes isolated too:

```bash
# Repeat for each settings module and each Django version above.
PYTHONPATH=.:example DJANGO_SETTINGS_MODULE=tests.settings \
  timeout 600s "${DEV[@]}" python -c '
import django
from django.conf import settings
from django.core.management import call_command
settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
django.setup()
call_command("makemigrations", check=True, dry_run=True)
call_command("migrate", verbosity=0)
call_command("migrate", check_unapplied=True, verbosity=0)
' 2>&1 | tee /tmp/getpaid-durable-migration-drift.log
```

All four graphs migrated without drift under both verified Django versions.
Run Ruff on changed Python paths and `ty check` on the touched library paths;
when ty does not follow uv's temporary overlay, add
`--extra-search-path "$CORE_CHECKOUT/src"` for this invocation only.
No Playwright, provider integration, browser flow or application allocation
behavior is covered or required by this storage-only prerequisite.

### Verification limitations outside this adapter

Normal imports are also tested with a finder that refuses upcoming core modules.
A released-core 3.2.0 selection of model, callback adapter, async repository,
reexport and import-boundary tests passed under both Django lines (69 passed;
seven skips comprise four existing vendor-dependent tests, two durable modules,
and the upcoming-core default-model probe). That is import/legacy regression
evidence, **not durable 3.2 support**.

**Historical baseline, now resolved:** at `00ff3e2`, 14
`test_abstracts.py`/`test_flow_adapter.py` cases failed against development core
because newly created monetary fields could still be integers. Released-core
checks also exposed an incorrect REFUNDED expectation for an uncaptured lock
release and an exact ecosystem-version parity assertion (Django 3.2.1 versus
core 3.2.0). The baseline source-export transcripts remain historical evidence,
not the current failure map.

The compatibility follow-up shares the legacy repository's Decimal normalizer
with direct model/flow entrypoints. It normalizes the same instance, including
explicit integer/string assignments, without reloading and losing caller edits.
An empty semantic update delegates pre-dispatch amount validation to the active
core FSM; the pinned development core rejects malformed/nonfinite/negative
payment fields before provider commands. Callback normalization and validation
run **after authentication**, before callback handling. Durable ownership checks
and database aliases remain unchanged. No core financial rules are copied.

Releasing a zero-captured authorization is tested as CANCELLED, with zero paid,
refunded and remaining authorized amounts; no refund is fabricated. Package tests
now verify installed metadata and declared dependency constraints, not equality
between independently patch-released packages. Version numbers still cannot
certify unreleased durable capabilities. REST result typing reflects the existing
branch-specific payload: `status_code` and `result` are required; `target_url`,
`form` and `message` are present only on their respective response branches.
Runtime payloads are unchanged.

Follow-up verification against core `f5a8aa4`, on Django 5.2.17 and 6.0.6:

- Combined original durable selection plus legacy model/flow, monetary-boundary,
  public-API and callback-adapter tests: **382 passed, four PostgreSQL-only skips**
  per Django line. The original 180-test selection remains included.
- Isolated PostgreSQL 17.11 legacy/durable selection: **334 passed** per line;
  custom-model/independent-alias selection: **three passed** per line on both
  SQLite and PostgreSQL. Only the unique testdb stack was started and removed,
  without deleting volumes.
- Released core 3.2.0 ordinary imports and representative legacy paths:
  **128 passed, five skips** per line (four PostgreSQL-only tests and the existing
  upcoming-core import probe). This does not certify upcoming strict validation
  or any durable API on released core.
- Broader non-browser run: **517 passed, 20 environment-dependent skips**;
  all skipped PostgreSQL/custom-settings cases passed in their separate runs.
  Two unawaited `AsyncMock` coroutine warnings remain visible in this run.
- Ruff passes on all 19 selected changed Python paths. `ty` passes on all nine
  touched library modules, including `abstracts.py`, plus the recorded-money
  migration. The ten historical diagnostics are resolved without added ignores.

No browser suite, live-provider behavior, Stripe durable support, historical
payment import, consumer integration or full release readiness is claimed.

### Next-major presentation compatibility

Django's payment choices now include the upcoming `PARTIALLY_REFUNDED` state,
with a translated label and generated migrations for the default, example and
custom test payment models. Core's enum determines which choices are exposed;
released core still imports normally without being asked for a member it does
not define. The two legacy choice-table tests in `tests/test_reexports.py`
therefore pass against development core too.

This fixes the missing status label, not legacy callback/parser wiring or
financial readers. Those still need explicit durable integration before a
next-major release. Schema-state/migration drift checks for this branch target
the upcoming core enum; ordinary import compatibility does not make published
core 3.2.0 a supported durable runtime.
