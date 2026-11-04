# JadwAI — complete implementation checklist

Status reviewed: **25 October 2026**, after the Phase 4 manual-baseline acceptance. This is the master checklist for the currently documented project scope, not a promise to add every conceivable scheduling feature.

## How to read this checklist

- `[x] DONE` means the stated feature is implemented with recorded evidence. It does not mean production deployment or research evaluation is complete.
- `[ ] PARTIAL` means a working subset exists; every remaining obligation is listed.
- `[ ] TODO` means planned but not implemented.
- `[ ] DEFERRED` means an optional extension outside the approved core.
- A requirement stays unchecked until all its amended acceptance criteria are met. No overall completion percentage is given: requirements vary greatly in size.

## Sources and scope precedence

- [Owner decisions](DECISIONS.md) override superseded assumptions in the [historical 64-FR SRS](../../output/SRS_updated.md).
- [Project specification](../../specifications/final-project-specification.md), [roadmap](ROADMAP.md), [verification record](VERIFICATION.md), current backend/frontend source and tests provide supporting evidence.
- Amendments: PostgreSQL; solver-assigned eligible instructors; mandatory weekly load and configurable daily limits; four extraction language categories; bilingual RTL interface; Year → Major → Group; exact five 90-minute periods; PDF and optional statistics; student group access.
- Later student request currently permits a labelled validated draft. Final published-only student/instructor access remains unfinished and must be reconciled when publication is added.

## All 64 functional requirements

### [ ] FR-001 — Academic term and calendar · PARTIAL

- [x] Edit semester name/dates/timezone, teaching days and calendar grid; exact five teaching periods with breaks.
- [ ] Multiple term creation, archiving and historical term selection; institution-defined semantic periods such as “morning”.

### [ ] FR-002 — Courses and scheduling activities · PARTIAL

- [x] Activity CRUD with lecture/tutorial/lab, duration, weekly occurrences, eligible instructors, attending groups and equipment needs.
- [ ] Separate parent courses and components; explicit minimum-capacity/attendance overrides; archival lifecycle and reference-aware deletion across approved constraints/publications.

### [ ] FR-003 — Instructors and availability · PARTIAL

- [x] Instructor CRUD, unique codes, department and approved weekly unavailable intervals.
- [ ] Aliases and ambiguity controls; dated availability exceptions. Configurable weekly maximum teaching hours are implemented.

### [ ] FR-004 — Rooms, capacities and equipment · PARTIAL

- [x] Room CRUD, capacity, lecture/lab/flexible types and equipment tags.
- [ ] Controlled equipment catalogue and aliases; room unavailable intervals are implemented.

### [ ] FR-005 — Student groups · PARTIAL

- [x] Group CRUD, size, activity links and Year → Major → Group hierarchy; group-ID conflict checks.
- [ ] Declared shared-student conflicts between different groups; explicit per-term conflict-basis setting. Group unavailable intervals are implemented.

### [x] FR-006 — Instructor-to-activity assignment · DONE

- [x] Amended scope: solver chooses an eligible instructor for each activity and keeps that instructor across its weekly occurrences. Lecture/tutorial/lab eligibility is stored separately.

### [ ] FR-007 — Bulk import with atomic validation · PARTIAL

- [x] CSV templates, preview, row errors, code-based reference lookup, atomic commit, stale-preview rejection and legacy group-column compatibility.
- [ ] Import parent courses and availability once their models exist; complete file/row/column error contract across every planned import type.

### [ ] FR-008 — Referential and domain integrity · PARTIAL

- [x] Typed records, foreign keys, required activity references, duplicate-code protection, value validation and transactional writes.
- [ ] Unified pre-snapshot integrity report with blocking defects and nonblocking coverage warnings.

### [ ] FR-009 — Supported constraint vocabulary and schema · PARTIAL

- [x] Strict backend schemas reject unsupported fields/types for the two implemented manual rules.
- [ ] Versioned complete shared vocabulary/schema; administrator vocabulary reference and unsupported examples.

### [ ] FR-010 — Manual constraint entry · PARTIAL

- [x] Manual forms for instructor unavailability and preferred periods.
- [ ] Forms for the remaining vocabulary; shared manual/AI object and provenance; experimental interaction timing.

### [ ] FR-011 — Constraint lifecycle and versioning · PARTIAL

- [x] Draft → approve → revoke; administrator approval, reviewer reference, audit and input-version changes; approved rules cannot be edited in place.
- [ ] Replacement/supersession history, rejection/deactivation/needs-review states and semantic dependency review after entity/calendar changes.

### [ ] FR-012 — Hard/soft classification and weights · PARTIAL

- [x] Mandatory unavailability and preferred-period classification; fixed documented preference penalty; mandatory constraints are not automatically relaxed.
- [ ] Editable soft weights, named weight profiles and versioned classification-change workflow.

### [ ] FR-013 — Pre-solve consistency checks · PARTIAL

- [x] Generation detects some empty domains, missing data and unsuitable rooms; infeasibility remains distinct from timeout.
- [ ] Pre-solve contradiction report naming conflicting rules and all activities with empty domains; complete checks before snapshot creation.

### [ ] FR-014 — Submit natural-language requirement · TODO

- [ ] Natural-language submission with immutable original text, author/time/context, length checks and logged minimal outbound context.

### [ ] FR-015 — Structured multi-rule proposal · TODO

- [ ] Schema-constrained zero/multi-rule proposals, source spans and plain-language interpretations; strict syntax and semantic validation; reject executable or unexpected content.

### [ ] FR-016 — Entity resolution without invention · TODO

- [ ] Resolve only existing entities; aliases/candidates, unresolved and ambiguous states, recorded resolution method; never create entities during extraction.

### [ ] FR-017 — Parameters and institutional terms · TODO

- [ ] Extract numeric parameters and units; resolve vague terms only from institutional definitions; request clarification for missing thresholds.

### [ ] FR-018 — Negation, polarity and hard/soft classification · TODO

- [ ] Handle negation, prefer/avoid polarity and mandatory/preferred strength; visibly flag unclear classification for review.

### [ ] FR-019 — Ambiguity, missing-value, contradiction and unsupported-request handling · TODO

- [ ] Rule/field-specific clarification for ambiguity, missing values, unknown entities, unsupported content and contradictions; allow approval only of resolved rules.

### [ ] FR-020 — Interpretation review interface · TODO

- [ ] Original text beside editable proposed fields, highlighted source spans, resolution/provenance, approve/correct/reject/re-extract and immutable raw versus reviewed outputs.

### [ ] FR-021 — Approval gate for the scheduling model · PARTIAL

- [x] Current manual snapshots include only approved rules; server restricts approval to administrators.
- [ ] Apply the same gate to AI proposals, unresolved fields and every expanded lifecycle state.

### [ ] FR-022 — LLM adapter and failure handling · TODO

- [ ] Replaceable LLM adapter, deterministic fake, server-side keys, bounded retries/timeouts, typed errors/refusals and explicit model selection without silent fallback. Paid calls need an agreed budget.

### [ ] FR-023 — Extraction audit and reproducibility record · TODO

- [ ] Store/export provider/model, prompt/schema versions, context, settings, raw/parsed outputs, attempts, errors, tokens, latency, cost and unreliable logging states.

### [ ] FR-024 — Immutable input snapshot · PARTIAL

- [x] Database-protected immutable academic/approved-rule snapshot per run; captured calendar, records, rules and input version.
- [x] Input/configuration content hashes, snapshot schema version 2, objective profile/weights, bounded run settings, application/model hashes, platform/version metadata, explicit parameter text, historical input selection and pre-search checks.
- [ ] Reproducible hardware/container capture and full environment/default-parameter manifests for external experiments.

### [ ] FR-025 — Timetable generation job · PARTIAL

- [x] Persistent worker-based CP-SAT generation, bounded instance sizes, 10-second default limit, two solver threads and recorded solver duration/objective.
- [x] New runs retain fixed profile/time limit/seed/worker settings, OR-Tools version, explicitly configured parameter text, worker elapsed time and objective identifier.
- [x] Administrator-editable search limit (1–60 seconds), seed, workers (1–4), objective profile and weights; saved request-payload conflict checks.
- [ ] Full environment/default-parameter manifests for external experiments.

### [ ] FR-026 — Job status and cancellation · PARTIAL

- [x] Queued/running/terminal states, polling, cancellation, heartbeat/lease monitoring and cancellation/completion race handling; cancellation discards candidates.
- [x] Score-only best-objective progress and queued/started/finished timestamps. Cancellation discards candidates; interrupted runs fail without automatic retries (retry limit zero).
- [ ] Optional retention of a complete validated cancelled candidate; intentionally unavailable in the baseline.

### [ ] FR-027 — Solver outcome semantics · PARTIAL

- [x] Optimal flag distinguishes optimal versus feasible completed results; infeasible, unknown, failed, cancelled and blocked outcomes remain distinct.
- [x] Raw CP-SAT outcome, version and explicit MODEL_INVALID reason are retained for solver-invoked outcomes.
- [x] CP-SAT model fingerprint; interrupted recovery retains lifecycle and explicit interruption outcome.
- [ ] Full environment provenance for interrupted external experiments.

### [ ] FR-028 — Hard-constraint model · PARTIAL

- [x] Full occurrence duration/coverage; instructor eligibility/continuity; room/instructor/group overlaps; capacity/type/equipment; exact teaching windows and approved instructor unavailability.
- [x] Activity/group permitted windows: union within a target across the week, intersection between targets; complete-session containment. Approved assignment locks, hard daily caps, activity distribution, consecutive-period caps, internal-gap caps/optimisation, configured weekly instructor maxima and room/group unavailability are implemented.
- [ ] Preferred daily-limit variants and entity-specific policy overrides.

### [ ] FR-029 — Soft objective and penalty reporting · PARTIAL

- [x] One penalty per applicable session outside all approved preferred windows; optimum flag and independently calculated rule/session preference satisfaction statistics.
- [x] Versioned preferences-first objective and weighted preference/idle-period objective; configurable positive integer weights. Worker independently checks applicable-session preference penalties, idle-period penalties and the total selected objective.
- [ ] Additional soft types (avoid/late/room-change/balancing), awaiting agreed semantics.

### [ ] FR-030 — Pre-solve data sufficiency report · PARTIAL

- [x] Basic missing-data/domain blocks plus separate validation limitations.
- [x] Pre-search report distinguishes blocking defects from unconfigured optional limits, names affected activities/resources/rules and reports local slot counts; explicitly does not prove global feasibility.

### [ ] FR-031 — Independent schedule validator · PARTIAL

- [x] Separate validator module with no solver import; stored run-specific checks for completeness, calendar, eligibility, continuity, room suitability, overlaps and approved unavailability; malformed assignment checks.
- [x] Independent checks for every supported baseline mandatory constraint, with occurrence/resource/time/rule details and run-specific saved reports.
- [ ] Validation history for future manually edited scenario revisions.

### [ ] FR-032 — Validation coverage statement · PARTIAL

- [x] Completeness, supported checks/errors, preference statistics and explicit saved-check coverage and unconfigured-limit limitations; draft-only status.
- [x] Baseline per-check coverage denominators, required versus optional configuration, not-applicable/not-evaluated states and exact-resource/half-open-interval conflict-basis disclosure.
- [ ] Configurable overlap/attendance semantics beyond disjoint group IDs.

### [ ] FR-033 — Validation of manual edits · TODO

- [ ] Validate edited revisions and show violations newly introduced relative to the parent.

### [ ] FR-034 — Scenario lifecycle and saving · PARTIAL

- [x] Generated runs and assignments persist automatically; recent run selector retrieves saved results.
- [ ] Named scenarios, notes, complete revision/archive lifecycle, parent links and idempotent explicit scenario saves.

### [ ] FR-035 — Stale-result detection · PARTIAL

- [x] Input-version stale badges in administrator/student views and exports; immutable old snapshots retained.
- [ ] List exact changes since generation; separate generation/validation freshness; revalidation against current inputs and comparison of stale scenarios.

### [ ] FR-036 — Scenario comparison · TODO

- [ ] Two-scenario assignment diffs, moved time/room/instructor, added/removed constraints and comparable completeness/violations/preference metrics without invented causes.

### [ ] FR-037 — Distinct scenarios by explicit variation · TODO

- [ ] Explicit scenario variations, recorded seed/profile/constraint-set changes, diversity options and identical-configuration replication labels.

### [ ] FR-038 — Manual timetable editing and locks · PARTIAL

- [x] Approved hard assignment locks for instructor, day/time and room, copied from validated saved drafts; explicit draft/approval/revocation workflow, audit/version tracking and independent validation.
- [ ] Manual occurrence edits, new draft revision per saved change and parent links.

### [ ] FR-039 — Edit-invalidates-validation rule · TODO

- [ ] Invalidate prior validation on every timetable edit; require a fresh passing report for the new revision.

### [ ] FR-040 — Publication gate · TODO

- [ ] Atomic publication gate for exact revision, current inputs, 100% completeness, zero mandatory violations and full required coverage; display failed conditions. Publication is currently unavailable, not implemented.

### [ ] FR-041 — Published versions · TODO

- [ ] Immutable numbered publications, supersession history and new-draft workflow preserving the previous publication.

### [ ] FR-042 — Timetable and agenda views · PARTIAL

- [x] Weekly timetable, days-left/days-top layouts, icon-only accessible layout controls, remembered layout and Year/Major/Group filters; student group timetable.
- [ ] Agenda/day views, instructor/room/course filters, persistent full filter state, publication/version labels and supported-viewport acceptance checks.

### [ ] FR-043 — Role-based visibility · PARTIAL

- [x] Server-enforced administrator/viewer/student access; student endpoint returns only own-group sessions/display records and rejects workspace/full schedules/statistics.
- [ ] Instructor-own-assignment and researcher experiment/publication roles; published-only reader routing. Student currently sees an explicitly labelled validated draft as a temporary owner-requested prototype behaviour.

### [ ] FR-044 — CSV export and run summary · PARTIAL

- [x] Saved statistics and an optional simplified PDF summary with charts, snapshot version and stale labels; explicit HTML/JSON remain available through the administrator API.
- [ ] Assignment CSV, named scenario/revision/hash metadata and approved-constraint deltas in the full run summary.

### [ ] FR-045 — Printable view · PARTIAL

- [x] Administrator print-to-PDF flow with grouped days, period columns, free cells, simultaneous sessions, filters and draft/version metadata.
- [ ] Student/instructor scoped print controls; visually verify native PDF pagination for large schedules and Arabic output.

### [ ] FR-046 — Requirement-to-publication trace · TODO

- [ ] Bidirectional statement → proposal → approved rule version → snapshot → run → revision → validation → publication trace with retention.

### [ ] FR-047 — Authentication and role-based access · PARTIAL

- [x] Local sign-in/out, scrypt hashes, hashed opaque HttpOnly sessions, administrator/viewer/student roles, account management, setup/reset links and password changes.
- [ ] Instructor and researcher roles with full endpoint/resource permission matrix; published reader access. University SSO is not an agreed core requirement.

### [ ] FR-048 — Audit log · PARTIAL

- [x] Transactional actor/time/action/version audit for implemented data/rule/account operations and schedule queue/cancel; append-only database protection and translated action codes.
- [ ] Audit solver start/terminal transitions and all future extraction/review/edit/publication actions; security-relevant denial events.

### [ ] FR-049 — Extraction experiment harness · PARTIAL

- [x] Versioned synthetic draft corpus (128 items/32 families), gold-free input exports, context-aware proposal contract and offline scorer for raw/declared post-review outputs, with manifest/configuration/prediction/scorer hashes.
- [x] Development/reserved family separation, normalized exact-text leakage check, explicit logged reserved access, corpus immutability checks and reproducible packaging tests.
- [ ] Actual provider runs/raw responses, repetitions, independent adjudication, reviewed frozen gold and prompt/settings, fresh blind confirmatory data and tuning controls. Reserved draft material is not a blind test.

### [ ] FR-050 — Manual-versus-assisted task instrumentation · TODO

- [ ] Consented pseudonymous manual-versus-assisted tasks; timing/corrections/final rules; separate study records and participant feedback.

### [ ] FR-051 — Examination timetabling · DEFERRED

- [ ] Optional examination calendar, exam durations, conflicts, capacity and spacing. Outside current weekly-course core.

### [ ] FR-052 — Individual enrolments · DEFERRED

- [ ] Optional individual enrolment imports and per-student conflicts/personal schedules. Current students view their assigned group.

### [ ] FR-053 — Minimal-change regeneration · DEFERRED

- [ ] Optional regeneration that explicitly minimises changes from a base revision; current constraints require a new generation and do not automatically repair a timetable.

### [ ] FR-054 — Arabic and mixed-language extraction · TODO

- [ ] Approved core amendment: English, formal Arabic, Egyptian Arabic and mixed Arabic-English extraction, with separate evaluation by category. Bilingual interface alone does not complete this.

### [ ] FR-055 — Calendar feed export · DEFERRED

- [ ] Optional authenticated iCalendar feed/export for published schedules.

### [ ] FR-056 — Schedule-change notifications · DEFERRED

- [ ] Optional affected-user notifications when published assignments change.

### [ ] FR-057 — Instructor availability submission · DEFERRED

- [ ] Optional instructor availability/preference submission as administrator-reviewed proposals.

### [ ] FR-058 — Solver-backed infeasibility explanation · DEFERRED

- [ ] Optional solver-backed infeasibility explanation identifying a possibly nonminimal/incomplete conflicting subset.

### [ ] FR-059 — Concurrent changes and publication consistency · PARTIAL

- [x] Shared/exclusive workspace locks, If-Match stale-write rejection, account version checks and concurrent generation protections.
- [ ] Semantic proposal re-review and atomic current-input publication checks, with generation versus validation freshness.

### [ ] FR-060 — Interrupted operations and recovery · PARTIAL

- [x] Acknowledged jobs survive requests/restarts; abandoned leases fail safely; database-outage recovery, atomic implemented mutations and safe errors.
- [ ] Retry original immutable snapshot explicitly; complete recovery for extraction/scenarios/revisions/publications and reconnect operation lookup UI.

### [ ] FR-061 — Duplicate requests and retry control · PARTIAL

- [x] Persistent generation request keys return the original job; one active run; concurrent retry tests.
- [ ] User/term/operation-scoped payload conflict checks across all mutations, approvals and publications; logged bounded provider attempts and late-response protection.

### [ ] FR-062 — Incomplete timetable results and cancellation completion · PARTIAL

- [x] Cancellation request/terminal distinction and race safety; no retained interim assignments or false cancelled optimality; completed schedule coverage in reports.
- [ ] Diagnostic partial source/retention decision, named unscheduled occurrences and incomplete scoped exports; optional retained complete cancelled-result flow.

### [ ] FR-063 — Validation failures and safe publication blocking · PARTIAL

- [x] Failed/crashed independent validation cannot produce a completed candidate; required checks/limitations disclosed and publication remains unavailable.
- [ ] Retryable validation reports per revision, PASS/FAIL/inconclusive history, freshness selection and tested publication blocking.

### [ ] FR-064 — Session expiry and permission changes · PARTIAL

- [x] Current server-side role/session checks; revocation on password/role/group/active-state changes; administrator reauthentication preserves drafts; student error/sign-in route.
- [ ] Full expiry/revocation UX for each future role/workflow, denial auditing and publication-time authorisation recheck.

## Constraint-by-constraint checklist

Each planned constraint needs input/schema validation, a manual form, approval/versioning, solver enforcement, independent checking, reporting and tests. A structural data field alone does not complete a managed rule type. CT identifiers come from the proposed SRS vocabulary; the final vocabulary and penalty semantics still need agreement.

- [x] Required weekly occurrences, full duration and distinct occurrence identifiers.
- [x] No simultaneous room use.
- [x] No simultaneous teaching by the same instructor.
- [x] No simultaneous sessions for the same group ID.
- [x] Capacity based on the sum of attending group sizes; room type and equipment matching.
- [x] Fit teaching days, exact period boundaries and breaks.
- [x] Instructor eligibility and same-instructor continuity across an activity's weekly occurrences.
- [x] CT-01 implemented subset: approved instructor-unavailability interval on one weekly day; multiple rules can cover multiple days.
- [ ] CT-01 full form: whole-day shorthand, multi-day selection and any agreed date-specific handling.
- [x] CT-02 weekly interval form, approval, typed room target, solver enforcement and independent validator.
- [x] CT-03 weekly interval form, approval, typed group target, solver enforcement and independent validator.
- [x] CT-04 activity and group permitted windows: typed targets, approval, solver, independent checks, diagnostics and tests.
- [ ] CT-04 parent-course targeting, dependent on the future parent-course/component hierarchy.
- [x] CT-05: approved fixed day/time/room locks.
- [x] CT-06 underlying activity data: lab/lecture type and required equipment.
- [ ] CT-06 full managed rule: explicit capacity/room overrides and provenance distinct from activity fields.
- [x] CT-07 implemented subset: preferred instructor windows with a documented one-penalty-per-session objective and applicable-session satisfaction report.
- [ ] CT-07 full semantics: avoid polarity, named institutional periods, weights and independent per-rule penalty verification.
- [ ] CT-08: late-session preference with an explicit threshold and penalty definition.
- [x] CT-09 implemented subset: minimise idle named teaching periods within instructor/group days, excluding fixed breaks, after instructor-window preferences.
- [ ] CT-10: room changes with an agreed consecutive-session definition.
- [ ] CT-11: balanced daily load with agreed units and penalty.
- [x] CT-12 mandatory subset: configurable global daily teaching-hour maxima for instructors and student groups; user-selected demo caps are 6 hours each.
- [ ] CT-12 preferred/weighted daily-limit variants and entity-specific overrides remain unfinished.
- [x] Owner addition: configurable hard weekly instructor maximum teaching hours, with independent checks. A 90-minute session counts as 1.5 hours. Missing maxima are disclosed, zero means no assignments.
- [ ] Historical candidate: explicit expected-attendance override and declared conflicting groups. Confirm semantics before adopting; current capacity uses disjoint group-size sums.

## Owner-requested interface and export features

These smaller completed features are checked independently even where their broader FR remains partial.

- [x] JadwAI identity and JAI assistant identity.
- [x] Guided JAI help/navigation panel.
- [ ] JAI natural-language understanding and reviewed rule extraction.
- [x] English/Arabic interface and RTL support for implemented screens.
- [x] Dashboard, academic-data cards, constraint list, activity log and account management.
- [x] Year → Major → Group data organisation and cascading timetable filters.
- [x] Working Generate schedule button, background state polling, saved run selection and cancel control.
- [x] Days on the left or across the top, with remembered layout selection.
- [x] Layout switch shows icons without visible text and retains accessible labels/tooltips.
- [x] Five 90-minute periods: 08:30–10:00, 10:15–11:45, 12:00–13:30, 13:45–15:15, 15:45–17:15. The owner removed the two evening slots on 18 October.
- [x] Existing activities converted to 90 minutes, occurrence counts preserved and timetable regenerated.
- [x] Print grid groups each day, places sessions in period columns, shows free periods and supports simultaneous sessions.
- [x] Save as PDF through the browser/system print dialog.
- [ ] Direct downloadable PDF file without the print dialog, if requested; not currently a core requirement.
- [x] Saved statistics per newly completed validated schedule; report downloads only when explicitly requested.
- [x] Optional one-page PDF report for administrators, including existing completed runs on demand; charts for daily sessions, preferences and resource use.
- [x] Coverage, unscheduled count, room/instructor/group overlap pairs and validation status.
- [x] Preference applicability, satisfied/unsatisfied sessions and fully/partly/not-applicable rule counts.
- [x] Room-time use excluding breaks; duration-weighted occupied seat use; per-resource minutes and daily distribution.
- [x] Solver duration, supported-objective optimality, penalty and explicit metric definitions/limitations.
- [ ] Additional constraint-specific statistics as workload/daily limits/gaps/locks become supported; do not invent an overall efficiency score.
- [x] Large labelled synthetic fixture: 64 activities, 28 instructors, 22 rooms, 21 groups and 97 weekly sessions.
- [x] Idempotent synthetic loader and pre-change backups; synthetic engineering checks are not research results.
- [x] Extreme-case tests for malformed assignments, boundary values, solver size limits, concurrency, cancellation and tiny exhaustive scheduling oracles.
- [ ] Complete long/mixed-script text, mobile, keyboard, screen-reader and cross-browser acceptance matrix.
- [x] Student account role and administrator group assignment in account create/edit.
- [x] Demo student account linked to Year 2 · Group A; live sign-in and three-session group timetable verified.
- [x] Student API excludes unrelated courses/groups, rules, full schedules, account data and statistics.
- [x] Student empty state, refresh, language switch, own account/password and sign-out controls.
- [x] Student draft and stale-input notices.
- [ ] Student final-published timetable selection, scoped PDF/CSV and instructor equivalent.
- [ ] Automatic schedule maintenance on a constraint change: not implemented and not part of the current generation contract; optional minimal-change regeneration is FR-053.

## All 23 quality requirements

Older English-only NFR-021 and undecided-auth NFR-005 are amended by the owner decisions.

### [ ] NFR-001 — Publication correctness · TODO

- [x] Current generated candidates receive independent checks; failed checks cannot complete successfully.
- [ ] Implement and test publication blocking for every mandatory violation, missing assignment and required uncovered check. No publication feature currently exists.

### [ ] NFR-002 — Validator independence · PARTIAL

- [x] Separate module without solver/model imports; seeded violations and exhaustive tiny-instance solver checks.
- [ ] Assignment-fixing model hook for direct solver/validator differential checks; CI dependency-boundary enforcement across the full vocabulary.

### [x] NFR-003 — Honest timeout semantics · DONE for the current baseline

- [x] Tiny-time-limit tests distinguish UNKNOWN from INFEASIBLE; optimality is explicit for completed candidates.

### [ ] NFR-004 — Server authorisation and secrets · PARTIAL

- [x] Protected endpoints check current role/scope; student denial tests; restricted API/worker database roles; owner credentials omitted from runtime children.
- [ ] Full role-by-endpoint matrix for instructor/researcher/publication/AI/experiments and a reproducible repository secret scan.

### [x] NFR-005 — Password storage · DONE

- [x] Local accounts use salted scrypt hashes; opaque session and reset tokens are stored hashed.

### [ ] NFR-006 — Minimal AI payload · TODO

- [ ] Minimise/log outbound context and verify that student-level personal data is excluded; no provider integration exists yet.

### [ ] NFR-007 — Privacy/policy compliance · DECISION NEEDED

- [ ] Identify institution rules, applicable law, provider terms, consent and retention responsibilities before real data/studies.

### [ ] NFR-008 — Accessibility · PARTIAL

- [x] Labelled controls, semantic forms, non-colour status text and layout-toggle accessible names.
- [ ] Agree the target standard; automated audit plus manual keyboard/screen-reader checks and documented fixes.

### [ ] NFR-009 — Failure reliability · PARTIAL

- [x] Solver cancellation, interruption, validator failure and database outage regression checks.
- [ ] Provider refusal, malformed/truncated output, rate-limit/timeout/outage fault tests with preserved statements.

### [ ] NFR-010 — Restart durability · PARTIAL

- [x] PostgreSQL-backed runs/sessions, worker lease recovery and abandoned-job failure.
- [ ] Full restart/recovery rehearsal across scenarios, extractions, publications and agreed recovery objectives.

### [ ] NFR-011 — Configurable performance · PARTIAL

- [x] Bounded generation time/size and stored solver time.
- [ ] Per-run settings, complete wall-clock metrics, agreed hardware/dataset scale and acceptance limits.

### [ ] NFR-012 — Extraction latency · TODO

- [ ] Record proposal latency and model-specific measurements; agree targets after pilot.

### [ ] NFR-013 — Scale claims · PARTIAL

- [x] Recorded synthetic fixture dimensions accompany current engineering measurements.
- [ ] Representative scalability suite and agreed maximum supported size; avoid extrapolating from one fixture.

### [ ] NFR-014 — Responsive timetable readability · PARTIAL

- [x] Responsive shell, wrapping timetable text and horizontally scrollable student grid; current narrow student view visually checked.
- [ ] Agree supported widths, implement compact agenda and verify every field is readable at each width.

### [ ] NFR-015 — Measured usability · TODO

- [ ] Task time, correction effort and participant feedback under an approved study design.

### [ ] NFR-016 — Reproducibility · PARTIAL

- [x] Immutable saved inputs, migrations, dependency locks and repeatable synthetic tests.
- [ ] Dataset/prompt/schema/configuration hashes, solver parameters/seeds/version, model manifests and rerunnable experiment artifacts.

### [ ] NFR-017 — Modular architecture · PARTIAL

- [x] Domain/API, scheduling, independent validation, reports, worker and frontend modules are separated.
- [ ] Replaceable extraction adapter and provider-swap tests.

### [ ] NFR-018 — Browser compatibility · TODO

- [ ] Agree browser/version support; execute cross-browser smoke checks. In-app browser verification alone is insufficient.

### [ ] NFR-019 — Data retention · DECISION NEEDED

- [ ] Agree and implement retention/deletion rules for inputs, drafts, publications, AI logs and study records.

### [ ] NFR-020 — Backup/recovery · PARTIAL

- [x] Local pre-conversion/input backups exist.
- [ ] Full database backup, tested restore, scheduling/storage policy and recovery runbook.

### [ ] NFR-021 — Localisation, amended · PARTIAL

- [x] English/Arabic interface and RTL implementation.
- [ ] Complete language QA for all future screens, errors, mixed text and exported documents. English statistics files currently preserve Unicode names but are not a translated report interface.

### [ ] NFR-022 — Observability · PARTIAL

- [x] Audit records, health/readiness/heartbeat and job-correlated failure logging.
- [ ] Structured correlation IDs across requests, solver, validation and extraction with a diagnostic runbook.

### [ ] NFR-023 — Licences · TODO

- [ ] Dependency licence inventory, third-party notices and provenance of any reused assets/code; UniTime remains a reference implementation.

## Evaluation and thesis deliverables

- [x] Draft versioned annotation guide and proposal contract for the supported Phase 4 vocabulary.
- [ ] Finalise them after independent review and supervisor agreement.
- [x] Author 128 synthetic draft labels across English, formal Arabic, Egyptian Arabic and mixed-language requirements.
- [ ] Independently annotate/adjudicate and approve the labels before research use.
- [x] Include draft examples of compound rules, negation, ambiguity, contradictions, unsupported requests, unknown entities, temporal boundaries and unit conversion.
- [ ] Agree dataset size, paraphrase families, independent review/adjudication and gold-label correction procedure.
- [x] Separate development/reserved intent families, hash the corpus/contracts and require logged opt-in access in the runner; development exports omit gold.
- [ ] Establish fresh independently authored/adjudicated blind confirmatory material and stronger researcher access controls. The current source-accessible reserved set is not blind or OS-isolated.
- [ ] Choose models and approve spending limits before paid runs.
- [ ] Freeze prompts, schema, model settings, retry policy, seeds and objective definitions before confirmatory evaluation.
- [ ] Measure raw and post-review semantic accuracy, rule precision/recall, entity/parameter/strength correctness and clarification behaviour.
- [ ] Measure invented entities, unsupported-content handling, paraphrase/repetition consistency, correction effort, latency and cost.
- [ ] Run scheduling tests with completeness, independently checked violations, preferences, runtime and stated scale.
- [ ] Approve participant recruitment, consent and pseudonymous storage; run manual-versus-assisted pilot or explicitly revise the research question if no study is possible.
- [x] Thesis source was previously updated and successfully compiled for the earlier foundation milestone.
- [x] Update Chapters 1--3 for the 25 October Phase 4 close-out and draft Phase 5 tooling, preserving the distinction between implementation/self-tests and measured research results; existing source compiled in the built-in editor.
- [ ] Write measured results, discussion, limitations and conclusion; current thesis has Chapters 1–3, not completed research results.
- [ ] Verify bibliography/provisional citations and remove unsupported performance/learning-outcome claims.
- [ ] Sync final SRS, architecture, checklist, thesis, demo script and source/archive.

## Deployment and delivery checklist

- [x] Independent `jadwai/` folder, PostgreSQL migrations and local setup/dev scripts.
- [x] Restricted application/worker DB roles, persistent job worker and health/readiness endpoints.
- [x] Backend tests, frontend tests and production frontend build executed locally.
- [x] CI definition and application/container configuration prepared.
- [ ] Select a repository, commit source with secrets excluded and run the remote CI workflow.
- [ ] Build/test production containers and verify migrations, worker, web routing and restart behaviour together.
- [ ] Configure actual deployment, HTTPS/secure cookies, secret management, backups and operational monitoring.
- [ ] Complete end-to-end role, recovery, publication, AI and accessibility acceptance checks.
- [ ] Final handover: reproducible install, seed/restore procedure, known limits and administrator/student/instructor demonstration.

## Next implementation order

1. Complete remaining vocabulary; approved assignment locks, configurable hard daily caps, weekly maxima, activity distribution and gap controls are implemented. Agree preferred daily-limit variants and institution-specific policy.
2. Complete contradiction/data-sufficiency reporting, snapshot hashes/configuration and detailed validation reports.
3. Build scenario revisions, manual edits, comparisons and atomic publication; switch students to the agreed publication policy.
4. Prepare the multilingual dataset and implement JAI extraction/clarification/review with a fake provider first.
5. Complete experiment tooling, operational/accessibility verification, approved research runs and thesis results.

These steps are priorities, not new user approvals for paid services, deployment, studies or undecided institutional policies.

## Evidence index

- Academic data/calendar/imports: `backend/app/{academic,schemas,imports,reference_periods,models}.py`; `frontend/src/{CalendarSettings,GroupHierarchy,ImportData,components}.tsx`.
- Authentication/student scope: `backend/app/{accounts,dependencies,main,security}.py`; migration `0010_student_accounts.py`; `frontend/src/{Accounts,StudentPortal}.tsx`.
- Generation/checking: `backend/app/{schedules,solver,schedule_worker,validation}.py`; `worker/main.py`; `frontend/src/Timetable.tsx`.
- Exports/reporting: `backend/app/statistics.py`; `frontend/src/{SchedulePrint,ScheduleGrid}.tsx` and `frontend/src/api.ts`.
- Regression evidence: `backend/tests/`, `frontend/src/*.test.*` and [verification record](VERIFICATION.md). Latest recorded run: **172 backend + 27 frontend tests passed**; two student tests rerun after strengthening cross-group exclusion; production build passed. This checklist review did not rerun application tests or perform new live feature verification.

25 October milestone: room/group unavailability completed for weekly intervals; teaching-hour load units confirmed. See the latest verification entry for exact suite counts and UI checks.

25 October workload milestone: configurable maximum weekly teaching hours are implemented in forms/CSV, exact-minute storage, solver, independent validation and reports. Existing instructor caps remain unconfigured until entered. Daily limits and assignment locks remain.

25 October practical-day milestone: editable 6-hour daily demo caps for both roles, max 3 consecutive periods, max 1 internal idle period, separate-day activity occurrences and preference-first gap minimisation are implemented and independently checked. The current v12 timetable meets these hard settings; still synthetic and unpublished. Real curriculum/eligibility data and institutional validation remain.

25 October assignment-lock milestone: administrator-selected instructor, day/time and room locks are saved as drafts, explicitly approved, included in immutable run inputs and enforced by CP-SAT plus independent validation. Instructor locks preserve activity-wide continuity. Existing drafts remain unchanged; regenerate after approval. 175 backend and 28 frontend tests pass. Phase 4 remains incomplete.

25 October generation-evidence milestone: new immutable snapshots contain SHA-256 fingerprints of canonical saved inputs (excluding the provenance envelope) and fixed solver configuration. Worker verifies both before solving. Results retain raw solver status, OR-Tools version, explicit parameters, objective ID, elapsed worker time and validator version. Timetable exposes bilingual generation details; old drafts disclose absent evidence. Fingerprints are integrity identifiers, not signatures. Parallel search does not guarantee identical schedules.

Phase 4 baseline close-out (25 October): see PHASE4_ACCEPTANCE.md for the supported scope and executable acceptance evidence. Partial FR headings above continue to disclose broader SRS extensions; closing this baseline does not mark them complete.

25 October Phase 5 initial release: corpus `0.1.0-draft`, 96 development/32 reserved examples, 18 evaluator tests pass. No extraction model was selected or called; oracle fixture scores are software tests only. Research thresholds, human review and adjudication remain unfinished.

4 November 2026 realistic-timetable milestone (branch `feature/realistic-timetables`):
- [x] Doctor/TA positions enforced in course setup, activities, input checks, solver and validator
- [x] Instructor accounts; instructor and student portals show only published schedules; personal CSV export
- [x] Room features / special rooms; activity-room rule
- [x] Multi-period sessions; half-hour and every-day rules; five limit rule types
- [x] Convenience objective with independent recount; warm-started search; 600-session limit
- [x] Built-in English/Arabic constraint parser feeding the proposal review flow; GPT instructions extended
- [x] Exam halls with splitting, TA invigilators, back-to-back avoidance, configurable cohort lists
- [x] Named scenarios, validated manual edits, comparison, publish/unpublish (teaching and exams)
- [ ] Real institutional data (room capacities/types, doctor/TA positions, course groups) — owner
- [ ] Paid GPT pilot and human annotations — owner
