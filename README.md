# JadwAI

A fresh implementation of the AI-assisted university timetabling project, started on 15 October 2026. JadwAI combines jadwal (جدول, timetable) with AI. JAI (pronounced “jay”) is the assistant identity. The interface uses warm ivory, forest green, and soft botanical colors, with English/Arabic layouts and responsive navigation.

## Current working milestone

- React/TypeScript frontend and FastAPI API, with an isolated PostgreSQL database.
- Local sign-in using hashed passwords and opaque, expiring, HttpOnly sessions. Administrator writes and read-only viewer policy.
- Add, edit, filter, and remove instructors, rooms, groups, and teaching activities.
- Separate lecture/tutorial/lab activities, each with eligible instructors and student groups.
- Structured instructor unavailability and preferred teaching periods; explicit approval and revocation.
- Serialized, version-checked writes, linked-record deletion protection, and transactional audit events.
- Alembic migrations, an idempotent synthetic seed, and a separate schedule-generation/maintenance worker.

The local Phase 2 foundation is implemented and verified, and the Phase 3 academic data foundation includes relational tables, configurable semester settings, and atomic CSV imports. This is not completion of the full specification. A bounded CP-SAT draft generator and separate validation of supported constraints are implemented. Complete mandatory-rule coverage, AI extraction, scenario comparison, publication and research evaluation remain unfinished. The overview calendar is a labelled illustration; all counts and records come from PostgreSQL.

## Realistic timetables, typed constraints and publishing — 4 November 2026

The owner's target: the administrator builds a teaching or exam timetable that satisfies every rule and is as convenient as possible; constraints can be typed in plain text; instructors and students see only their own published schedule.

- **Doctors and TAs.** Each instructor is a Doctor (teaches lectures) or a TA (teaches tutorials and labs). Course setup, activities, input checks, the solver and the validator all enforce this strictly. Instructors saved before this change stay unclassified (a warning) until edited. Every TA must teach at least one session: the solver and validator enforce it, and Check inputs names any TA who cannot be given one.
- **Special rooms.** Room *features* (for example `Data Science Lab`, `Workshop`, `GPU`) are matched against an activity's *required features*; only rooms with every required feature are used. The rule *Activity must use these rooms* pins an activity to specific rooms.
- **Realistic sessions.** A session may span consecutive named periods whose teaching minutes add up to its duration (a 3-hour lab over two 90-minute periods); breaks of up to 30 minutes stay inside the session. Rules accept half-hour times and *Every day*.
- **New rule types:** activity must use these rooms; activities on different days; instructor or student-group daily hour limit; instructor teaching days per week.
- **Most convenient timetable.** The default scoring profile `convenience-v1` minimises, in weighted order: missed instructor preferences, two sessions of one activity on the same day, student gaps, instructor gaps, student and instructor days on campus, the busiest day per group, teaching beyond 4.5 hours in a day, sessions in the first or last period, and uneven instructor workload (a stepped cost above 3, 6 and 12 weekly hours). Every term is recounted independently by the worker before a draft is kept. Search starts from a quick valid timetable (warm start); Search settings default to 30 seconds and 4 CPU workers, or 240 seconds and 8 workers above 150 weekly sessions (limits: 300 s and 8). Fine 30-minute grids need more time than named periods.
- **Type a constraint.** Constraints → *Type a constraint* accepts English, Arabic or mixed text, for example “Dr. Ahmed Hassan can’t teach on Sunday before 10:30” or “No classes for year 1 on Thursday after 2pm”. A built-in parser interprets it offline; ambiguous names or missing details become clarification questions. When `JADWAI_AI_ENABLED=true` and `OPENAI_API_KEY` are set, *Ask GPT* handles what the parser cannot. Every interpretation becomes draft rules that still need approval. Limitation: the parser cannot match an Arabic-script name to a record stored in Latin letters (use the name as stored, or GPT).
- **Scenarios.** Drafts can be named, compared (moved sessions and convenience metrics side by side), and edited by moving one session; an edit is saved as a new draft only if the independent validator passes.
- **Publishing.** *Publish* re-validates a draft against the current approved inputs and refuses stale drafts. Exactly one teaching timetable and one exam timetable can be published.
- **Instructor and student portals.** Accounts with the *Instructor* role are linked to an instructor; students to a group. They see only the published timetable: their own sessions, their exams (students) or invigilation duties (TAs), and can download them as CSV.
- **Exams.** Each exam gets one or more rooms marked *Exam hall* whose capacity covers its students (group sizes, or *Expected students* on the course), and a free TA invigilator per hall (day off and approved unavailability respected). The planner avoids exams for one cohort on consecutive days. The list of shared core programmes is editable (`/api/exam-schedules/cohort-rules`).

- **Exam convenience.** The exam solver merges student groups that sit the same exams, places dates and slots first (seats and halls per slot), then assigns halls slot by slot. It reports back-to-back exam days, two exams on one day, and how many back-to-back days the chosen dates make unavoidable, with advice to add dates or allow another exam per day. All 203 demo courses (every faculty) reach that floor in the default 20 seconds.
- **Advising students.** Students whose courses differ from their group's (retakes, drops, another group's sections, electives from another programme) are kept under Academic data → Student groups → **Advising students**. Each one keeps their group's sessions minus dropped courses, plus the added courses' sessions with the chosen group. None of a student's sessions may overlap (hard rule in solver and validator), joining students count toward room seats, and each student is an exam cohort: never two exams at once, and the daily maximum gives way only when their courses cannot be spread further, in which case the result names them. A student account can follow an advising student instead of a group. `scripts/load_advising_demo.py` adds 60 invented ones to a demo database; on the university demo, ignoring them would leave 24 of 60 with clashing sessions.
- **University-scale demo.** `scripts/load_university_demo.py` loads a multi-faculty semester (448 weekly sessions, 93 tutorial/lab groups, 35 courses) through the API, structured after `GIU-WINTER 26-schedule-V7.xlsx` and the Winter 2026 midterm schedule. Room capacities and types, staff names, group sizes and days off are placeholders. Use it only on a separate demo database. At this size allow about 4 minutes and 8 workers. `app.provision` writes the URLs it is given into `.env`, so restore `.env` after provisioning any other database.
- **Room pooling.** Rooms with the same capacity, types and features that no rule or lock names are treated as one pool by the solver; concrete rooms are assigned afterwards. This is what makes hundreds of sessions tractable.

After updating, apply migrations 0027–0029 with `bash scripts/setup.sh` (it also re-provisions database roles), then generate new drafts.

## Run

Requirements: Python 3.14, Node.js 22+, Docker with Compose. The first setup downloads dependencies.

```sh
cd ~/Downloads/jadwai
bash scripts/setup.sh
bash scripts/dev.sh
```

Open http://127.0.0.1:5180. Initially sign in using `JADWAI_ADMIN_EMAIL` and `JADWAI_ADMIN_PASSWORD` in the generated, ignored `.env` file. Setup creates a random local password and never changes an existing account. API documentation is at http://127.0.0.1:8010/docs. Database port: 5440. The new container and named volume use the Compose project name `mizan`.

Use Ctrl+C in the development terminal to stop the frontend, API, and worker. `docker compose -p mizan stop` stops the database while retaining records.

## Verify

```sh
bash scripts/check.sh
```

Integration tests use disposable schemas in JadwAI's PostgreSQL database; they never reset the demo workspace. The test role must be allowed to create schemas. Frontend tests check version transport and error handling; the production build type-checks the interface. Browser verification is recorded separately in `docs/VERIFICATION.md`.

## Project map

- `docs/ROADMAP.md`: nine phases, deliverables, dependencies, acceptance criteria, and remaining tasks.
- `docs/DECISIONS.md`: approved scope, starter assumptions, unresolved choices, and source precedence.
- `docs/BRAND.md`: JadwAI naming, JAI's identity and tone, current guide behavior, and storage compatibility notes.
- `backend/app`: database models, API, validation schemas, local authentication, synthetic seed.
- `backend/migrations`: frozen, versioned schema migrations.
- `frontend/src`: UI, API client, translation catalog, and visual design.
- `worker`: background schedule generation and session maintenance.

The new project is built independently. Claude's repository and the existing specifications have not been edited or imported as application code.

## Accounts and recovery

Administrators can add accounts, change names/roles, activate or deactivate accounts, and end sessions. New accounts and administrator-assisted password resets produce a one-time link; copy it from the dialog and give it directly to the account owner. Links expire in 30 minutes. No email is sent. Users set/change passwords with at least 15 characters. The initial password in `.env` is a bootstrap value; it is not automatically changed when a user changes their password.

At least one active administrator is required. Changes to role/activation immediately revoke existing sessions. Session expiry preserves an open form in memory until reauthentication; reloading or closing the browser discards that in-memory draft.

## Data and CSV imports

Use **Semester settings** to edit the term, optional paired dates, timezone, teaching week/hours, and period length. Settings changes that exclude an existing rule or conflict with an activity duration are rejected.

Under **Academic data**, choose a category, then **Import CSV**. The dialog shows exact headers. Activity imports resolve existing instructor and group codes. Separate multiple codes/equipment names with `|`. Limits: 500 rows and 1 MB. Preview is read-only; commit revalidates every row against the preview version and writes either all rows or none.

### Real data from the Winter 2026 workbook

1. `cd backend && .venv/bin/python ../scripts/make_data_template.py` writes `data-entry/JadwAI-data-template.xlsx` from the imported workbook data: every room, group (programme, semester, stream, group number) and course is already listed. `data-entry/` is git-ignored.
2. Fill the yellow cells: room capacities and uses, staff (code, name, position `doctor`/`ta`, day off), group sizes, and per course the weekly lectures/tutorials/labs, minutes, doctors, TAs and room features. Row 2 of each sheet is an example and is skipped.
3. Check it (read-only): `.venv/bin/python ../scripts/import_data_template.py ../data-entry/JadwAI-data-template.xlsx`. Every problem is listed with its sheet and row, including TAs who teach nothing.
4. Import it: add `--commit`. The importer signs in with `JADWAI_EMAIL`/`JADWAI_PASSWORD` (`JADWAI_URL` defaults to the live API on port 8010), writes a JSON backup to `backups/` first, then creates or updates records by code.

The full university is about 2,700 weekly sessions, more than the solver's 600-session limit per run; generate per faculty.

## Runtime database separation

Setup keeps `DATABASE_ADMIN_URL` for migrations and provisioning, and creates separate `DATABASE_URL` and `WORKER_DATABASE_URL` credentials for restricted runtime roles. The API may append audit events but cannot alter/delete them or create schema objects. The worker may write its heartbeat and clean expired credentials; it cannot modify academic inputs. Normal development processes omit migration-owner and bootstrap-password credentials.

## Local deployment bundle

`ops/` contains API/worker and static-web Dockerfiles plus a Caddy same-origin reverse proxy. To build/run a local container preview after setup:

```sh
bash scripts/container-env.sh
docker compose -p mizan -f compose.yaml -f compose.app.yaml up --build -d
```

Open http://127.0.0.1:8080. The configuration binds only to loopback and is validated, but the images have not yet been built/tested in this milestone. For a real HTTPS deployment, configure the TLS endpoint and set `JADWAI_COOKIE_SECURE=true`; do not expose the development server as a production server. The GitHub Actions definition is prepared for a standalone repository rooted in this folder; no GitHub destination or remote run is configured yet.

## Remaining scope

The parent-course/component hierarchy, full manual constraint vocabulary, immutable rule replacement history, contradiction/data-sufficiency reports, scheduling, independent validation, AI extraction, publication/scenarios, and research evaluation are still to be completed. Teaching-load units remain an owner decision. No paid AI calls are authorized or implemented. JAI remains a guided workspace companion.


## Generate a draft timetable

Run the local stack with `bash scripts/dev.sh`, sign in as an administrator, and open **Timetable → Generate schedule**. The separate worker assigns eligible instructors, times and suitable rooms from a saved snapshot of current academic data and approved rules. Review the weekly cards, filter by group, or select a saved draft. Input changes flag older drafts as stale. Only one run is active at a time; cancellation and refresh preserve saved runs.

Generation uses OR-Tools CP-SAT and a separate validator for supported constraints. It is a draft feature: configured weekly workload, practical-day policies and approved assignment locks are supported; publication is unavailable. Read `docs/VERIFICATION.md` for scoring, size/search limits and evidence. After updating an existing checkout, apply migrations through 0015 as the database owner and rerun `python -m app.provision` before starting the API/worker; `bash scripts/setup.sh` performs those steps using the saved owner URL.

## Large synthetic demo data

The local workspace contains an additional labelled `[Demo]` / `LOAD-` batch: 24 instructors, 18 rooms, 18 student groups, 60 activities (90 weekly sessions), and 24 approved instructor availability/preference rules. Existing records are preserved. A pre-load academic-input backup is in the ignored `backups/` directory.

The additive loader is `backend/app/stress_seed.py` (`python -m app.stress_seed` after loading `.env` from the project root). It uses the configured administrator, respects the current calendar, validates references, commits atomically and does not duplicate or overwrite a fully loaded batch. Do not use this synthetic dataset as institutional or research evaluation data.

## Student groups

Student groups are organised as **Study year → Major → Group** in Academic data. Add/edit a group to set its year, major and size. Existing groups with missing classification remain visible under Unassigned year/major. CSV columns are `name,code,size,year,major`; the legacy three-column format still works. The timetable provides cascading year/major/group filters from its saved input snapshot. Generate a new draft after classification changes to use the updated hierarchy.

## Save a schedule as PDF

Open a completed draft under Timetable, choose any year/major/group filters, then click **Save as PDF** beside the validation badge. In the system print dialog, select **Save as PDF**. The dedicated A4 landscape print view contains only matching sessions in a weekly grid with days on the left, configured time slots across the top, duration-spanning session blocks and Free cells for empty periods; it repeats table headings across pages, and includes department/term, input version, timezone, filter scope, draft reference and publication limitations. Stale snapshots carry an outdated-draft warning. English and Arabic/RTL are supported. Exporting a draft does not publish it.

## Optional PDF schedule report

Each completed, validated generation stores versioned statistics with its saved inputs. Nothing downloads automatically. Choose **Download report PDF** for a one-page summary with charts for daily sessions, applicable preference satisfaction and resource use, plus coverage, supported checks and overlap counts. Reports cover the full saved schedule, independently of display filters, and identify stale inputs and draft/publication limitations. The administrator API still accepts explicit HTML/JSON formats for compatibility.

Metrics include assignment coverage; room/instructor/group overlap-pair counts; applicable and satisfied preferred-period sessions; fully/partially/unsatisfied/not-applicable preference rules; room-time utilization excluding breaks; duration-weighted occupied-room seat usage; daily session distribution; room/instructor/group teaching-minute totals; solver time and optimality for the implemented objective. Definitions are included in the file. No single undefined efficiency score is claimed, and unassigned instructors' preferences are not counted as satisfied. Configured workload, daily policy and approved lock checks are recorded in each newly generated draft; historical reports retain their saved coverage.

## Resource availability (25 October 2026)

Manual constraints now include instructor, room and student-group unavailable intervals, plus preferred instructor periods. Room/group closures are mandatory, start as drafts, require approval, and are enforced by both the solver and independent validator. To apply a newly approved rule, generate a new draft; existing timetables remain unchanged. Instructor workload uses a 12-hour standard week: hours above 12 are reported as extra time and never block generation (a 90-minute session is 1.5 hours). Per-instructor `max_weekly_hours` values are kept for compatibility and still accepted in CSV, but generation and validation do not enforce them while this overtime policy is active. Configurable hard daily limits and practical-day policies are implemented.

## Practical daily timetables

Semester settings → Daily timetable quality controls the named-period policy. The current demo uses student/instructor daily maxima of 6 teaching hours, at most 3 consecutive teaching periods, at most 1 internal idle teaching period per day, and different days for occurrences of the same activity. Gap minimisation follows instructor time preferences. These are editable demo settings, not approved university policy. Breaks between named periods are excluded from teaching-hour/gap counts. Changes invalidate earlier drafts; generate a new timetable. Published use still requires real curriculum, cohort and eligibility data plus institutional review.

### Keep selected assignments fixed
On a validated generated session, choose **Keep fixed**, select instructor, day/time and/or room, then **Save draft lock**. Approve it under **Constraints → Assignment locks** and generate a new timetable. Draft locks are ignored. Instructor locks apply to every weekly occurrence of the activity for continuity. Approved locks can be revoked; revoke before removing. References are rechecked against current inputs and contradictory constraints may make a new solve infeasible. Existing drafts are never changed.

### Generation evidence — 25 October
New drafts retain canonical input/configuration SHA-256 fingerprints, fixed solver profile, OR-Tools version, explicit parameter text, raw solver outcome, objective identifier, worker elapsed time and independent-validator version. The worker refuses mismatched fingerprints. Expand **How this draft was generated** under Timetable to inspect details; historical drafts are not retroactively credited with this evidence. Parallel search can produce different valid schedules with identical inputs/seed. These hashes do not authenticate a source or capture the full execution environment. Phase 4 was accepted locally on 25 October and revalidated on 1 November; Phase 5 is active.

### Phase 4 manual baseline
Use **Check inputs** before generating. Blocking defects identify affected activities/resources and rule IDs; missing optional workload maxima are warnings. Passing local checks does not prove global feasibility. New runs always repeat input checks in the worker.

Under **Search settings**, choose a 1–60 second bound, seed, 1–4 workers and either preferences-first or weighted preference/idle-period scoring. Idle minimisation requires Compact days in semester settings. Historical input reruns are an explicit checkbox and remain stale if the input version differs from the current workspace. The worker independently cross-checks all supported hard rules, each implemented objective component and the total objective before retaining a completed draft.

Manual rules now include **Activity permitted window** and **Student group permitted window**. For one target, approved windows are weekly alternatives (days without a window are excluded); each session must fit one complete window. Different activity/group targets apply together. Rules start as drafts and require approval.

**Validation coverage** shows evaluated counts, skipped optional limits and detailed violations. **How this draft was generated** retains hashes, settings and execution metadata. Cancellation discards candidates; automatic retry limit is zero. Publication and advanced proposed constraint variants remain unavailable. See `docs/PHASE4_ACCEPTANCE.md` for baseline acceptance and remaining project scope.

### Phase 5 evaluation materials
`evaluation/` contains a reproducible **synthetic draft** corpus (128 examples, four language categories), annotation guide, output schema and offline scorer. Run `backend/.venv/bin/python -m unittest discover -s evaluation/tests -v` and read `evaluation/README.md` for exports/scoring commands. Expected labels are not independently reviewed. The reserved split is not blind, and no real model-performance results are included. The scorer makes no model calls or website changes.

### Room uses
Rooms support multiple selected uses: Lecture, Laboratory, Flexible and Exam hall. At least one is required. Existing room types are preserved. Course scheduling accepts a matching Lecture/Laboratory use or Flexible; Exam hall alone does not qualify for teaching. CSV keeps the `room_type` header and accepts `lecture|exam_hall`, for example.

### Instructor day off
The instructor form requires one weekly day off, respected as a mandatory restriction by generation and independent validation. Existing instructors remain unspecified until edited. CSV optionally accepts a `day_off` column with an English weekday name. Generate a new draft after changing it; saved schedules retain their original inputs.

### Courses and activity eligibility
Teaching Activities → Course setup defines course names/codes, eligible instructors separately for lectures/tutorials/labs, and eligible student groups. Add a teaching activity by choosing its course, then type. Only matching instructors and course groups appear. Changing the course clears both selections; changing type clears instructors. The server rejects assignments outside the course configuration. Course configuration cannot remove eligibility still used by an activity. Existing activities are linked by their exact name (ignoring case/outer whitespace), with the union of their existing eligibility; review these synthetic configurations before real use. Legacy CSV/API activity inputs remain supported without a parent course; new website activities require a course. Saved timetable snapshots remain unchanged.

### Standard teaching load and Saturday — 30 October 2026
New timetables use 12 teaching hours per instructor per week as the standard load. Additional teaching is permitted and reported as extra time (e.g. 13.5 total = 12 regular + 1.5 extra). This replaces individual weekly hard caps for new runs; historical snapshots retain their saved rules. Daily limits, eligibility and individual days off still apply. The saved calendar now includes Saturday through Thursday. Regenerate to use the new calendar and policy.

### Demo cleanup — 30 October 2026
The live workspace's synthetic starter and stress-test batches were removed after a local backup: 134 academic records, 64 derived course entries, 26 linked rules and 24 generated timetables. Three separately added academic records and all accounts were preserved. Previous sections describing demo counts are historical. Setup leaves an existing workspace unchanged; it does not reload these examples. Student accounts whose demo group was removed need a new group assignment before use.


### Source course catalogue — 30 October 2026
Course setup contains 127 distinct course codes and their names extracted from the supplied GIU PDF. Each course retains source program/semester labels, page references and course-name variants as metadata. No exam dates, times, exam records or exam-schedule interface were added. Broad program labels do not create student groups or establish teaching eligibility. Set the eligible instructors for each component and actual student groups before adding teaching activities. Existing manual academic records and settings are preserved.

### Rooms from Winter 2026 workbook — 30 October 2026
Added 63 distinct room identifiers from the six explicitly named Winter 2026 weekday sheets of GIU-WINTER 26-schedule-V7.xlsx. Each retains source sheet/cell references. Eighteen additional identifiers found only in older/other schedule tabs remain in the extraction file and were not imported. Room-count totals, tutorial group numbers and vague ROOM/PT room references were excluded. Capacities and confirmed types were absent, so imported rooms display these as unset. Complete both fields under Rooms → Edit before using them in generation. Solver, preflight, independent validator and room-time statistics exclude incomplete rooms. Existing manual rooms were preserved.

### Exam timetable drafts — 30 October 2026
Timetable now has separate Teaching timetable and Exam timetable modes. The exam planner defaults to the supplied PDF's 20–31 October 2026 period, excluding Fridays, with three two-hour slots (09:00–11:00, 11:15–13:15, 13:30–15:30). It schedules one shared exam per course catalogue entry and defaults to at most one exam per program/semester or configured group per day. Date range, Friday exclusion and the daily maximum can be changed. Saved draft inputs and independent validation are retained; CSV downloads include a draft label. Search balances the largest number of simultaneous exams, without claiming room feasibility.

Conflict membership is derived from source program/semester labels and any actual course group IDs. General/core programs include known specializations in that faculty/semester; engineering program spelling prefixes are normalized. A source course with an unspecified semester conflicts conservatively with known semesters of that same program; known semesters remain distinct. Missing all cohort information blocks generation. The generator does not use the PDF's original exam assignments, infer individual enrolments, assign rooms/invigilators, or claim institutional acceptance. Room capacity, individual-student conflicts, staff availability, accessibility arrangements and institutional exam rules need separate verification before use. User authorization to generate an exam schedule expands the earlier course-only scope.

### Current phase — 1 November 2026
Phase 4 is complete for the agreed weekly manual baseline, with regression revalidation, exact-fixed-assignment solver/validator cross-checks and an offline scale CSV. Phase 5 is in progress: the offline harness now adds family-clustered uncertainty, immutable material versions, frozen-configuration checks and reserved-attempt logging. Independent annotation, a second institutional context and fresh confirmatory data remain. See `docs/PHASE4_REVALIDATION_2026-11-01.md` and `evaluation/PHASE5_STATUS.md`. Imported teaching-source blocks remain review data; no synthetic benchmark entries are added to the live website.

Phase 5 development continuation: `evaluation/development-v2/` adds the second fictional institution, bringing development material to 144 items in 36 families. `evaluation/development.py` validates the bundle and supports gold-free review exports, separate annotation imports, agreement, adjudication records and lexical fingerprint screens. `output/phase5-review-pack-v2.json` contains a 24-item sample spanning both contexts. No actual human annotations or model results are claimed.

### Evaluation workspace — 1 November 2026
Administrators can open **Evaluation** in the sidebar to inspect the current development bundle, download the gold-free 24-statement review pack and annotation guide, and upload completed review JSON files under pseudonymous reviewer IDs. The server validates the entire pack against source text, context, dataset version, supported output semantics and nonempty rationales before saving a separate append-only review record. Duplicate retries reuse the same record; conflicting payloads are rejected. Review exports work with the offline agreement/adjudication tools. Submitted identities and reviewer independence are operator-declared; no automatic human review, gold promotion, model-performance finding or Phase 5 completion is implied. Viewers/students cannot access the research endpoints. The production image includes development-only evaluation material; reserved files are excluded. The updated image recipe has not been built or deployed in this milestone.

Evaluation now includes saved-review comparison and JSON report downloads. Choose two reviews of the same pack under different reviewer IDs to inspect decision agreement, Cohen's kappa, semantic matches and side-by-side disagreements. The current live dataset has no human review submissions; fabricated demonstration reviews are not inserted. Agreement does not establish correctness, and research sign-off remains pending.

Evaluation comparison now supports recording adjudication decisions in the website: select submitted or custom interpretations, provide a rationale per disagreement and a distinct declared adjudicator ID, then save an immutable decision record. Saved history and JSON exports preserve both source reviews. Runtime privileges and database triggers prevent rewriting adjudication history. This does not promote draft labels or establish independent human review. Live synthetic adjudication records are not inserted during verification; UI preview fixtures are isolated and cannot submit.

Evaluation now supports the current gold-free review pack directly in the browser: statement navigation, context-only manual rule builders, decisions/codes/rationales, completion tracking and server-validated submission. No answers are preselected. In-memory drafts survive internal navigation, are account-scoped and clear on sign-out; refreshing/closing clears unsaved work. File import remains available. The form does not perform AI extraction or create operational scheduling constraints.

### Phase 5 review protocol — owner decision, 1 November 2026
The administrator will provide the human annotation review. The Evaluation page now uses the single-admin protocol, makes additional-review comparison/adjudication optional, and records that protocol on new submissions. State the single-annotator limitation in thesis reporting. No real reviews are supplied by implementation tests. Future-source `evaluation/dataset_lifecycle.py` provides deterministic whole-family splits and technical sealing/access checks; it does not promote the existing exposed draft material or certify blindness.

### GPT-5.4 mini interpretation

The administrator Proposal review page can send a requirement to the selected GPT-5.4 mini adapter and retain the result as an unapproved proposal. Calls default to disabled. Configure `OPENAI_API_KEY` in the server environment and set `JADWAI_AI_ENABLED=true` only when ready to use the API account; restart the backend afterward. Never use a `VITE_` credential variable. Local development removes the key from the frontend and schedule-worker environments. The configuration endpoint reports whether configuration is present; it does not validate credit, model access or API connectivity.

Request keys prevent replayed clicks from issuing another model call. Failed/abandoned requests do not retry automatically. A running job can be found at `/api/model-calls/by-key/{request_key}` and cancelled at `/api/model-calls/{id}/cancel`; cancellation blocks result acceptance and cannot promise reversal of provider processing or charges. Every accepted interpretation still needs administrator review and separate rule approval.
