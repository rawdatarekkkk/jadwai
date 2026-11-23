# JadwAI — functional and non-functional requirements

Companion to the bachelor thesis *AI-Assisted University Timetabling Through Natural-Language Constraint Extraction* (JadwAI). Status as of **23 November 2026**.

- **Source.** Requirements are taken from the project's Software Requirements Specification (SRS) v0.4 of 18 November 2026, shortened to one sentence each. The full SRS defines inputs, outputs, error behaviour and acceptance criteria for every requirement.
- **Approval.** SRS v0.2 was reviewed by the supervisor; v0.3 and v0.4 carry the project owner's approval only.
- **Status** is the project owner's record of the prototype, not a supervisor acceptance or a research result:
  - **Implemented**: works in the prototype and is covered by automated tests.
  - **Partial**: a working subset exists; the note says what is missing.
  - **Not started**: no implementation.
- **Priority:** P1 is required for the core workflow, P2 supports it, P3 is an extension.

## Summary

| | Implemented | Partial | Not started | Total |
|---|---|---|---|---|
| Functional requirements | 55 | 17 | 6 | 78 |

## Functional requirements

| ID | Requirement | Priority | Summary | Status |
|---|---|---|---|---|
| FR-001 | Academic term and calendar | P1 | The system shall allow an administrator to create, edit and archive an academic term with name, start/end dates, teaching days, time zone and the department(s) in scope. | Partial — One term only; no multiple terms |
| FR-002 | Courses and scheduling activities | P1 | The system shall store courses (code, title, department) and one or more activities per course with type (lecture, tutorial, laboratory), duration in slots, number of weekly occurrences, associated st… | Partial — No separate parent courses and components |
| FR-003 | Instructors and availability | P1 | The system shall store instructors with a unique identifier, display name, aliases used for entity resolution (for example ‘Dr Ahmed’) and department. | Partial — No aliases or dated availability exceptions |
| FR-004 | Rooms, capacities and equipment | P1 | The system shall store rooms with identifier, name or alias, capacity, room type and a set of equipment tags, with unavailable intervals. | Implemented |
| FR-005 | Student groups | P1 | The system shall store student groups with identifier, name/alias, size, unavailable intervals (the term-data source of GROUP_UNAVAILABLE effects, S-07) and the activities each group attends. | Implemented — Year → Major → Group hierarchy |
| FR-006 | Instructor eligibility and assignment | P1 | The system shall let an administrator define, for each course, the set of eligible instructors separately for its lectures, its tutorials and its laboratories. | Implemented |
| FR-007 | Bulk import with atomic validation | P2 | The system shall import courses, activities, instructors, rooms, groups and availability from CSV files using a documented column specification. | Implemented — CSV import with validation |
| FR-008 | Referential and domain integrity | P1 | The system shall enforce referential integrity for all entities in the database. | Implemented |
| FR-009 | Supported constraint vocabulary and schema | P1 | The system shall define the supported constraint types (SRS §9) in a machine-readable, versioned schema (contracts/constraint.schema.json). | Partial — Supported rule types listed in the thesis; not every planned type |
| FR-010 | Manual constraint entry | P1 | The system shall provide a structured form for every supported constraint type that produces exactly the same constraint object as the AI route. | Implemented — Manual forms |
| FR-011 | Constraint lifecycle and versioning | P1 | The system shall give each constraint a lifecycle state: proposed, draft, approved, rejected, superseded, deactivated, needs-re-review. | Partial — Draft → approve → revoke; no supersession history |
| FR-012 | Hard/soft classification and weights | P1 | The system shall classify every constraint as hard or soft; | Partial — Weights fixed in code; no weight editing in the interface |
| FR-013 | Pre-solve consistency checks | P2 | The system shall detect direct contradictions among approved hard constraints (for example a lock on a time that the same instructor’s unavailability forbids) and report the constraints involved. | Partial — Input checks name blockers; not every contradiction |
| FR-014 | Submit natural-language requirement | P1 | The system shall accept a natural-language requirement of one or more sentences in English (initial language scope; | Implemented — Typed constraints and the JAI chat |
| FR-015 | Structured multi-rule proposal | P1 | The system shall request schema-constrained output from the LLM and shall return a proposal with zero or more proposed constraints, each with type, entity references, parameters, hard/soft status, a h… | Implemented |
| FR-016 | Entity resolution without invention | P1 | The system shall resolve each entity mention only to an identifier that exists in the term’s data. | Implemented |
| FR-017 | Parameters and institutional terms | P1 | The system shall extract explicit parameters (days, time intervals, durations, capacities, counts) with their units. | Partial — No institutional aliases |
| FR-018 | Negation, polarity and hard/soft classification | P1 | The system shall represent negation and polarity explicitly (for example ‘cannot’ → forbidden window; | Implemented |
| FR-019 | Ambiguity, missing-value, contradiction and unsupported-request handling | P1 | The system shall detect and report: missing values, ambiguous or unknown entities, unsupported rule types, contradictory statements within one submission, and statements that conflict with existing approved constraints. | Partial — Clarification and unsupported handling; quality not yet measured |
| FR-020 | Interpretation review interface | P1 | The system shall display the original statement beside each proposed rule, with every field editable, the source span highlighted, the interpretation in plain language, and resolution/provenance indicators. | Implemented — Proposal review beside the original text |
| FR-021 | Approval gate for the scheduling model | P1 | The system shall include in an input snapshot only constraints in state ‘approved’ (manual or AI-derived). | Implemented — Nothing reaches the solver unapproved |
| FR-022 | LLM adapter and failure handling | P1 | The system shall access LLM providers through an adapter interface with a shared extraction schema, so that providers can be swapped by configuration without changing review logic. | Implemented — Local Ollama adapter; GPT adapter built but disabled |
| FR-023 | Extraction audit and reproducibility record | P1 | The system shall record for each extraction: provider, model identifier, request date/time, prompt template version, schema version, decoding settings, context sent, raw response, parsed proposal, ret… | Partial — No complete audit export with cost |
| FR-024 | Immutable input snapshot | P1 | The system shall create, at generation time, an immutable snapshot of all scheduling-relevant data and approved constraints, the weight profile, the schema version and the solver settings, identified … | Implemented |
| FR-025 | Timetable generation job | P1 | The system shall run generation as a background job through a worker, not inside the web request. | Implemented |
| FR-026 | Job status and cancellation | P1 | The system shall expose job states QUEUED, RUNNING, FINISHED, FAILED, CANCELLED with timestamps. | Implemented |
| FR-027 | Solver outcome semantics | P1 | The system shall record one solver outcome per finished run: OPTIMAL, FEASIBLE, INFEASIBLE, UNKNOWN, MODEL_INVALID, or, for jobs that did not complete, FAILED or CANCELLED (SRS §11). | Implemented |
| FR-028 | Hard-constraint model | P1 | The solver model shall require every activity occurrence to be assigned a start time and room for its full duration within permitted windows. | Implemented |
| FR-029 | Soft objective and penalty reporting | P2 | The solver model shall minimise a weighted sum of soft-constraint penalties defined by a versioned objective definition. | Implemented |
| FR-030 | Pre-solve data sufficiency report | P2 | The system shall, at snapshot time, list which supported checks can be performed and which cannot because required data is absent (for example no groups, no instructor on an activity). | Implemented |
| FR-031 | Independent schedule validator | P1 | The system shall check every revision for completeness (every required occurrence assigned for its full duration). | Implemented |
| FR-032 | Validation coverage statement | P1 | The system shall display separate indicators for assignment completeness, supported hard-rule violations, soft penalties, and data/validation coverage. | Implemented |
| FR-033 | Validation of manual edits | P1 | The system shall mark a revision created by an edit as ‘unvalidated’ and shall run the validator on it. | Implemented |
| FR-034 | Scenario lifecycle and saving | P1 | The system shall let an administrator name a scenario, add notes, and retrieve it later. | Implemented — Named drafts |
| FR-035 | Stale-result detection | P1 | The system shall compare each scenario’s snapshot input version with the term’s current input version and shall display ‘Generated before the latest input change’ when they differ, listing the changes since. | Implemented |
| FR-036 | Scenario comparison | P1 | The system shall compare two scenario revisions and list, for each changed activity occurrence, the old and new day/time/room. | Implemented |
| FR-037 | Distinct scenarios by explicit variation | P2 | The system shall let the administrator create a scenario from a stated variation (a different weight profile, a different approved constraint set, a different seed, or a diversity requirement) and sha… | Not started |
| FR-038 | Manual timetable editing and locks | P1 | The system shall allow an authorised administrator to change the day, time or room of an activity occurrence, or the instructor of an activity (to another eligible instructor), in a draft revision, an… | Implemented — Moves and locks; each edit is a new validated draft |
| FR-039 | Edit-invalidates-validation rule | P1 | The system shall mark prior validation as not applicable to a revision created by an edit, and shall require re-validation before the scenario can reach VALIDATED. | Implemented |
| FR-040 | Publication gate | P1 | The system shall publish a revision only if: (a) validation was run on that exact revision and the term’s input version it was generated from is recorded; | Implemented |
| FR-041 | Published versions | P1 | The system shall keep each published timetable immutable and numbered per term. | Implemented |
| FR-042 | Timetable and agenda views | P1 | The system shall display published (and, for administrators, draft) timetables by student group, instructor, room and course, in a day/week view and an agenda view. | Implemented |
| FR-043 | Role-based visibility | P1 | The system shall show draft revisions and scenarios (including run results, validation reports and comparisons of unpublished scenarios) only to administrators; | Implemented |
| FR-044 | CSV export and run summary | P2 | The system shall export a revision’s assignments as CSV and a run summary (scenario name, input version, snapshot hash, approved-constraint changes since the previous run, coverage statement, outcome,… | Implemented |
| FR-045 | Printable view | P2 | The system shall provide a print-optimised view of any timetable view the user may access, including scenario/version identification, that the user can save as PDF through the browser's print function (v0.3: D-12; | Implemented |
| FR-046 | Requirement-to-publication trace | P1 | The system shall store and display the chain: original statement → extraction run → proposed rule → approved constraint version → input snapshot → solver run → scenario revision → validation report → publication. | Partial — Partial trace from rule to published timetable |
| FR-047 | Authentication and role-based access | P1 | The system shall authenticate users and assign roles (administrator, instructor, student, researcher). | Implemented — Local accounts; scrypt instead of Argon2id (deviation) |
| FR-048 | Audit log | P2 | The system shall log who did what and when for: constraint approval/rejection, data changes, job start/cancel, edits, publication, role changes. | Implemented — Transactional audit events |
| FR-049 | Extraction experiment harness | P1 | The system shall run a configured extraction experiment over a versioned dataset split with a stated provider, model, prompt version, schema version and repetition count. | Partial — Development bundle and scorer; no human annotations yet |
| FR-050 | Manual-versus-assisted task instrumentation | P2 | The system shall provide an experiment mode that assigns a task, records start/end time, number of edits/corrections and final constraint set for each condition (manual form, AI-assisted), without alt… | Not started — No participant study |
| FR-051 | Examination timetabling | P2 | The system shall support a separate exam calendar and exam durations, prevent mandatory student exam conflicts, enforce room capacity and allowed dates, and support configurable minimum s… | Implemented |
| FR-052 | Individual enrolments | P3 | The system shall import individual section enrolments, check student conflicts per student, and show personal timetables to students. | Partial — Covered in part by advising students (FR-070) |
| FR-053 | Minimal-change regeneration | P3 | The system shall regenerate a timetable with an objective term penalising differences from a chosen base revision. | Not started |
| FR-054 | Arabic and mixed-language extraction | P1 | The system shall accept requirement statements in English, formal Arabic, Egyptian Arabic and mixed Arabic/English through the same route as FR-014–FR-021, and shall store the statement verbatim, incl… | Partial — Built-in Arabic/Egyptian patterns and the local model; accuracy not measured |
| FR-055 | Calendar feed export | P3 | The system shall provide iCalendar feeds of published timetables restricted to the authorised user’s scope. | Not started |
| FR-056 | Schedule-change notifications | P3 | The system shall notify affected instructors and students when a new published version changes their entries. | Not started |
| FR-057 | Instructor availability submission | P3 | The system shall let instructors submit availability and preferences as proposals that enter the model only after administrator approval. | Not started |
| FR-058 | Solver-backed infeasibility explanation | P2 | The system shall, where the solver supports it, report a subset of constraints involved in infeasibility and shall state that the set is not necessarily minimal or complete. | Implemented |
| FR-059 | Concurrent changes and publication consistency | P1 | The system shall check the submitted resource version before a change and refuse a stale update without overwriting a newer change. | Partial — Version-checked writes, workspace lock |
| FR-060 | Interrupted operations and recovery | P1 | The system shall preserve acknowledged statements, committed drafts and recorded job identifiers. | Partial — Heartbeats and leases |
| FR-061 | Duplicate requests and retry control | P1 | The system shall recognise retries of the same operation using a stable request identifier scoped to the authorised user, term and operation. | Implemented — Idempotent request keys |
| FR-062 | Incomplete timetable results and cancellation completion | P1 | The system shall show scheduled and required occurrence counts and name every unscheduled occurrence. | Partial — Cancelled results are not retained |
| FR-063 | Validation failures and safe publication blocking | P1 | The system shall distinguish validation PASS, validation FAIL and an unavailable or inconclusive validation operation. | Implemented — Publication blocked on validation failure |
| FR-064 | Session expiry and permission changes | P1 | Every protected read and mutation shall verify current server-side authorisation and resource scope. | Implemented — Session expiry and permission checks |
| FR-065 | Instructor positions: doctors and teaching assistants | P1 | Each instructor shall have a position, Doctor or TA. | Implemented |
| FR-066 | Special rooms and room features | P1 | Rooms shall carry room features and activities shall carry required features. | Implemented |
| FR-067 | Sessions spanning consecutive periods and half-hour rule times | P1 | A session may start at a period only if the consecutive named periods starting there cover exactly the session's teaching minutes. | Implemented |
| FR-068 | Convenience objective | P1 | The default objective profile `convenience-v1` shall minimise, in weighted order: missed instructor preferences; | Implemented |
| FR-069 | Building a large timetable in parts | P2 | A run may schedule only selected programme years (at most 600 sessions per part) and may continue from an earlier draft. | Implemented |
| FR-070 | Advising students | P2 | An advising student shall keep the group's sessions minus dropped courses, plus the sessions of added courses with the chosen group. | Implemented |
| FR-071 | Exam plans and exam types | P2 | Each course shall have an exam plan: a number of quizzes (default 3, from 0 to 10), one midterm, an optional second-chance midterm and one final. | Implemented |
| FR-072 | Exam halls, splitting and TA invigilators | P2 | Students per exam shall be the sum of the course's group sizes, or the course's expected students. | Implemented |
| FR-073 | Built-in rule-based interpreter for typed constraints | P1 | The interpreter shall accept English, formal Arabic, Egyptian Arabic and mixed text. | Implemented |
| FR-074 | Locally hosted language model | P1 | The system shall support a language model hosted on the institution's server or network through Ollama (prototype default Qwen 2.5 7B Instruct). | Implemented |
| FR-075 | Ask JAI: questions about timetables and data | P2 | JAI shall answer questions about rooms, instructors, groups, courses and exams from the published timetable, or, if none is published, from the newest valid draft, or from the timetable the chat is about (FR-077). | Implemented |
| FR-076 | Ask JAI: commands with explicit confirmation | P2 | JAI may prepare any task the website offers, including: generating teaching or exam timetables; | Implemented |
| FR-077 | Ask JAI: chat memory and the timetable in question | P2 | Chats shall be kept per administrator. Each chat shall remember its subject, including the timetable it generated or discussed. | Implemented |
| FR-078 | Publishing one group's week from a whole draft | P2 | The system shall publish a merged timetable: the chosen groups' sessions from the draft (including shared lectures), plus the sessions the published timetable does not yet have; | Implemented |

## Non-functional requirements

No numeric target was invented; where the SRS leaves a value to a later decision it is marked open.

| ID | Category | Requirement | Prototype status |
|---|---|---|---|
| NFR-001 | Correctness | Publication shall be blocked whenever the independent validator detects a supported hard-rule violation or a missing assignment (FR-040). | Met in tests: publication is refused on any validator violation |
| NFR-002 | Correctness / maintainability | The validator shall be implemented separately from the solver model: separate module, no import of the solver’s constraint-building code, own test suite. The solver model shall expose an internal test hook that fixes every assignment variable to a given timetable by equality constraints, so the validator and solver model can be cross-checked (UNKNOWN is inconclusive, never agreement). | Met: separate validator module with its own tests |
| NFR-003 | Correctness | Solver outcomes shall be reported exactly as §11.2 defines; a time limit shall never be reported as infeasibility. | Met in tests |
| NFR-004 | Security | All authorisation shall be enforced server-side on every endpoint, including exports and experiment data. LLM credentials and database credentials shall be stored server-side only and never be sent to the browser or committed to the repository. | Met: server-side permissions; repository history scanned for secrets on 23 Nov 2026 |
| NFR-005 | Security | User credentials of local accounts (D-51) shall be stored using a salted, adaptive password hash. | Deviation: scrypt used instead of Argon2id |
| NFR-006 | Privacy | When the local model is configured, no text leaves the server. Otherwise, only the text and minimal entity context needed for extraction shall be sent to an LLM provider; student-level personal data shall not be sent; the outbound context shall be logged (FR-014). | Met with the local model: no text leaves the server |
| NFR-007 | Privacy / compliance | Applicable data-protection law, university policy, provider data-use terms and retention rules shall be identified and followed. The applicable rules are unknown to this draft. | Open |
| NFR-008 | Accessibility | The user interface shall meet an agreed accessibility standard; colour shall never be the sole carrier of meaning (FR-042); interactive controls shall be keyboard operable and labelled. | Partial: labelled, keyboard-operable controls; no formal audit |
| NFR-009 | Reliability | The system shall handle provider refusals, malformed or truncated output, rate limits, timeouts and outages without losing the submitted statement or corrupting state (FR-022); solver cancellation shall leave the system consistent (FR-026). | Met in tests (timeouts, retries, malformed output, cancellation) |
| NFR-010 | Reliability | Job and scenario state shall survive a web-server restart. Behaviour on worker crash: job marked FAILED. | Partial: jobs use heartbeats and leases; recovery objectives open |
| NFR-011 | Performance | Generation shall run under a configurable time limit; wall-clock runtime, outcome and objective shall be recorded for every run (FR-025). Numeric time limits and acceptable runtimes depend on the agreed dataset scale and hardware. | Met: every run records time limit, runtime, outcome and objective |
| NFR-012 | Performance | Extraction latency (request to validated proposal) shall be measured and recorded for every extraction (FR-023). Interactive page-response targets are not defined here. | Partial: latency recorded for extractions and chat evaluations; no target |
| NFR-013 | Scalability | The instance sizes (activities, rooms, instructors, groups, slots) on which each claim was tested shall be stated alongside the claim. | Met in the thesis: tested scale stated with each result |
| NFR-014 | Usability / responsiveness | Timetable views shall be readable (time, course, instructor, room legible, no overlapping labels, no horizontal page scroll in agenda view) at the supported viewport widths. | Partial: checked manually; supported widths not agreed |
| NFR-015 | Usability | Usability is defined operationally by measured task completion time, number of corrections and participant feedback (EV-3), not by adjectives. No target is set. | Not measured (no participant study) |
| NFR-016 | Reproducibility | The system shall record datasets, prompt and schema versions, model identifiers, solver version, parameters, seeds and dates for each run (FR-023, FR-024, FR-025). | Partial: versions, seeds and dates recorded for runs and fine-tuning |
| NFR-017 | Maintainability | Extraction, domain validation, solving, checking and presentation shall be separate modules; the LLM provider shall be replaceable by configuration (FR-022). | Met: separate modules; provider chosen by configuration |
| NFR-018 | Compatibility | Supported browsers: TBD. | Open |
| NFR-019 | Data retention | Retention periods for term data, extraction records, experiment data and logs: TBD; proposals in §10.5. | Open |
| NFR-020 | Backup / recovery | Backup and recovery for the prototype: TBD. | Partial: local database backups before destructive changes |
| NFR-021 | Localisation | The user interface shall be available in English and Arabic, selectable by the user, with right-to-left layout for Arabic (document direction, mirrored layout, logical start/end alignment). Timetable data entered in either script shall display correctly in both interface languages. | Met: English and Arabic interface with right-to-left layout; mixed Arabic/English chat text kept in reading order |
| NFR-022 | Observability | Jobs, extractions and validations shall emit structured log records with correlation identifiers. | Partial |
| NFR-023 | Licensing | Third-party components and any reused code shall have recorded licences and notices; UniTime code shall not be copied without a separate decision. | Not yet checked |

## Work added after SRS v0.4 (not yet written as SRS requirements)

- **Verified guide for JAI:** 25 code-checked statements about how JadwAI works are given to the local model with each relevant message, so it answers from them or says it is not sure (`backend/app/assistant_guide.py`).
- **Reply safeguards:** repeated sentences are removed; a reply cut off mid-loop keeps its complete sentences; an English reply to an Arabic message is rewritten once into Egyptian Arabic; a reply that drifts into Chinese, Japanese or Korean is cut at that point.
- **Fine-tuned local model:** QLoRA fine-tuning of Qwen2.5-7B-Instruct on reviewed, guide-grounded examples, merged into Ollama (`finetuning/`; results in `finetuning/RESULTS.md`).
- **Mixed-direction chat text:** English words, codes and times inside Arabic replies are shown in reading order.

## Known deviations to resolve with the supervisor

- PostgreSQL 17 is used instead of 18 (OQ-26).
- Passwords are hashed with scrypt instead of Argon2id (NFR-005).
- There is no separate Researcher role (SRS §3.2).
