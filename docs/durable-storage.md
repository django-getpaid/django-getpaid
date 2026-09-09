# Durable Django storage (next-major development)

**Status: unreleased development prerequisite, not a released 3.x API.**

`getpaid.durable_repository.DjangoDurablePaymentRepository` implements the
next-major `getpaid_core.durable.DurablePaymentRepository` contract. This work
was developed against core revision
`40474307e0781aea8baeeea3d45217a89579f42c`. Published core **3.2.0 does not contain
that contract**. Installing the released dependencies does not enable this
adapter. There is no version bump, release, automatic flow selection, or unsafe
fallback in this change.

Core owns all financial validation, semantic hashes, reservations, submission
claims, outcomes, observations and audited resolution. See core's
`docs/durable-storage.md` and `docs/adr/0001-durable-money-operations.md` at that
revision. This adapter only supplies Django storage. It calls no provider and
retries neither provider commands nor database failures.

The existing `getpaid.repository.DjangoPaymentRepository`, instance methods,
views and legacy flow remain unchanged. Importing the normal Django models does
not import unreleased core modules. Only explicit durable imports require them.

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
update, reset, durable-history import, or repair API. They create no operation
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

All three models have read-only public managers/querysets and instances. Normal
`save`, `save_base`, `delete`, creation, updates, bulk writes, conflict-upserts,
`get_or_create` and `update_or_create` are refused with
`DurableStorageReadOnlyError`; their async counterparts are refused too. Root
payment/order deletion through normal Django collection is protected by foreign
keys. The repository alone uses a private writer to persist planner results.
These are **ordinary ORM guards**, not a security boundary against database
administrators, raw SQL, private ORM bypasses, or schema migrations. Restrict
such access operationally. There is no public evidence deletion/archive API.

### Encoding and retention

Codec version 1 is tagged JSON, with an explicit allowlist of record types and
fields. It preserves finite Decimal text (including scale), enums, tuples versus
lists, nested JSON mappings, and aware datetimes including microseconds, offset,
`fold`, and a `ZoneInfo` key or fixed timezone name. Custom arbitrary `tzinfo`
implementations are refused rather than serialized unsafely. A timezone-rule
change that disagrees with a stored offset fails closed for investigation.
Unknown versions, missing fields and changed derived idempotency keys fail
closed. There is no pickle, eval, raw-result serialization, repr fallback,
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
3. Call `migrate_payment_sync(str(payment.pk))` for each selected stored root.
   Read `MigrationPlan.findings`. Amounts, status and metadata are preserved;
   legacy `applied_event_ids` remains readable **untrusted metadata**. No
   historical operation IDs are invented. Nonfinite source amounts refuse
   migration; repair source data under controlled review first.
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
"${DEV[@]}" pytest tests/test_durable_repository.py \
  tests/test_durable_storage_guards.py tests/test_durable_codec.py -q \
  2>&1 | tee /tmp/getpaid-durable-sqlite.log
"${DEV[@]}" pytest --ds=tests.settings_durable \
  tests/test_durable_custom_model.py -q 2>&1 | tee /tmp/getpaid-durable-custom.log
```

The first file invokes core's complete `run_conformance_suite` against actual
adapter-backed tables. Its factory resets the isolated test database between
checks and uses a valid UUID for core's fixture identity. This is not an
in-memory repository or a substitute for process races.

For PostgreSQL, start **only** `testdb` from `compose.test.yml` with a unique
compose project name. Do not build the existing browser-oriented test image.
Point `TEST_DATABASE_URL` at that isolated database (not a development or
production database), and run:

```bash
"${DEV[@]}" --with 'psycopg[binary]' --with pytest-timeout pytest \
  tests/test_durable_postgres.py tests/test_durable_repository.py \
  tests/test_durable_storage_guards.py --timeout=300 -q \
  2>&1 | tee /tmp/getpaid-durable-postgres.log
```

Give the command an outer timeout of at least 1800 seconds. Process tests use
spawned workers and independent connections, plus a PostgreSQL blocking-lock
probe. They cover empty-history reservations, duplicate submission claims,
stale/full captures, duplicate/conflicting event identities and concurrent
retained disputes. Run the custom-model test under PostgreSQL too to exercise
swappable migrations, joined managers and an independent `storage` alias.
PostgreSQL 17 Alpine was used for development verification with a local image
override; the repository's default compose image is PostgreSQL 16, not separately
certified by that run. SQLite runs skip the PostgreSQL tests explicitly.

Check migration drift for both `tests.settings` and
`tests.settings_default_payment`; the custom-model test checks its own graph.
Run Ruff on changed Python paths and `ty check` on the touched library paths;
when ty does not follow uv's temporary overlay, add
`--extra-search-path "$CORE_CHECKOUT/src"` for this invocation only.
No Playwright, provider integration, browser flow or application allocation
behavior is covered or required by this storage-only prerequisite.

### Known next-major integration gap

Under the local core override, the unchanged legacy choice-table tests
`TestEnumIsNotWrapper.test_choices_values_match_core_enum` and
`TestEnumReExports.test_payment_status_has_choices` in `tests/test_reexports.py`
fail: core has eleven statuses, including `PARTIALLY_REFUNDED`, while Django's
released `PAYMENT_STATUS_CHOICES` has ten. The durable JSON codec handles the new
status, but this storage slice deliberately does not change released legacy
choices or migrations. Those tests pass against released core 3.2.0. Consequently
this prerequisite is not a claim that the entire Django wrapper has completed
its next-major integration or that its whole suite passes against development
core. Resolve the legacy presentation/parser integration separately before a
next-major release.
