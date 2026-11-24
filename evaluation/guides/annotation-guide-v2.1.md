# Annotation guide v2.1 draft — development review

Version: annotation-guide-v2.1-draft. Date: 24 November 2026. Status: assistant-authored, pending independent multilingual review. Predecessor: annotation-guide-v2-draft (1 November 2026), retained unchanged with development bundle 0.2.0-draft.

## Changelog

### v2.1 — 24 November 2026: merged synonymous codes

Two pairs of codes in the 0.2.0-draft labels meant the same thing. A method cannot know which synonym is expected, so each pair now has one canonical code:

| Retired code | Canonical code | Meaning |
|---|---|---|
| `missing_day` (clarification) | `day_required` | The statement gives a time but no weekday. |
| `minute_rule_precision` (unsupported) | `manual_rule_minute_precision_not_supported` | The rule needs minute precision, which manual rules cannot store. |

`manual_rule_minute_precision_not_supported` is kept because the labels use it more often: 8 times (4 in release 0.1.0-draft, 4 in bundle 0.2.0-draft) against 4 for `minute_rule_precision` (bundle 0.2.0-draft only). It also follows the `*_not_supported` pattern of the other unsupported codes, and keeping it leaves release 0.1.0-draft (and its reserved split) unchanged. `day_required` is also the code the backend rule parser emits.

Development bundle 0.2.1-draft (`development-v2.1/`) applies these two renames to bundle 0.2.0-draft and changes nothing else: same 144 statements, wording, contexts, decisions and proposals. Eight labels change (four `missing_day`, four `minute_rule_precision`). Bundle 0.2.0-draft and this guide's predecessor stay in the repository unchanged.

Results already reported under `thesis/evidence/` were scored on the pre-merge 0.2.0-draft labels and are not re-scored by this revision.

## Clarification and unsupported codes

Use these stable codes. Do not use a retired code or invent a synonym for an existing one; if no code fits, record that in the rationale.

Clarification codes: `ambiguous_group`, `ambiguous_instructor`, `day_required`, `hard_window_has_no_placement`, `historical_context_required`, `operation_required_for_negated_closure`, `resolve_hard_conflict`, `rule_type_and_strength_required`, `time_window_required`, `undefined_early`, `unknown_instructor`.

Unsupported codes: `hard_capacity_relaxation_not_supported`, `hard_weekly_cap_under_overtime_policy`, `manual_rule_minute_precision_not_supported`.

Retired (do not use): `missing_day` → `day_required`; `minute_rule_precision` → `manual_rule_minute_precision_not_supported`.

## Context boundary (carried over from v2)

Development bundle 0.2.0-draft, and therefore 0.2.1-draft, retains the original 96 development items and adds 48 statements in 12 four-language families for a second fictional institution, a design school. All new items are development material, not confirmatory data. Family IDs are unique across contexts. No reserved examples have been read, moved, replaced or relabelled by this release builder.

Apply guide v1's supported rule semantics and entity-resolution rules to the first synthetic context. Its Sunday–Thursday calendar and weekly-cap examples remain historical context-specific diagnostics. They do not assert current GIU policy.

For the second context, use Saturday–Thursday and the explicitly recorded 12 regular teaching hours with overtime permitted. A request to prohibit all hours above 12 is unsupported by that context's proposal boundary; do not silently change the application's overtime policy or reinterpret a prohibition as a warning. Integer-hour unavailable/preferred/permitted-window proposals remain supported. A minute-specific rule remains unsupported by the current storage precision, even if named teaching periods have minute boundaries. Do not round it.

## Annotation procedure

Read the context and full statement. Produce an envelope with decision, proposals, clarification codes and unsupported codes. Proposals remain unapproved. Do not infer a missing weekday, vague threshold, unknown instructor ID, student group membership or room suitability. Shared-target permitted windows are alternatives; different targets intersect. Mandatory closures take precedence over soft preferences without making their combination a hard contradiction.

All four translations in one intent family remain together. Reviewers must check semantic equivalence, Arabic negation, Egyptian clock expressions, time units and hard versus preferred wording. Record ambiguity rather than assuming the draft gold is authoritative.

- Ready: all fragments resolved into supported proposals.
- Clarify: missing day, undefined early, unknown instructor or similar unresolved meaning; stable codes identify the question, not exact natural-language wording.
- Unsupported: a request cannot faithfully fit the context's supported operations.
- Conflict: interpreted hard constraints cannot both hold; retain interpretations and ask for resolution.
- Mixed: supported and unresolved/unsupported fragments coexist; never drop fragments.

A label is not human-reviewed merely because a script validates its schema or a scorer matches it. Do not include oracle self-test scores in thesis model results.

## Reviewer workflow

Export a gold-free review pack through `development.py export-review`. Reviewers use pseudonymous IDs and independently add a complete output under annotation, a nonempty rationale, and their reviewer ID. Importing labels validates IDs, context semantics and completeness; it writes a separate immutable review record. It never overwrites gold or promotes a release automatically.

Two independent human reviews and a recorded adjudication are required to claim double annotation. Agreement on decision categories can be computed separately; field-level and semantic agreement require review of the complete annotations. A fresh independently managed confirmatory set and a development pilot are still needed. Automatic text-duplicate checks cannot rule out semantic paraphrase leakage.
