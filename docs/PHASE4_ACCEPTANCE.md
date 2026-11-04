# Phase 4 — manual scheduling baseline acceptance

Accepted locally: 25 October 2026. The agreed weekly manual scheduling baseline is complete. This does not certify production readiness or complete every proposed SRS extension.

## Supported boundary

The baseline supports activity occurrence coverage/duration, eligible instructor selection and activity-wide instructor continuity; exact calendar/period fit; shared-room/instructor/group collision prevention; room capacity/type/equipment; approved instructor/room/group closures; weekly unions of activity/group permitted windows with intersection between different targets; approved instructor/time/room locks; configured weekly instructor teaching maxima; global hard student/instructor daily caps; separate-day activity distribution; consecutive/idle-period caps. Groups are disjoint cohorts identified by exact IDs. Time intervals exclude their end point; adjoining classes do not overlap. Date-specific exceptions, cross-group enrolment overlap and parent-course targeting are not claimed.

Soft scoring has two explicit profiles: preferences first then internal idle teaching periods, or a weighted sum of those two independently calculated components. Idle-period minimisation requires Compact days. Fixed breaks are excluded. Other proposed soft types are unfinished extensions, not silently ignored supported inputs.

## Acceptance evidence

- **194 backend tests pass** against the real Alembic chain in disposable PostgreSQL schemas; **30 frontend tests pass**; TypeScript/Vite production build passes.
- Valid generation, seeded collisions/invalid assignments, room/equipment failures, weekly/daily policies, locks and permitted-window failures are independently checked. Detailed violations retain occurrences, resources, times and rule IDs; early structural failure is labelled not evaluated.
- `test_phase4_completion.py` tests window union/intersection, preliminary blockers versus optional warnings, collision details, custom weighted settings, permission/target validation, payload-conflicting retries, historical-input staleness, score-only progress, global infeasibility after passing local checks and MODEL_INVALID.
- Existing scheduling tests cover queued/running cancellation, cancellation winning the terminal-write race, interrupted recovery, immutable snapshots, validator failure and unknown/search-limit distinction. Cancelled candidates are discarded. Automatic retry limit is explicitly zero; users may retry after reviewing an outcome.
- New runs retain schema-versioned approved snapshots, canonical input/configuration fingerprints, objective settings, raw solver outcome, explicit parameters, OR-Tools/Python/platform versions, model/application hashes, lifecycle timestamps and validator version. Hashes are identifiers, not authenticity signatures. Parallel search may yield different schedules with identical inputs/seed.
- Input checks run before solving and are also available on demand. They identify proven local contradictions and missing data without claiming to establish global feasibility. Missing optional limits remain warnings.
- The one-page chart PDF was rendered and visually checked after correcting the selected-objective label. Reports remain optional downloads.

## Final live run

Run `0aeb884a-de45-4964-a48e-6e2d4db4cb13` uses current input version 12 and snapshot schema 2. It retained 97 sessions, passed independent validation with no reported errors, verified both saved fingerprints and independently matched the selected objective score. The report lists 19 checks; checks with zero applicable targets are explicitly not applicable, not evidence that such targets were exercised live. The demo currently has no configured weekly instructor maxima; its optional-limit warnings are retained. The daily policy is configured.

Machine-readable evidence is in `output/phase4-acceptance.json`. Browser previews are `docs/preview-phase4-input-checks.png` and `docs/preview-phase4-validation.png`. An academic-input/run backup was saved under the ignored `backups/` directory before migration 0015.

## Publication and remaining project scope

There is no publication action or published timetable in this baseline. Therefore a failed, incomplete, cancelled or stale draft cannot become published through it. This is absence of publication functionality, not a claim that future publication gates have been implemented or verified. Student viewing remains explicitly labelled draft access.

Phase 5 can now begin: versioned evaluation/annotation guidance and reproducible synthetic multilingual materials for the verified vocabulary. Advanced constraint variants and rule replacement history remain visible in the Phase 3/full-feature checklist; AI extraction is Phase 6; scenario editing/comparison/publication is Phase 7; deployment and institutional acceptance are later work. These are not marked complete by this sign-off.
