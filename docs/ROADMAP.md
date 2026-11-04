# JadwAI implementation roadmap

Master feature status: [complete implementation checklist](FEATURE_CHECKLIST.md), reviewed 17 October 2026.

Started 15 October 2026. This plan follows the approved workflow and carries exception handling into the phase that introduces each feature. Dates and estimates await the owner's deadline and availability. Requirement IDs refer to the 64-FR historical SRS baseline, amended by the later owner decisions in `DECISIONS.md`.

## Phase 1 — Reconcile the scope and establish the design

Status: initial reconciliation complete; full requirement traceability still to be reconciled.

Deliverables: independent project folder, approved-decision summary, current roadmap, visual direction, explicit unresolved decisions. Read the previous review as input without copying Claude's implementation. Record bilingual scope and solver-assigned instructors as amendments to the older SRS. Maintain a requirement-to-task checklist as coverage expands.

Exit: no English-only, MySQL, or pre-assigned-instructor assumptions govern implementation. Every undefined domain behavior remains visible. Demo: explain the manual-entry → approval → generation → validation workflow.

## Phase 2 — Deliver a runnable, polished workspace

Status: local implementation complete and verified. GitHub execution is pending a repository destination; deployment containers are configured but have not been built or published.

Scope: FR-047, FR-048; foundations of FR-059, FR-060, FR-064. Dependency: Phase 1 platform choices.

Implemented: frontend shell, sign-in/logout, hashed credentials, expiring server sessions, administrator/viewer policy, PostgreSQL, Alembic, transactional audit, shared-read and exclusive-write workspace locks, If-Match version checks, heartbeat-only worker, English/Arabic UI, responsive layouts, isolated test schemas.

Completed in the foundation milestone:

- Administrator account creation, activation/deactivation, role changes, and explicit session revocation; every protected request checks current account state. A shared database lock protects the last-active-administrator invariant under simultaneous changes.
- Password changes and administrator-issued, hashed, single-use password setup/recovery links with 30-minute expiry. Role changes, deactivation, recovery, and password changes revoke affected sessions. No email service is assumed.
- Persisted per-account and per-client login limits; worker cleanup of expired sessions, reset links, and rate buckets.
- Separate restricted API/worker PostgreSQL roles; migration-owner credentials are omitted from runtime child environments. Audit update/delete/truncate are blocked by PostgreSQL triggers and runtime grants.
- Readiness and liveness endpoints, heartbeat freshness, reconnecting worker, and sanitized database outage responses. A controlled database stop/start returned 503 then recovered automatically with all saved data intact.
- Stable translated audit action codes, current-session refresh, read-only viewer controls, and an in-memory reauthentication overlay that preserves an open draft.
- Prepared CI and a local production-container configuration. The same migration, test, and build steps pass locally; no GitHub remote has been selected, so a remote Actions run is not claimed.

Exit evidence: PostgreSQL regressions cover race conditions, account/reset lifecycle, authorization, throttling persistence, append-only audit, and runtime role restrictions. A UI test confirms draft preservation through reauthentication. Browser checks verify the account and semester interfaces. See `VERIFICATION.md` for exact checks and limitations.

## Phase 3 — Academic data and precise manual constraints

Status: academic data foundation substantially implemented; complete constraint semantics and rule revision history remain. Dependency: working Phase 2 data access.

Scope: FR-001–FR-013, FR-021, with FR-006 updated for solver-assigned instructors and the owner-approved daily-limit additions.

Implemented: normalized typed instructor/room/group/activity tables; real eligibility, group, and rule foreign keys; database-enforced typed-record completeness and activity references; equipment and required-equipment fields; versioned CRUD; explicit draft/approve/revoke for two manual rule types. Semester name, dates, timezone, teaching days/hours, and period length are editable. CSV imports preview row errors, revalidate on commit, enforce the preview version, and commit all rows atomically. Duplicate codes, missing references, invalid values, and linked-record deletion are rejected.

Remaining tasks:

- Completed: normalize academic tables and eligibility/group links; preserve starter records and audit/version information through the migration. Additional availability types remain with the constraint vocabulary.
- Completed: term/calendar editor and institutional periods. Remaining: explicit parent-course/component hierarchy and the complete precise constraint vocabulary.
- Document and test independent semantics for every supported rule, including preferred-period scoring, locks, and daily limits. Weekly maximum teaching-hour limits are implemented (25 October); daily-limit policy and remaining preference semantics still need completion.
- Completed: transactional CSV import preview, per-row errors, referential lookup by existing codes, stale-preview rejection, and all-or-nothing commit (FR-007).
- Add a versioned rule replacement history and approval trace; run contradiction and data-sufficiency checks. Editing a referenced entity must visibly flag affected rules for review where semantics change.

Exit: a complete synthetic semester can be entered and imported; all references are database-enforced; supported constraints have unambiguous definitions. Demo: create an activity with instructor eligibility, add a rule, review it, approve it, and verify stale edits fail.

## Phase 4 — Correct manual scheduling baseline

Status: complete for the agreed manual scheduling baseline, locally accepted on 25 October 2026; final local acceptance evidence is recorded in `PHASE4_ACCEPTANCE.md`. Scope is the explicitly supported weekly manual vocabulary: instructor/room/group closures, activity/group permitted windows, assignment locks, configured weekly instructor maxima, hard global daily caps, distribution/consecutive/gap policy and instructor-window plus idle-period objectives. This milestone does not mean every proposed SRS constraint variant or later-phase publication/AI feature is implemented. Dependencies on institutional semantics are documented under Phase 3 extensions. Scope: FR-024–FR-032 baseline, foundations for FR-033–FR-035 and FR-059–FR-063.

- Implement the independent validator first, with seeded violations per supported rule. It must not import solver model-building code.
- Create immutable approved input snapshots with hashes and schema versions.
- Implement CP-SAT choices for instructor/time/room, weekly instructor continuity, eligibility, group/instructor/room conflicts, capacity/equipment, approved mandatory rules, and documented preference penalties.
- Add PostgreSQL job claiming, leases, crash recovery, bounded retries, cancellation, and idempotency keys with payload conflict checks.
- Preserve OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, FAILED, and CANCELLED distinctions. Retention on cancellation requires an explicit user choice and a complete validated result.
- Report missing data, mandatory violations, preference penalties, and evaluation coverage separately.

Exit: manual data → approved snapshot → background run → independent report works end to end. Invalid, incomplete, errored, or stale results cannot be published. Demo: valid schedule, seeded collision, infeasible case, and cancellation. Diagnostic partial result sources remain an explicit decision.

## Phase 5 — Reproducible evaluation materials

Status: in progress (updated 1 November 2026). Technical harness extensions now provide family-clustered intervals, immutable material versions, frozen configuration checks and logged reserved-access denials; see `../evaluation/PHASE5_STATUS.md`. A separate development-v2 bundle now provides 144 items/36 families/two contexts, a draft updated guide and gold-free review/import/agreement tools. Human annotation and fresh confirmatory data remain. The first synthetic draft corpus and offline scorer are implemented in `evaluation/`: 128 items in 32 four-language intent families, with 96 development and 32 reserved items. Versioned annotation/output contracts, manifest hashes, gold-free exports, reserved-access logging and scoring tests are implemented. Gold is not independently reviewed, the reserved set is not blind, and no model-performance experiment has been run. Scope: FR-049 foundations, methodology and dataset procedures.

- Version annotation guidance and author synthetic English, formal Arabic, Egyptian Arabic, and mixed statements.
- Include ambiguity, unsupported rules, negation, names, missing values, multiple rules, contradictions, and temporal boundaries.
- Split development and held-out families, adjudicate gold labels, hash and isolate held-out data, and screen development families for leakage.
- Define per-field and end-to-end correctness, uncertainty handling, latency, retries, cost, and raw/post-review measures.

Exit: dataset provenance, split isolation, gold corrections, and configuration hashes are reproducible. Set acceptance thresholds after a development pilot, before confirmatory evaluation.

## Phase 6 — AI extraction and human review

Status: implementation started 1 November 2026, with Phase 5 research sign-off still pending administrator review and fresh confirmatory material. JAI has a guided-help panel. A provider-independent transport and deterministic test double now exercise candidate JSON, input hashes, bounded retry policy, cooperative timeouts and cancellation; there is no live extraction endpoint or real provider integration yet. Dependencies: Phases 3 and 5 for research acceptance; paid calls require budget approval. Scope: FR-014–FR-023, FR-054 (promoted into base scope), FR-061, FR-064.

- Add interchangeable provider adapter and a deterministic fake for tests.
- Validate syntax separately from semantics. Resolve only real entities; ask for clarification rather than inventing names, units, or institutional definitions.
- Show original input beside each proposal, editable fields, unsupported fragments, and approval state. No automatic approval or silent relaxation.
- Handle timeouts, late responses, provider errors, duplicates, revocation, and stale inputs without overwriting reviewed rules.
- Record model/prompt/schema versions, input hashes, attempts, costs, and raw versus corrected outputs.

Exit: multilingual text → proposal → clarification/correction → explicit approval reaches exactly the same scheduling path as manual rules. Demo: ambiguous Arabic/English requirement and a corrected interpretation. No real model is selected without evidence and budget authorization.

## Phase 7 — Scenarios, editing, comparison, publication

Status: partially implemented: saved runs, stale labels, weekly layouts/group filters, administrator print-to-PDF, optional chart-based PDF statistics and scoped student draft viewing work. Named scenario revisions, manual editing, comparison, publication, instructor/researcher views and assignment CSV remain. Dependency: validated Phase 4 workflow; AI integrates when ready. Scope: FR-033–FR-046, FR-059, FR-063, FR-064.

- Immutable scenario revisions, exact input-version tracking, and stale badges.
- Timetable and accessible agenda views, filters, locks, manual edits creating new draft revisions, and mandatory revalidation.
- Compare moved assignments, completeness, violation coverage, and actual preference satisfaction. Label inferred explanations.
- Atomically publish only a complete exact revision independently validated against current approved inputs. Mandatory checks cannot be disabled.
- Add student/instructor visibility, labelled CSV drafts, published CSV, printable view, and complete requirement-to-publication trace.

Exit: publication races and stale reports are blocked in PostgreSQL-backed tests. Demo: generate two scenarios, compare them, edit one, revalidate, publish, and export.

## Phase 8 — Recovery, accessibility, and operational completion

Status: planned; safeguards are implemented in earlier phases, then exercised together here. Scope: remaining FR-059–FR-064 and cross-cutting NFRs.

- End-to-end duplicates, browser retries, worker crashes, provider failures, concurrent edits/publication, expired sessions, and role revocation.
- Independent validator-failure and missing-data publication tests.
- Keyboard/screen-reader checks, mobile and desktop layouts, RTL/mixed strings, translated errors, realistic dataset measurements, backup/restore rehearsal.
- Complete CI and record exact dependency/runtime versions and verification limits.

Exit: documented reproducible deployment and recovery, no unresolved correctness blockers, and all essential requirement acceptance criteria have evidence.

## Phase 9 — Run the evaluation and write results

Status: planned. Dependencies: stable implementations, frozen configurations, and approved study design. Scope: FR-049, FR-050 and thesis procedures.

- Compare models on isolated held-out data with frozen configuration manifests.
- Evaluate accuracy, clarification, correction effort, language categories, latency/cost, scheduling outcomes, and seeded validator violations.
- Run a consented manual-versus-assisted pilot only if the study is approved; otherwise reconcile RQ3 and methodology explicitly.
- Write results, discussion, limitations, and conclusion; sync the SRS, thesis, demonstration, and source archive.

Exit: measured claims are supported by preserved artifacts; no claims about learning outcomes or superiority to UniTime without corresponding evidence.

## Extension queue

FR-051 examinations, FR-052 individual enrolments, FR-053 minimal-change regeneration, FR-055 calendar feeds, FR-056 notifications, FR-057 availability submission, FR-058 deeper solver-backed explanations. These wait until core evaluation unless the owner explicitly changes scope. FR-054 multilingual extraction is already part of the approved base, not this queue.

## Immediate next tasks

1. Select the GitHub repository and run the prepared workflow there; no destination is currently configured.
2. Start Phase 5 evaluation materials for the verified vocabulary; retain advanced constraint variants as explicitly unfinished extensions.
3. Add parent-course/component hierarchy, complete manual constraint vocabulary, replacement history, and contradiction/data-sufficiency checks.
4. Extend the verified baseline only when additional institutional rule semantics are agreed; re-run acceptance for every added rule.

## 25 October progress

Phase 4 now enforces approved room and student-group unavailability in addition to instructor rules, with typed targets, independent checks and bilingual manual forms. Weekly teaching-hour units are confirmed; limit fields/enforcement, daily policy, locks and the rest of the constraint vocabulary remain.

Weekly maximum instructor teaching hours are now configurable and independently enforced, with missing-cap coverage disclosure. Phase 4 remains incomplete: daily limits, locks, remaining vocabulary, detailed validation provenance and snapshot/configuration hashes remain.

Practical-day policy now includes configurable hard daily hour caps, separate-day activity occurrences, consecutive-period and idle-period caps plus secondary gap minimisation. Owner-selected demo caps: students 6 hours, instructors 6 hours. Phase 4 still needs locks, remaining vocabulary, detailed provenance/snapshot configuration and complete acceptance coverage; preferred daily-limit variants are not implemented.

25 October assignment locks: draft/approve/revoke workflow now supports selected instructor, day/time and room targets from validated saved runs. Approved targets are mandatory in regeneration and independently checked; source drafts remain immutable. Phase 4 continues with remaining vocabulary and detailed snapshot/solver provenance. Manual editing and publication remain planned.

### Generation evidence — 25 October
New drafts retain canonical input/configuration SHA-256 fingerprints, fixed solver profile, OR-Tools version, explicit parameter text, raw solver outcome, objective identifier, worker elapsed time and independent-validator version. The worker refuses mismatched fingerprints. Expand **How this draft was generated** under Timetable to inspect details; historical drafts are not retroactively credited with this evidence. Parallel search can produce different valid schedules with identical inputs/seed. These hashes do not authenticate a source or capture the full execution environment. Phase 4 remains in progress.

25 October Phase 4 close-out: activity/group permitted windows, conservative preflight diagnostics, detailed independent violations/coverage, per-run search settings and objective weights, historical input reruns, model hash, lifecycle/progress and independent objective cross-checks complete the manual baseline. Publication remains unavailable; this is a locally verified prototype milestone, not an institutional deployment approval. See PHASE4_ACCEPTANCE.md.

Phase 5 initial materials (25 October): `evaluation/README.md` documents the reproducible corpus/scoring workflow; 18 evaluator tests pass, including backend schema compatibility. Pending: supervisor agreement on sampling/definitions, independent multilingual annotation and adjudication, pilot-based threshold selection and fresh confirmatory data. Existing app tests/build are unchanged by this research tooling milestone.
