# JadwAI annotation guide v1 — synthetic draft

Dataset version: `0.1.0-draft`. Schema: `proposal-contract-v1`. Original synthetic authoring by the project assistant on 25 October 2026; no private university data, external corpus or model-generated experimental outputs were used. Human review and adjudication have not happened. These labels are hypotheses for review, not confirmed ground truth.

## Unit and language categories

One item is one user statement plus an explicit synthetic department context. Categories are English (`en`), formal Arabic (`ar`), Egyptian Arabic (`arz`) and mixed language (`mixed`). A family groups translations of one intent/template. All four stay in the same split. The 24 development families contain 96 items; eight reserved families contain 32 items. A family is not an independent real participant, and four translations are not four independent institutional requirements.

The split is reserved development material, not a blind test: its author has seen every label, source files contain both partitions, and access is a local workflow guard rather than operating-system isolation. No model has been tuned or evaluated here. A fresh independently authored/adjudicated confirmatory set will be needed if this material informs prompts or implementation.

## Output decisions

- `ready`: every requested part is resolved into supported proposals, with no unresolved questions or unsupported content.
- `clarify`: ask the coded question instead of inventing a missing day, time, entity, interpretation or institutional threshold. Do not treat an omitted weekday as every day.
- `unsupported`: no supported proposal can represent the request faithfully. Retain an explicit unsupported code; do not silently approximate or weaken a hard rule.
- `conflict`: the meaning is understood but requested hard conditions or scalar updates are inconsistent. Retain the interpreted proposals for review and ask for resolution; do not approve them automatically.
- `mixed`: retain resolved supported proposals and explicitly disclose unsupported/unresolved fragments. Partial extraction is not permission to ignore the remainder.

The JSON contract uses `decision`, `proposals`, `clarifications` and `unsupported`. Codes are stable evaluation labels, not a requirement to show machine codes to users. Natural clarification wording can vary and is not scored by string similarity.

## Supported proposal boundary

A `rule` carries the current manual RuleInput fields and one typed target. Instructor unavailable/preferred, room unavailable, group unavailable, activity permitted and group permitted windows are supported. Rules are proposals only: approval is a later human action. Their hours are integers because that is the current manual-rule storage boundary; exact minute-based requests must not be rounded. Named teaching slots can still start at 08:30 or 10:15.

Windows for the same target are weekly alternatives. Different activity/group restrictions intersect. A session must be completely inside one permitted window. No permitted window on a day excludes that day. A mandatory closure prohibits any overlapping session. Adjoining time intervals do not overlap.

An `instructor_weekly_limit` proposes setting a scalar cap in teaching hours, in half-hour increments from zero through 168. Zero forbids teaching; it does not mean missing. Four 90-minute sessions equal six teaching hours. Unsetting a cap is outside this draft corpus.

A `realism_policy` proposal is a patch to the explicitly stated global student/instructor daily hour caps, not a reset of other policy fields. Entity-specific overrides and preferred daily caps are outside this draft.

An `assignment_lock` proposal identifies the context draft, activity and zero-based occurrence plus selected keep flags. Human-facing “occurrence 1” means payload `occurrence: 0`. It is never a direct instruction to change the live database. The context draft is fictional and cannot be used as a real website run ID.

Titles are human labels: generated wording is not semantically graded. Field values, targets, polarity, units, day/time, hard/preferred strength and all compound fragments are graded. Ordering of independent proposals is irrelevant; duplicate proposals are extra predictions.

## Context and ambiguity rules

Resolve full names/aliases only against the supplied context. “Nour” is ambiguous between two supplied instructors; Mona Adel is absent. “Group A” is ambiguous across two majors. Do not manufacture IDs. “Early” has no defined institutional threshold, so ask. “Not unavailable” does not unambiguously request a new availability constraint, removal of an old rule or no action: ask which operation is intended. Last week's requirements are absent from context.

Before 10:00 on a named day starts at the context teaching-day boundary of 08:00. An explicitly whole teaching day is 08:00–18:00. Friday is outside the supplied current calendar: request a calendar/day resolution instead of inventing Friday classes.

An unavailability plus a preference for the same time is not automatically a hard contradiction: a soft preference can be unsatisfied. The conflict example instead combines an activity's only permitted window with a mandatory closure of its attending group for the whole window. Two simultaneous exact values for the same scalar field require clarification.

Travel time between campuses, exam scheduling and silently ignoring capacity limits are unsupported. An exact 10:15–11:45 manual rule is unsupported at the current rule schema's precision, even though the timetable has such a teaching period.

## Review and correction protocol

1. Two human reviewers independently read every statement with its context, without treating the current expected output as authoritative. Check semantic equivalence across languages, especially Egyptian phrasing, negation and clock expressions.
2. Compare annotations, record disagreements and adjudicate with a third reviewer or the supervisor. Use pseudonymous reviewer IDs. Record item IDs, old/new semantic hashes, reason and decision in a versioned correction log; do not overwrite history.
3. Correct the authoring source and packaged labels together. Bump the dataset/annotation/schema version as appropriate, regenerate the manifest, and retain the old release. Review statuses and release metadata must reflect actual review.
4. Review near-duplicate intent/template families manually in addition to automatic family-ID and normalized-text checks. Semantic concept overlap is expected; paraphrase leakage is not claimed eliminated by hashing.
5. Freeze model/provider, prompt text/version, schema, decoding settings, retries, repetitions, language/family sampling and metric definitions before a pilot. Select acceptance thresholds from a development pilot and document them before confirmatory evaluation.
6. Reserve an independently authored set for confirmatory use. Record every access and its purpose. Do not tune on scored reserved results and later call the same set unseen.

## Measures and limits

Primary correctness requires an exact semantic match for the entire case. Proposal precision/recall preserves field association and counts invalid attempted proposals as false positives. The field-bag diagnostic is conditional on individually valid proposals and can miss association errors; never replace whole-case accuracy with it. Decisions, clarification/unsupported codes, unknown entity references, language breakdowns and cross-language family consistency are reported separately. Consistent wrong outputs remain wrong.

Missing predictions count against the full case denominator. Empty metric classes are undefined (`null`), not 100% successful. Missing telemetry is unknown. Only supplied measured latency, token, attempt and cost values are summarised. Retries include the initial attempt. Declaring `post_review` identifies an input file's stage; the scorer does not verify a human review occurred or measure correction effort.

Repeat runs, confidence intervals accounting for family dependence, human correction effort, independent adjudication and real model performance are future experiment work. Do not put oracle/unit-test scores into thesis results. The test suite copies labels only to verify scorer arithmetic.
