# Test Inventory

## Purpose

This inventory implements Step 2 of the governing development brief
(`reports/CHAMACORE_SCALE_ENGINEERING_REPORT.md` §12): every deferred test
must have an explicit reason and a known path to activation. Deferred tests
are not counted as evidence that a feature is fully protected.

## Categories

| Category | Meaning |
| --- | --- |
| Collected | Tests defined in the repository (including deferred) |
| Active | Tests executed by the normal suite (passing) |
| Deferred | Tests intentionally skipped with a recorded reason and activation path |
| Failed | Test failures that must be fixed before any other work in the area |

## Totals (2026-09-23)

| Category | Count |
| --- | --- |
| Collected | 307 |
| Active (passing) | 280 |
| Deferred (skipped) | 27 |
| Failed | 0 |

Active tests run on SQLite locally; native PostgreSQL concurrency and trigger
paths are covered in CI (see also `docs/04_DATABASE.md` and the V3/V2 design
docs).

## Deferred test inventory

All 27 deferred tests are Jenga adapter contract tests in
`tests/test_provider_adapters.py`, skipped with the marker reason
`"Jenga deferred; Daraja-only focus"`.

| Skip site | Marked item | Tests | Reason deferred | Required environment | Local-only? | CI should run? | Activation condition |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `test_provider_adapters.py:181` | `TestRegistry.test_jenga_adapters_one_per_environment` | 1 | Jenga adapter is not registered as an active provider (Daraja-only focus since 2026-09-17); no live Jenga account exists | none (MockTransport) | no | only after activation | Product re-registers Jenga as an active provider (or an approved decision reactivates its contract tests) |
| `test_provider_adapters.py:216` | `TestJengaAuthentication` | 5 | Same as above (authentication request/rejection contracts) | none (MockTransport) | no | only after activation | Same |
| `test_provider_adapters.py:504` | `TestJengaPaymentAttempt` | 5 | Same as above (STK Push request, phone normalization, rejection mapping) | none (MockTransport) | no | only after activation | Same |
| `test_provider_adapters.py:602` | `TestJengaSignature` | 3 | Same as above (signature header contracts) | none (MockTransport) | no | only after activation | Same |
| `test_provider_adapters.py:755` | `TestJengaStatusQuery` (incl. parametrized `test_normalize_provider_status`, 6 cases) | 9 | Same as above (status-query contracts and status normalization) | none (MockTransport) | no | only after activation | Same |
| `test_provider_adapters.py:899` | `TestJengaCallbacks` | 4 | Same as above (callback parse/verify contracts) | none (MockTransport) | no | only after activation | Same |

Because the tests use `httpx.MockTransport`, they do **not** require Jenga
credentials or a network; they are deferred solely because the Jenga adapter
is out of the active provider scope, not because they cannot run.

### Activation path

When the product records a decision to re-activate Jenga (or to delete the
Jenga adapter entirely), this inventory must be updated in the same change:

1. Re-register the adapter (registry + `JENGA` provider code) per ADR-016, or
   record the removal decision.
2. Remove the matching `@pytest.mark.skip` markers in
   `tests/test_provider_adapters.py` (the whole set of affected classes) and
   confirm the tests pass.
3. Move the rows above into a "previously deferred" section (do not delete the
   history) or mark the activation decision in the commit message.

## Maintenance rules

- Never delete deferred tests.
- Never add a `skip` marker without recording the test here with a reason,
  required environment, and activation condition in the same change.
- Keep this inventory consistent with the test suite; run the collection check
  when touching tests:
  `python -m pytest tests --collect-only -q` (307 collected as of 2026-09-23).
- Deferred counts do not count toward feature protection (scale report §12).