# Second local-model run: contract-aligned prompt (144 statements)

Run: `qwen2.5:7b-instruct` via Ollama, 24 Nov 2026 05:00–07:53 (see `RUN.txt`), temperature 0, seed 42,
`num_ctx` 8192, `num_predict` 1800, one attempt, 600 s limit. Prompt and schema: `score_contract_prompt.py`.
Scores: `score-qwen2.5_7b-instruct.json`. Comparisons: `../2026-11-23-full/` (first run, application
prompt) and `../2026-11-08/parser_score.json` (rule-based parser).
Intervals: 95% percentile bootstrap over the 36 families, 1,000 replicates, seed 42.

**What changed from the first run.** The prompt describes only the evaluation contract's proposal kinds
and rule types, gives the 12 clarification and 4 unsupported codes of guide v2 with one-line meanings
(constrained to these as enums), and the context adds the source draft. The model and decoding are the
same. The code descriptions were written from the codes used in the development labels, so this run is
tuned toward the labels: development evidence only.

| Measure | Rule-based parser | Model, application prompt | Model, contract prompt |
|---|---|---|---|
| Exact output | 0.326 (47), 0.215–0.458 | 0.090 (13), 0.028–0.167 | 0.167 (24), 0.069–0.264 |
| Decision accuracy | 0.597, 0.465–0.736 | 0.479, 0.340–0.604 | 0.556, 0.431–0.674 |
| Contract-valid outputs | 144 | 18 | 122 |
| Proposal F1 (P / R) | 0.400 (0.448 / 0.361) | 0.148 (0.116 / 0.204) | 0.239 (0.169 / 0.407) |
| Field F1 | 0.605 | 0.313 | 0.380 |
| Clarification F1 | 0.351, 0.141–0.576 | 0.000 | 0.104, 0.000–0.236 |
| Unsupported-request F1 | 0.000 | 0.000 | 0.160, 0.000–0.308 |
| Unknown entity referenced (cases) | 0 | 16 | 6 |
| Families with all four versions valid | 36 | 0 | 24 |
| Median seconds per statement | not measured | 116 | 39 |

By language, exact / decision accuracy (contract prompt): English 8/36, 0.61; formal Arabic 8/36, 0.56;
Egyptian Arabic 3/36, 0.56; mixed 5/36, 0.50. (First run: 4, 6, 1, 2 exact. Parser: 20, 8, 7, 12.)

The contract prompt roughly doubled exact output and made most outputs valid, but the parser is still
higher on every measure except unsupported requests, and the intervals of the parser and the
contract-prompt run overlap for exact output and decision accuracy.

## Decisions (expected → predicted; "none" = invalid output)

| Expected | ready | clarify | unsupported | conflict | mixed | none |
|---|---|---|---|---|---|---|
| ready (76) | **52** | 16 | 0 | 0 | 2 | 6 |
| clarify (44) | 19 | **25** | 0 | 0 | 0 | 0 |
| unsupported (16) | 5 | 7 | **3** | 0 | 0 | 1 |
| conflict (8) | 3 | 0 | 0 | **0** | 0 | 5 |

- The model now asks: 25/44 clarify cases were recognised (first run 5/44). It also asks when it should
  not (16 clear statements answered `clarify`), so the bias moved from guessing towards over-asking.
- Conflicts are still never recognised; 5 of 8 conflict statements produced no valid output.
- Unsupported requests are mostly answered as `clarify` or `ready`.

## Why the remaining cases fail

- **Invalid outputs (12).** All 12 took 330–383 s and returned no parseable JSON; the most likely cause
  is reaching the 1,800-token output limit while generating (the raw text was not kept). Six of them
  are conflict or unsupported statements, four of which are the four versions of one conflict family.
- **Wrong rule kind.** The model produced 161 `instructor_weekly_limit` proposals where the labels have 8,
  in 84 of 144 cases: 57 with 0 hours used in place of a day-specific `unavailable` rule (e.g. jdw-001,
  "cannot teach Sunday 08:00–10:00"), and 79 with 12 hours added without any basis in the statement.
  The prompt's phrase "0 forbids teaching" probably invited the first error. This over-generation is why
  proposal precision is 0.17 while recall rose to 0.41.
- **Wrong codes.** `ambiguous_instructor` was used 28 times, never where the labels use it.

## Label inconsistency found while writing the prompt

Guide v2's labels use both `day_required` and `missing_day` for a missing day, and two codes for
minute-precise rules (`manual_rule_minute_precision_not_supported` and `minute_rule_precision`). A model
cannot tell which of a synonymous pair is expected, so a few clarification and unsupported errors are
label noise. The codes should be merged in the next revision of the guide; the labels were not changed
for this run.

## Caveats

Draft, unreviewed labels; synthetic statements; the code descriptions were written from these labels;
the parser was adjusted after its first run on the same data; one run, temperature 0, seed 42, one CPU
laptop. Development-level evidence only; the reserved statements were not used.
