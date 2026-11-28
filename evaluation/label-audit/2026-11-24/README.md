# Label audit, 24 November 2026

A human check of a sample of the AI-drafted development labels (bundle `0.2.1-draft`, guide v2.1).

- **Sample:** 36 statements, one from each of the 36 intent families, built with `python evaluation/label_audit.py build` (seed 42). The language rotates within each context, so there are 9 statements per language. Draft decisions in the sample: 19 ready, 11 clarify, 4 unsupported, 2 conflict.
- **Part A** (`part-a-blind.md`): blind. The reviewer chooses the decision and writes the expected answer without seeing the draft label.
- **Part B** (`part-b-check.md`): the draft label in plain English. The reviewer marks it correct, wrong or ambiguous, and corrects it if wrong.
- **Key** (`key.json`): maps sheet IDs to case IDs and the draft labels. Do not open it while reviewing.

## Order

1. Fill in all of Part A. Do not open Part B, `key.json` or `cases.jsonl` until you finish.
2. Fill in Part B. Do not edit Part A afterwards.
3. Run `python evaluation/label_audit.py score`. It checks the sheets are complete and writes `score.json`. It reports:
   - decision agreement and Cohen's κ between the reviewer's blind decisions and the draft labels;
   - the share of draft labels judged wrong, with a 95% Wilson interval;
   - the verdicts per language and the list of labels that are not correct.

## What it can and cannot support

The audit can support "a single reviewer checked a stratified sample of 36 of the 144 draft labels; N were judged wrong." It is not double annotation and does not give inter-annotator agreement. One statement per family is checked, so the other three translations of each family are not. The guide summary in Part A states the guide's rules, so Part A measures agreement under the guide, not an independent reading. Do not change the labels in `cases.jsonl` from this audit. Corrections go into a new bundle version with a correction log, following the guide's review protocol.
