# Verification — current through 25 October 2026

Current result: **194 backend tests and 30 frontend tests pass; TypeScript/Vite build passes.** Phase 4 manual-baseline acceptance is recorded in [PHASE4_ACCEPTANCE.md](PHASE4_ACCEPTANCE.md). Dated sections below are historical milestones, superseded by the latest record.

## Historical foundation checks — 15 October

## Automated checks

Final `bash scripts/check.sh` succeeds:

- 38 PostgreSQL-backed tests.
- 7 frontend tests, including a rendered app draft-preservation test and a CSV preview/commit flow test.
- TypeScript checking and Vite production build.

All database test fixtures apply the real Alembic migration chain in disposable isolated schemas. They never reset the saved workspace. The relational migration is also tested through downgrade to 0005 and upgrade to 0006, preserving records, equipment, eligibility/group links, and input version.

One upstream warning remains: Starlette's TestClient deprecates its httpx integration in favor of httpx2. Tests pass on the locked versions; the warning is not hidden. The earlier Alembic path-separator warning was corrected in configuration.

## Account and operational coverage

Tests cover authentication, expiry, HttpOnly/SameSite cookies, viewer restrictions, CSRF request-header enforcement, current-password checks, one-time reset links, hashed token storage, reset expiry/reuse rejection, account activation/deactivation, role changes, immediate revocation, stale account updates, and per-account/client rate buckets.

Two active administrators attempting simultaneous self-demotion produce one success and one conflict; a last administrator remains. Academic writes with the same expected version also have exactly one winner. Security/account events do not increment the academic input version.

Audit rows have stable action codes and parameters for English/Arabic display. PostgreSQL rejects UPDATE, DELETE, and TRUNCATE on audit history. The live API role `jadwai_app` was inspected: no superuser, database-creation, role-creation, or schema-object-creation privilege; audit INSERT allowed, UPDATE/DELETE denied. API and worker have separate restricted credentials, and normal runtime child processes omit migration-owner/bootstrap credentials.

Worker maintenance removes only expired credentials/rate buckets and refreshes its heartbeat. Readiness checks schema, workspace, and heartbeat freshness. A controlled database stop returned HTTP 503 with a sanitized error; after restarting, readiness returned HTTP 200 without restarting the app/worker. All 15 records and input version 3 remained intact.

## Academic data coverage

Typed instructor, room, student-group, and teaching-activity tables replace the original generic JSON record store. Eligibility/group links and rule instructor references use real foreign keys. Deferred database checks reject orphan/wrong-kind details and activities lacking instructor eligibility or student groups. Domain bounds and unique codes are database-enforced alongside API validation.

The live migration to schema 0006 retained all 15 records, 7 instructor-eligibility links, existing approvals, and input version 3. Room equipment and activity-required equipment have typed array fields.

Semester settings support paired optional dates, timezone, teaching days/hours, and period length. Tests reject invalid calendars, stale updates, rules outside the calendar, and calendar changes conflicting with existing rules.

CSV preview is read-only. Commit re-parses/revalidates every row, checks the preview's input version, and saves all rows or none. Tests cover invalid rows with no partial writes, within-file duplicates, existing-code lookup, missing references, and stale previews. The UI test verifies that a valid preview is required and commit sends its exact version. Limits are 500 rows and 1 MB at the file-input boundary, with a matching character limit on API text input.

## Browser checks

The running app was inspected through the Codex in-app browser:

- Existing saved records and counts remain visible after migrations/restarts.
- Accounts page lists the existing administrator and exposes create/edit/recovery/session controls; new-account form fields and default viewer role were inspected without creating extra live accounts.
- Semester settings show persisted defaults and editable calendar fields.
- Academic data exposes the CSV import dialog with category-specific headers and a disabled preview action before file selection.
- English/Arabic interfaces, JAI panel/navigation, and desktop/mobile layouts were checked during this project. Account/settings screenshots are retained with this milestone.

Full browser password changes and live CSV commits were not performed on the saved workspace; automated tests cover those paths with isolated/mocked data. This is representative browser QA, not a complete accessibility or cross-browser audit.

## Deployment and external verification

Shell syntax checks pass. `docker compose -p mizan -f compose.yaml -f compose.app.yaml config --quiet` succeeds. API/worker/static-web Dockerfiles and same-origin Caddy configuration are provided, but the deployment images have not been built or published. GitHub Actions steps are prepared and their commands pass locally; no repository remote has been selected, so there is no remote Actions-run evidence.

## Remaining scope

The local Phase 2 implementation is complete. Phase 3 has a working relational academic-data/import/calendar foundation, but parent-course/component hierarchy, the full supported constraint vocabulary, immutable rule replacement history, and contradiction/data-sufficiency checks remain. Workload units still need the owner's decision.

No solver, independent timetable validator, immutable approved input snapshots, generated schedule, AI extraction, publication/scenario workflow, or research experiment is claimed. JAI is currently a guided companion. No paid AI calls or external deployment were made.

## Design references

The database privilege boundaries follow [PostgreSQL's GRANT model](https://www.postgresql.org/docs/current/sql-grant.html). Recovery links are random, hashed, expiring, and single-use, consistent with the relevant principles in the [OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html); this is not a claim of a complete security audit or certification.

## 17 October 2026 — draft schedule generation

- Added OR-Tools CP-SAT 9.15.6755, independent checks in `backend/app/validation.py`, and migration 0007 for persistent jobs with database-protected immutable snapshots.
- Administrator-only generation/history/detail/cancel endpoints; input-version checks, idempotency keys, one active workspace run, transactional job claims, monitored cancellation, and abandoned-run recovery. A repeated key returns its original snapshot/run even after inputs change. Cancellation before the terminal commit discards the result; no partial result or cancelled optimality claim is retained.
- Assigns every weekly occurrence, one eligible instructor per activity across all occurrences, time and suitable room. Prevents instructor/group/room overlap; respects approved instructor unavailability, room capacity/type/equipment, semester days/grid and durations. Only approved rules enter snapshots.
- Preferred-period objective: each session for an instructor with approved preferred periods incurs one penalty if the entire session fits none of that instructor's preferred windows; otherwise zero. Weights and other preference types are not implemented. Optimality labels concern this objective for the frozen snapshot only.
- Limits: 160 occurrences, 50,000 placement candidates, 10 seconds of solver search, two search threads. Too-large models are blocked. INFEASIBLE and UNKNOWN are separate; a search timeout never proves infeasibility. Solver/model errors become failed runs. Interrupted runs become failed (or cancelled if requested), with explicit new-run retry.
- English/Arabic timetable page: Generate Schedule, progress/cancel, recent persistent drafts, frozen names, group filter, weekly session cards and stale-data warnings. Unpublished drafts are restricted to administrators.
- Local checks: **48 backend tests and 11 frontend tests pass**; TypeScript and production build pass. Seeded validation corruption covers incomplete assignments, invalid room/instructor, invalid times, conflicts and mandatory availability. PostgreSQL tests cover idempotency, stale snapshots, denied viewer access, queued/running cancellation, completion/cancellation races, validator failure, interruption and immutable snapshots.
- Live API + separate worker + restricted runtime database roles produced a complete **7-session** draft from existing synthetic inputs, all seven supported check categories passed, and academic records/input version remained unchanged. Website Generate Schedule was exercised against the same running stack.
- Drafts are **not publication-ready**: undefined weekly workload semantics, daily limits and assignment locks remain absent. Full-scope validator coverage, snapshot schema/hash provenance, manual timetable editing, publication, exports and AI extraction remain outstanding. These are engineering verification checks, not thesis research results.

## 17 October 2026 — adversarial edge-case pass

- Added 75 backend edge-case checks: malformed result shapes/types (including Python boolean/integer aliasing), empty input coverage, exact closing-time/back-to-back boundaries, capacity and room-type boundaries, instructor continuity under contradictory availability, candidate/occurrence limits, 50 seeded randomized cases checked against independent exhaustive oracles, eight concurrent requests with distinct/repeated keys, and competing worker claims.
- First adversarial run exposed ten failing cases: malformed rows could raise exceptions, boolean occurrence identifiers could be accepted as zero, and an empty snapshot could pass vacuously. The validator now checks assignment shape and exact scalar types before dictionary lookups/counting, and rejects datasets with no activities or rooms. Failed validation never enables publication.
- Added five frontend edge-case checks: icon-only accessible controls with persisted layout across language/remount changes, denied browser-storage access, hostile multilingual markup rendered as text, stable generation keys after network errors, and UNKNOWN never labelled as proven infeasible. Layout preference now survives storage errors in memory, and unbroken text wraps within session cards.
- Verification: full original+expanded backend suite **102 passed**, then **21 additional multi-resource/actual-limit cases passed** (123 backend cases total). Frontend **16 passed**; TypeScript/production build passed. Total verified cases: **139**. The single existing Starlette/httpx deprecation warning remains. These bounded checks do not establish production capacity, complete supported-rule coverage or research performance.

## 17 October 2026 — large populated semester

- Added 120 clearly labelled synthetic academic records (24 instructors, 18 groups, 18 rooms, 60 activities) and 24 approved demo rules, preserving all previous records and rules. The batch adds 90 weekly occurrences; the current workspace has 97 in total. The single input-version increment marks previous drafts stale. Pre-load academic inputs, including draft rules, are backed up under ignored `backups/` with restricted file permissions.
- The original Cartesian placement model hit the 10-second search limit on this actual dataset and correctly returned UNKNOWN. Replaced its Boolean placement expansion with factored time domains, shared instructor choices, optional room/instructor intervals and resource NoOverlap constraints. Mandatory availability, room suitability, continuity, symmetry and preferred-period semantics remain unchanged; configured size/search limits remain in place.
- The revised model completed and independently validated all 97 occurrences in a measured local call of 0.359 seconds total (0.318 solver seconds), proving the best score for the implemented preferred-period objective. This single local synthetic measurement is not a general performance guarantee or thesis research result.
- The existing exhaustive-oracle, malformed-result, concurrency and persistence tests are retained; an additional 97-session synthetic regression checks complete assignment and independent validation.
- After restarting the actual API/worker stack, a saved version-4 draft completed with all **97 assignments**, passed all seven independent supported checks, and left academic input records/version unchanged. The website displays 64 activities, 28 instructors, 22 rooms, 21 groups and 25 approved rules. Full backend regression suite: **123 passed**, plus the newly added large-semester regression **1 passed** (124 backend cases total); existing frontend suite remains at 16 passing tests (140 cases across both suites). Re-running the data loader reported `already_loaded`, 120 records, input version 4, confirming no duplicates or version changes.

## 17 October 2026 — Year → Major → Group

- Migration 0008 adds nullable study-year/major classification to group details, with range/nonblank constraints, preserving every group ID and activity-group FK. Explicit English year labels are recovered; only labelled LOAD demo groups receive synthetic sample majors. Existing unknown institutional majors remain unassigned. Actual workspace version advanced from 4 to 5; historical snapshots remain unchanged and stale.
- Nested bilingual academic-data display, classification fields in group forms, hierarchical labels in activity selection and timetable cards, and cascading year/major/group timetable filters. Changing a parent filter clears dependent selections. Group conflicts continue to use exact group IDs; a shared year/major alone does not prohibit parallel teaching of different groups.
- CSV supports optional year/major columns and legacy three-column group files. Case-only variants of an existing major within a year share one spelling, including rows within one CSV batch. A major without a year and invalid year ranges/types are rejected by the API.
- Validation: full backend suite initially 131 passed with one new CSV canonicalisation test exposing a batch issue; fixed and all eight hierarchy cases then passed (132 unique backend cases). Frontend 17 passed, including cascading filter reset/assignment filtering. TypeScript and production build passed. Live site displays all 21 groups nested under three years and the recorded majors, with original unknown majors clearly labelled.

## 17 October 2026 — schedule PDF option

- Added Save as PDF via the browser/system print dialog, using a dedicated print-only React portal. The export is a chronological A4 landscape table with repeating column headings and rows configured to avoid page splitting; application navigation, controls and assistant are omitted. The print document is removed after the dialog closes.
- Export reflects the selected saved draft and current year/major/group filters, with explicit scope/count, snapshot version/timezone, reference, stale warning and unpublished/coverage limitations. Arabic uses RTL text and LTR time ranges. This printable draft export does not introduce publication or server-generated PDF downloads.
- Frontend **19 tests pass**, including filtered print contents, stale/draft warnings, print invocation/cleanup and Arabic markup. TypeScript/production build passed. The live website exposes the control beside the saved draft. These automated checks verify print content/behaviour, not the native system dialog or a saved PDF's rendered pagination.
- PDF day grouping: sessions are now grouped into one table body per teaching day with a single merged day-label cell (`rowSpan`) rather than repeating the day for every session. All session details remain chronological; day boundaries have a stronger separator and long groups may continue across pages. Added a regression asserting two Sunday sessions produce one Sunday label spanning both rows.
- Reference-style PDF timetable: replaced the flat session list/merged labels with a real day-by-time matrix. One row per configured teaching day; columns follow the snapshot's period length and teaching hours. Sessions span their actual duration, including half-hour starts; concurrent activities occupy separate lanes within the same day row. Adjacent sessions reuse lanes, and contiguous globally empty periods merge into Free cells (including entirely free days). Group codes have a full hierarchy key below the matrix. Arabic retains right-to-left session text with physical days-left/time-left-to-right alignment. The example image's institutional hours and breaks were not applied to the saved semester.
- Build and 20 frontend tests pass after replacing the two superseded list-format tests with a matrix regression covering column counts, duration spans, concurrent lanes and Free cells. Native PDF pagination remains a manual visual check.

## 17 October 2026 — exact seven-period conversion

- Migration 0009 persists versioned named teaching periods. Validated ordered, non-overlapping minute boundaries; legacy regular calendars remain supported. Snapshots include the period list. Solver choices use exact starts/ends and independent validation rejects off-period/break placements.
- Owner-authorised conversion: 64 activities now last 90 minutes; all 97 weekly occurrences retained, workspace input version 6. Existing rule, activity/group/instructor IDs and historical drafts preserved. Pre-change input backup retained under ignored `backups/`.
- PDF matrix uses the snapshot's exact seven windows, numbered First through Seventh Period with real boundary times. Legacy snapshots keep their original grids. Semester settings exposes the matching preset, and activity forms offer compatible durations.
- Full backend suite **138 passed**; frontend **21 passed**, including exact seven PDF header ranges and placement into the seventh column; TypeScript and production build passed.
- Live regeneration saved a new version-6 draft with all **97 sessions**. Every assignment was confirmed to match one of the seven exact `(start,end)` pairs and to last 90 minutes; all independent supported checks passed. Academic inputs were unchanged by generation. Historical drafts remain available, with the newly generated version selected in the website.

## 17 October 2026 — automatically generated statistics files

- Completed validated runs store versioned statistics in their result before the terminal transaction commits. Downloads are administrator-only HTML attachments or JSON, based on the exact generation snapshot; legacy completed drafts can generate reports on demand. Stale status is checked at download without altering academic inputs.
- Frontend automatically downloads the HTML attachment for a generation initiated on the active timetable page, once per completed run, and offers Statistics report / JSON downloads later. Display filters do not change the full-schedule statistics. Direct authenticated attachment links are used after an authenticated status check because blob downloads did not work reliably in the in-app browser.
- Measured fields: coverage; room/instructor/group overlap-pair counts; approved input counts; preference applicability/satisfaction at rule and session levels; room time excluding breaks; duration-weighted seat utilization during occupied periods; daily distribution; per-resource teaching minutes; solver duration, supported-objective optimality and penalty. Every ratio includes its definition. Undefined workload compliance, daily limits and locks remain explicitly unevaluated. No fairness or overall efficiency score is invented.
- Unit calculations checked against hand-counted sessions (50% applicable preference satisfaction, 43.75% room-time use, 80% occupied-room seat use), including zero-applicability denominators, break exclusions, HTML escaping and Unicode. Persistence, stale reports, invalid formats and permission checks pass. Full backend suite **142 passed**; frontend **22 passed**; production build passed. Three report tests rerun successfully after final HTML layout cleanup.
- Live generation produced a saved 97-session report and automatically downloaded `JadwAI-statistics-99e6b8c3-aa0c-4788-9feb-7fccb945a4bc.html` to Downloads. Repeat-download was also verified. This run has 97/97 assigned sessions; zero overlap pairs in all three categories; 2/2 applicable preferred sessions satisfied, one fully satisfied rule and 11 not-applicable rules; room-time utilization 12.60%, occupied-room seat utilization 59.88%. These are synthetic engineering checks, not thesis evaluation results. Verified report copies are in `output/statistics/`; temporary static preview removed after visual QA.

## 17 October 2026 — student portal

- Migration 0010 extends roles and adds a group foreign key. Account create/edit validates group existence/type and requires it for students; changed group permissions revoke sessions. Existing administrator and viewer workflows remain intact.
- Dedicated `/api/student/schedule` endpoint filters assignments on the server, strips unrelated records, rules and aggregate reports, and ignores caller-supplied group selectors. Other workspace/schedule endpoints reject students. Empty/unassigned states are supported.
- Full backend suite: **144 passed**. Two student cases rerun after strengthening the other-group course exclusion assertion: **2 passed**. Frontend regression suite: **22 passed**. TypeScript and production build passed.
- Live demo login verified in the browser: Year 2 · Group A, three sessions from the existing validated version-7 draft. English student layout visually checked at the current narrow viewport; timetable scrolls horizontally. Screenshot: `docs/preview-student.png`. Arabic text/RTL supported in implementation; no full accessibility-conformance claim.


## 18 October 2026 — five teaching slots

Five-slot preset tests: 6 backend cases passed, including rejecting an evening assignment; 23 frontend tests and production build passed. Current-preset print test checks exactly five period columns plus the day column and no sixth/seventh headings. A separate test preserves historical seven-period snapshot rendering.

Live regeneration saved run `ff60898e-cba8-4c7a-931a-974d3a7101d0` against input version 11: all 97 sessions assigned, every start/end pair matches one of the five periods, latest session ends 17:15, and all supported independent checks passed. Existing historical drafts/PDFs are unchanged; users must select the new run and export a fresh PDF. Browser visual recheck was unavailable because the current browser connection reported no tabs.


## 18 October 2026 — optional chart PDF

- Removed the generation-completion download effect and its tracking reference. Frontend regression verifies generation makes no statistics request or anchor click, and explicit PDF button makes exactly one status-check request before the attachment download.
- New ReportLab endpoint defaults to PDF; legacy explicit HTML/JSON formats remain protected. Existing saved statistics are reused without input changes. PDF tests cover one-page output, known coverage/preference/resource percentages, no-applicable preferences, stale-input warning and the draft/unsupported-check limitations.
- Full backend suite: **145 passed**; frontend: **23 passed**; production build and pip dependency check passed.
- Live authenticated PDF retrieval for run `751791b6-fd83-4a77-a68a-d0cc6f58d824` returned application/pdf. Saved sample: `output/pdf/JadwAI-schedule-report.pdf`. Rendered with Poppler and visually inspected: one page, clear charts, no overlapping/clipped content. A browser download-event wait timed out; a subsequent explicit button click issued both the status-check and attachment GET and the API returned 200 for both, without an application error. The browser file-save completion was not confirmed; the authenticated API response and rendered PDF were independently verified.

## 18 October 2026 — descriptive PDF filenames

Timetable printing temporarily sets the document title to a safe descriptive basename containing JadwAI, semester, department, Timetable, selected year/major/group (or All-Groups), Draft, input version, creation date and short run ID. After printing/cancelling or component unmount, the original title is restored. Browser/system print dialogs generally use this title as the suggested PDF name; the user can still change it. Statistics attachment names use Statistics-Report and Full-Schedule to avoid suggesting that display filters change the report. Content-Disposition supplies an ASCII fallback plus RFC 5987 UTF-8 filename; frontend no longer overrides it with a UUID-only name. Reserved filename characters/control codes are stripped. Frontend 24 tests and production build passed; statistics backend 6 tests passed, including Unicode/control-character safety and response naming. No PDF content/layout changes.


## 25 October 2026 — room/group unavailability

- Migration 0011 adds optional typed room/group foreign keys, exactly-one-target and expanded mandatory-strength checks; legacy instructor rules remain intact. A lossy downgrade is refused if room/group rules exist. Readiness expects revision 0011.
- Forms and cards support room/group targets in English/Arabic, enforce mandatory strength and retain draft/approve/revoke flow. Referenced resources cannot be deleted. Approval rechecks current rule validity. Statistics include all three unavailability categories.
- Independently tested solver and validator: room/group closures, ignored draft rules, exclusive interval ends, infeasibility when no windows remain, overlapping closure intervals and alternative-room use. API tests cover invalid/multiple/wrong-kind targets, strength, approval, persistence, deletion protection and invalid direct database writes. Unsupported approved rules fail safely.
- Full backend regression run: **151 passed**. After two final edge-case tests were added, the availability suite was rerun: **7 passed**, yielding 153 unique backend tests in the current tree (not a second full-suite execution). Frontend **25 passed**; production build passed.
- Applied migration locally; verified the live English form changes the resource selector and preview for both room and group types. Preview screenshot: `docs/preview-resource-unavailability.png`. No sample closure was saved to the live workspace during UI verification.


## 25 October 2026 — weekly teaching-hour limits

- Migration 0012 adds nullable integer max_weekly_minutes with range/half-hour integrity checks and refuses lossy downgrade when configured limits remain. No default caps or live input changes were introduced. Readiness expects revision 0012.
- API/forms/CSV accept optional finite maxima in 0.5-hour increments (0 through 168, the physical weekly bound). Zero and blank remain distinct; legacy records/imports remain supported. Input edits preserve immutable old snapshot values and mark previous drafts stale.
- CP-SAT constrains the sum of duration times weekly occurrences for each selected instructor; independent validation separately sums assigned elapsed minutes. Reports include per-instructor assigned hours, maximum, configuration and exceeded status. Missing maxima and legacy saved reports are disclosed. Daily limits and locks remain unsupported.
- Full backend suite: **164 passed**. Frontend: **26 passed**. TypeScript and production build passed. Coverage includes exact-cap success, under-cap infeasibility, alternative-instructor selection, zero versus null, multiple attending groups counted once, invalid/nonfinite/boolean/fractional inputs, CSV, integer persistence, DB constraints and frozen snapshot preservation.
- Applied migration locally. Live instructor cards show Not configured; edit form and help text visually verified without changing any instructor's maximum. Screenshot: `docs/preview-weekly-workload.png`. A synthetic PDF was rendered and visually checked to verify updated workload disclosure without layout overlap. No live timetable regeneration was necessary because no live cap values were set.


## 25 October 2026 — practical-day scheduling

- Migration 0013 persists calendar realism_policy without enabling defaults on migration. API validates it and requires named periods; settings/snapshots carry it. Disabling it preserves legacy scheduling. Lossy downgrade with an active policy is refused.
- Solver policy encoding is in realism_model.py; independent measured checks are in realism_validation.py. Checks cover per-instructor/per-group daily teaching hours, repeated activity occurrences on one day, consecutive named periods and internal idle named periods. Fixed breaks are excluded. Gaps are a secondary lexicographic objective after the original instructor-window objective.
- Tests cover policy enable/disable, exact daily caps and infeasibility, independent seeded distribution/consecutive/gap violations, break exclusion, input snapshot immutability, invalid policy data, separate preference counts and persisted/stale calendar versions. Full backend **172 passed**; frontend **27 passed**; production build passed.
- Read-only trial on a saved 97-session fixture found a validated optimum with 4.5 maximum daily teaching hours and no internal gaps. This trial is separate from the retained generation; it is not a research result.
- Retained run `87a368fd-8e67-40a6-878a-04cc4761873a`, input version 12: **97/97** sessions; maximum student daily hours **4.5**, instructor daily hours **6.0**; maximum consecutive periods **3**; maximum internal idle periods per resource/day **1**; total idle periods across instructors/groups **5**. It passed all 14 configured/supported checks. Two applicable instructor-window sessions remain unsatisfied; optimum was not proven within the bounded search. Do not substitute the trial's zero-gap/zero-penalty result for this saved draft.
- Pre-change backup under backups/before-practical-days-20261025T160001Z.json; verification summary output/practical-days-verification.json. Live UI confirmed saved caps 6/6, consecutive 3, idle 1 and selected latest v12 draft. Screenshot docs/preview-practical-days.png. New report PDF rendered and visually checked: one page, readable policy disclosure, no clipping/overlap. No report downloads were added to generation.

## 25 October — assignment locks
175 backend tests and 28 frontend tests pass; TypeScript/Vite production build passes. Added full/partial selection UI test, full lock preservation, activity instructor continuity, independent corruption detection, contradictory-lock infeasibility, draft exclusion, lifecycle, retry idempotency and viewer denial tests. Migration 0014 adds typed source-linked lock storage. PDF notes rendered and visually inspected on one A4 page. Local browser dialog verified without saving a default lock; current v12 timetable retained unchanged.

## 25 October — generation evidence
178-test full backend suite passed; focused provenance/statistics rerun passed 10 tests including one additional integrity-refusal test (179 backend tests total). All 28 frontend tests and production build pass. Live run `6393b115-2e57-4cdc-9695-13cbbacacf75` retained 97 assignments on input version 12, passed independent validation and reported OPTIMAL for the implemented objective. Its input fingerprint verifies, with explicit OR-Tools 9.15.6755 settings. Saved evidence: `output/generation-evidence-verification.json`; browser preview: `docs/preview-generation-evidence.png`. Existing drafts are retained without retroactive metadata.

## 25 October — Phase 4 manual-baseline acceptance
194-test full backend suite passes; all 30 frontend tests and production build pass. Final live run 0aeb884a-de45-4964-a48e-6e2d4db4cb13 retained 97 sessions and passed independent hard-rule, preference/idle-component and total-objective validation. Snapshot/configuration hashes verify. Explicit not-applicable and unconfigured-limit coverage remains visible; no publication functionality is claimed. See PHASE4_ACCEPTANCE.md and output/phase4-acceptance.json.

## 25 October — Phase 5 draft corpus and scorer
18 evaluator tests pass under `backend/.venv/bin/python -m unittest discover -s evaluation/tests -v`, including current backend RuleInput/RealismPolicy compatibility for both splits, reproducible packaging, reviewed-release overwrite refusal, manifest mismatch detection, default reserved isolation, explicit access logging, gold-free CLI export, duplicate/unknown/missing predictions, malformed outputs, numeric limits, false-positive duplicate/unknown proposals, empty-class denominators, title/order invariance and CLI score hashing. Full-corpus structural validation passes for 128 cases in 32 families (four language categories). Reserved author-review access is logged; this is not blind evaluation.

`evaluation/README.md` and its annotation guide record unreviewed synthetic provenance and pending human adjudication. No model run, API expense, extraction accuracy finding or participant result is claimed. Existing application code and database were not changed in this milestone. The project check script now includes the evaluator suite.
