# Local model vs rule-based parser on development-v2 (144 statements)

Run: `qwen2.5:7b-instruct` via Ollama, code commit 3183a03, 23–24 Nov 2026 (see `RUN.txt`).
Scores: `score-qwen2.5_7b-instruct.json` (this folder) and `../2026-11-08/parser_score.json`.
Intervals: 95% percentile bootstrap over the 36 families, 1,000 replicates, seed 42.

| Measure | Rule-based parser | Local model |
|---|---|---|
| Exact output | 0.326 (47/144), 0.215–0.458 | 0.090 (13/144), 0.028–0.167 |
| Decision accuracy | 0.597, 0.465–0.736 | 0.479, 0.340–0.604 |
| Contract-valid outputs | 144/144 | 18/144 |
| Proposal precision / recall / F1 | 0.448 / 0.361 / 0.400 | 0.116 / 0.204 / 0.148 |
| Field F1 | 0.605 | 0.313 |
| Clarification F1 | 0.351 | 0.000 |
| Unsupported-request F1 | 0.000 | 0.000 |
| Unknown entity referenced (cases) | 0 | 16 |
| Median seconds per statement | not measured | 116 |

By language (exact / decision accuracy): English 4/36, 0.50; formal Arabic 6/36, 0.44;
Egyptian Arabic 1/36, 0.53; mixed 2/36, 0.44. (Parser: 20, 8, 7, 12 exact; 0.69, 0.53, 0.50, 0.67.)
The figures now differ by language, so the earlier "identical in every language" fault is gone.

## Why the model's outputs fail validation (errors per case, a case can have several)

| Scorer error | Cases | Meaning |
|---|---|---|
| decision_consistency | 85 | decision does not fit the rest, e.g. `unsupported` with a correct proposal |
| rule_fields | 83 | extra or missing fields, mostly `params` objects from the app's newer rule format |
| invalid_hours | 57 | hours outside the calendar or not whole hours |
| unsupported_rule_type | 56 | rule types the evaluation contract does not know |
| outside_calendar | 51 | day not in the context's calendar |
| unknown_entity | 18 | an ID that is not in the context |

18 cases fail **only** on rule type or fields.

## Two setup mismatches (must be stated next to the numbers)

1. **Rule vocabulary.** The model receives the running application's prompt, which now describes
   more rule types than the October evaluation contract (`teaching_preferred`, `teaching_allowed`,
   `instructor_max_daily_hours`, `instructor_max_days`, `activity_room`, ...) and a `params` field.
   The model used them (56 proposals of types the contract rejects). The parser was written
   against the contract. Part of the gap therefore measures the prompt/contract mismatch, not
   only interpretation quality.
2. **Clarification codes.** The prompt does not list guide v2's fixed codes, so the model invented
   its own (`clarify_if_needed`, `confirmed`, `no_instructor_id`, ...). Clarification F1 = 0 partly
   reflects that. The parser's codes were renamed to the guide's after its first run.

## What is a genuine model behaviour (not explained by the mismatches)

Decisions are scored on their own, so the confusion below holds whatever the vocabulary:

| Expected → predicted | ready | clarify | unsupported | conflict | mixed | none |
|---|---|---|---|---|---|---|
| ready (76) | **62** | 2 | 10 | 0 | 1 | 1 |
| clarify (44) | 24 | **5** | 13 | 1 | 1 | 0 |
| unsupported (16) | 11 | 2 | **2** | 1 | 0 | 0 |
| conflict (8) | 8 | 0 | 0 | **0** | 0 | 0 |

- The model mostly answers `ready`: 24 of 44 statements that need a question, all 8 conflicts and
  11 of 16 unsupported requests were treated as ready. It guesses rather than asks (RQ2).
- It labels 10 clear statements `unsupported` while also producing a correct proposal
  (e.g. jdw-001: correct unavailable rule, decision `unsupported`).
- One reply was invalid JSON (time limit 600 s, one attempt).

## Caveats

Draft, unreviewed labels; synthetic statements; the parser was adjusted after its first run on the
same data and the schema order was tuned on 8 of these statements; one run, temperature 0, seed 42,
one CPU laptop. Development-level evidence only. A fairer second run would give the model the
contract's rule list and the guide's codes in the prompt; that run has not been done.
