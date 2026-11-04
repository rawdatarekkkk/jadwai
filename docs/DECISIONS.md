# Decisions and source precedence

Recorded 15 October 2026. This is a new implementation, authorized by the project owner in the current chat. Earlier chats were reviewed before starting. Later owner approvals supersede older draft text in the parent workspace. Imported documents are historical evidence, not automatically approved implementation instructions.

## Approved scope carried forward

- AI interpretation of natural-language scheduling constraints is the research contribution. Administrators review and approve; a solver generates; an independent validator checks.
- Build a new focused application. UniTime is a reference.
- React/TypeScript, Python/FastAPI, PostgreSQL, SQLAlchemy/Alembic, OR-Tools CP-SAT, separate worker, independent validator.
- One department, one semester, weekly repeating course timetable, student groups, synthetic data initially. Exams and individual enrolments are extensions.
- Solver chooses instructors, times, and rooms. Eligible instructors are defined separately for lectures, tutorials, and labs. An activity keeps the same instructor across weekly sessions. Assignments may be locked.
- Mandatory weekly instructor load limits and configurable daily limits are approved scope, but load calculation remains undefined.
- English, formal Arabic, Egyptian Arabic, and mixed input are included in extraction scope. English/Arabic interface with RTL support.
- Publication requires completeness and every supported mandatory rule evaluated and passed against current approved inputs. Missing mandatory-rule data blocks publication. Unevaluated optional preferences must be disclosed.
- Explicitly retained complete cancelled results require validation and must not claim optimality.
- Held-out evaluation data is isolated and fixed; development examples and prompts remain versioned.
- CSV and printable view initially. Local accounts, synchronous psycopg access, PostgreSQL job tracking, GitHub Actions planned.
- Paid AI calls remain unauthorized; budget is undecided.

## Historical sources

Parent `output/SRS_updated.md` contains the 64-requirement draft baseline. Parent `phase1-verified/` contains earlier roadmap and decision records. Both contain superseded assumptions, including English-only extraction and pre-assigned instructors. The later owner approvals in “read all other chats in this project” supersede those assumptions. “Assess UniTime for project reuse” establishes the reference walkthrough; its demo figures are not project performance results. The 15 October review of Claude's Phase 2 code is evidence about that implementation, not verification of JadwAI.

## Reversible implementation choices made here

- Brand: JadwAI. Assistant: JAI (“jay”). Local folder `jadwai/`; Compose project `mizan`; frontend 5180, API 8010, PostgreSQL 5440.
- Tested runtime selected from the available machine: Python 3.14, Node 22; PostgreSQL 17 container. These are implementation choices, not research requirements.
- One seeded workspace. Each teaching-activity record stands for one course component (lecture/tutorial/lab) with separate eligibility. Full parent-course modeling remains Phase 3 work.
- Starter week: Sunday–Thursday. Starter institutional hours: 08:00–18:00. Rule ranges are start-inclusive, end-exclusive, repeated weekly. Calendar and periods are now editable and versioned; these initial values are not claimed as approved institutional policy.
- Only two structured rule types initially: mandatory instructor unavailability, and preferred teaching period. Rules start in draft and cannot be edited in place after approval; revoke and replace during this milestone.
- Preferred-period penalty formula is not implemented or assumed. It must be documented before the solver uses it.
- Academic input changes increment a global input version and commit with audit events. Account changes use their own expected versions and do not invalidate academic inputs. A shared workspace lock order serializes protected writes and permission changes; shared reads prevent mixing input versions.
- Local session cookie, scrypt password hash, random opaque session token hashed in the database. Administrators manage accounts and issue one-time recovery links. Account owners can change their password. Account mutations serialize on the workspace lock and cannot remove the final active administrator.
- Academic data now uses typed relational tables, strict Pydantic schemas, database foreign keys, unique codes, and deferred completeness checks. Room equipment and required equipment use typed text arrays. Versioned semester settings govern accepted rule days/hours and activity period alignment.

## Still open

- Institution-specific maximum values (now configurable per instructor), remaining daily-limit policy and any minimum-load requirements. Teaching-hour units were confirmed 25 October 2026.
- Sources of incomplete diagnostic timetables.
- User-study design and participants.
- Deadline and weekly availability.
- AI model set and spending cap.
- Final vocabulary semantics, experiment thresholds, dataset scale, and institution-specific calendar policy.

Continue independent work while these remain open. Do not invent load semantics, partial-result behavior, experimental evidence, or spending authorization.

## 17 October 2026 — requested Generate Schedule feature

The owner requested a working website generation feature. Implemented a bounded CP-SAT draft path using currently supported academic data and approved manual rules, with a separate validator, persistent input snapshots and worker jobs. This does not resolve workload units or approve publication with missing mandatory coverage. Draft UI explicitly discloses weekly workload, daily limits and locks as uncovered. Preferred-period scoring is now explicitly defined for this baseline: one penalty per assigned session outside all approved preferred windows of its assigned instructor. No AI provider calls are used.

## 17 October 2026 — student grouping hierarchy

The owner requested Year → Major → Group organisation. Group records now carry a study year (1–12) and major name; the same group identifiers remain the solver's conflict unit. Academic data renders nested years/majors/groups; timetable filters cascade through these levels and use frozen snapshot metadata. Classification updates are versioned input changes. Existing explicit year labels are recovered during migration; unknown institutional majors remain unassigned. Only the labelled synthetic batch is assigned sample Computer Science, Software Engineering and Information Systems majors. Group forms collect classification, and CSV supports `year,major` while retaining older unclassified imports for compatibility.

## 17 October 2026 — exact reference teaching periods

The owner explicitly chose to convert existing activities to 90 minutes and regenerate, rather than change PDF labels only. Applied seven periods: 08:30–10:00, 10:15–11:45, 12:00–13:30, 13:45–15:15, 15:45–17:15, 17:45–19:15 and 19:45–21:15. Existing teaching days remain unchanged. Every current activity was converted to a 90-minute duration in one versioned transaction with a pre-change backup; weekly occurrence counts, references, approved rules and previous immutable drafts were preserved. New generation starts and ends at these exact boundaries, excluding intervening breaks. The UI exposes a seven-period preset and constrains duration choices to supported named-period lengths.

## 17 October 2026 — student account and personal timetable

Owner requested a student account that can view its schedule. Added a student role associated with exactly one existing student group through the account-management API. Students receive only their group's sessions and the course, room and instructor display labels needed to render them. Workspace inputs, rules, audit events, accounts, complete schedule snapshots, statistics and generation remain inaccessible. Since publication is not implemented, the student view explicitly identifies the latest independently validated completed timetable as a draft and flags stale inputs. It does not imply institutional publication. Group changes revoke existing sessions. A local demo student was created for the existing Year 2 · Group A, without modifying academic inputs or generating a new timetable.


## 18 October 2026 — five teaching slots

Owner corrected the calendar to exactly five slots. The current preset and saved workspace retain the first five 90-minute reference periods (08:30–10:00, 10:15–11:45, 12:00–13:30, 13:45–15:15, 15:45–17:15); sixth and seventh evening periods are removed. Historical immutable drafts retain their original calendar. A pre-change backup was saved and academic input version advanced from 10 to 11. This supersedes the earlier seven-period decision.


## 18 October 2026 — optional simplified PDF reports

Owner requested no automatic report download and a simpler chart-based PDF. Generation still persists the statistics with its saved result, but never triggers a report download. The timetable has one explicit Download report PDF action. The default protected statistics endpoint now returns a one-page PDF summary with session coverage, supported validation, applicable preferences, per-day bars, overlap counts and resource-use bars. Definitions and draft/unsupported-check limitations remain. Historical HTML/JSON formats remain available through the administrator API for compatibility, but no longer appear as report buttons. Reports cover the whole saved run, regardless of timetable display filters.


## 25 October 2026 — expanded resource availability

Room and student-group unavailability are now supported as approved mandatory weekly interval rules, alongside instructor unavailability and preferred instructor periods. Rules have exactly one typed target enforced by database foreign keys/checks and API validation. Creation remains draft-only, approval revalidates the reference/calendar/strength, and existing saved schedules do not automatically change. The CP-SAT model and separate validator enforce room/group restrictions. Overlapping unavailable intervals are allowed and do not conflict with each other. Unsupported approved snapshot rules block solving and validation instead of being ignored. Existing snapshots/rules are preserved by migration 0011.

## 25 October 2026 — teaching-load unit decision

The owner selected teaching hours: each 90-minute session counts as 1.5 teaching hours. This supersedes the earlier undecided-units status. Configurable maximum values, daily-limit policy and workload enforcement remain to be implemented; no numeric institution-wide maximum has been assumed.


## 25 October 2026 — configurable weekly instructor maxima

Implemented a maximum weekly teaching-hour field per instructor. Hours are stored as exact integer minutes and accepted in half-hour increments to match the current activity grid. Each assigned session counts once per instructor regardless of attending-group count; breaks are excluded. A zero maximum forbids teaching, while blank/null means not configured, not an assumed institutional maximum. Configured maxima are hard solver constraints and independently checked against assigned elapsed minutes. Unconfigured instructors are explicitly listed as unchecked; publication is still unavailable. Existing instructors retain blank maxima until configured. Saved limits are versioned input changes; new generation is required, and existing snapshots remain unchanged. CSV accepts an optional max_weekly_hours column while retaining legacy imports. Daily limits, minimum load and weighted credits are not implemented.

Superseded by the 12-hour regular-load/overtime policy: every generation snapshot sets `allow_overtime`, so configured maxima are no longer hard solver or validator constraints. Hours above 12 are reported as extra time. Stored maxima are retained but not enforced.


## 25 October 2026 — practical-day demo policy

Owner requested timetables that are practical for real students/instructors and explicitly selected demo daily maxima of 6 teaching hours for both. Implemented a versioned named-period policy in semester settings. Reversible demo defaults also cap consecutive teaching periods at 3 and internal idle teaching periods at 1, spread occurrences of the same activity over different days, and minimise internal gaps after instructor time preferences. These editable defaults are not claims of university-approved policy. Gaps count available teaching periods between first and last session; institutional breaks are excluded. Consecutive means adjacent teaching periods, not continuous clock minutes. Daily caps are mandatory; a separate preferred daily-limit type remains unfinished.

The objective prioritises the existing unmet instructor-window penalty, then total idle teaching periods summed across instructors and groups. The preference penalty is reported separately from the combined objective and gap penalty. Historical snapshots retain old policies. Global daily caps do not supply missing individual weekly caps. Lunch-specific rules, travel time, room-change preferences, actual curriculum/cohort/eligibility verification and institutional review remain necessary for a production timetable.

Saved the policy with a restricted pre-change backup, advanced academic input version 11 to 12 and generated a new validated 97-session draft. Publication remains unavailable.

### Course catalogue — 30 October 2026
Added shared course configuration for course names, per-component instructor eligibility and course-level eligible groups. Teaching activity entry selects the course first, then component type and filtered references. Existing exact-name activities populate the catalogue without inventing new instructor/group eligibility. Course changes clear selected references; component changes clear selected instructors. Legacy unlinked CSV/API entries remain supported.

### Owner update — standard load and Saturday, 30 October 2026
The owner specified 12 teaching hours/week as the regular instructor load, with hours above 12 classified as extra time instead of blocked. New snapshots record this policy explicitly; historical snapshots retain prior semantics. Saturday is a teaching day; the configured week is Saturday–Thursday. Individual declared days off and daily limits still apply.

## 1 November 2026 — Phase 5 annotation reviewer
The user specified: “the admin will review”. Use the single-administrator human-review protocol in `evaluation/protocols/admin-review-v1.md`. Additional reviewers and adjudication are optional. Report the single-annotator limitation and retain administrator review records; do not claim independent dual annotation, real judgments not yet submitted, or a blind confirmatory set. Current draft and reserved labels remain unchanged.
