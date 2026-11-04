# Phase 4 baseline revalidation — 1 November 2026

The agreed weekly manual scheduling baseline remains complete. The original local sign-off is `PHASE4_ACCEPTANCE.md` (25 October). This revalidation includes the later room-type, day-off, 12-hour regular-load/overtime, source-import and separate exam-draft changes. It does not expand the baseline into every proposed SRS feature or certify production readiness.

## Additional checks

- `test_differential_baseline.py`: eight deterministic small generated instances; solutions pass independent validation and remain feasible when every assignment decision is fixed by equality. Seeded conflicting assignments fail independent validation and the exact-fixed model is INFEASIBLE. The test hook is not accepted by any HTTP endpoint and never uses hints. Partial/duplicate occurrence lists are refused.
- An AST dependency-graph regression test follows local validator imports and refuses any route into solver, model-building, preflight or worker modules, or OR-Tools. It is included in the normal pytest CI command.
- `backend/tools/phase4_probe.py` exports an offline synthetic scale record with instance size, required/scheduled sessions, status/reason, validation result, runtime, seed, workers, limits, solver/Python versions and snapshot/configuration hashes. It does not seed or alter the website.

## Recorded scale

`output/phase4-scale-2026-11-01-detailed.csv` records 10, 40, 80 and 160 independent synthetic activities over six days. The 10/40-activity instances completed OPTIMAL and passed independent validation. The 80/160-activity instances were blocked by the existing candidate/model-size guard (`instance_too_large`); they are not reported as INFEASIBLE and no runtime or university-scale feasibility target is claimed. This probe is distinct from the earlier 97-session demonstration and has a different candidate-space shape.

## Regression results

The full local check command is `bash scripts/check.sh`. Final results are retained in `output/phase-transition-2026-11-01.json`. Tests use disposable migrated PostgreSQL schemas. The current live academic inputs are not replaced with synthetic fixtures.

## Phase transition

Phase 5 is now the active phase. `evaluation/harness.py` provides offline uncertainty/version/configuration-guard foundations and `evaluation/PHASE5_STATUS.md` records research prerequisites. Independent multilingual annotation, a second institutional context and fresh confirmatory data are still required. Neither this document nor passing software tests declares Phase 5 complete or supplies model-performance evidence. Paid model calls and deployment are not part of this transition.
