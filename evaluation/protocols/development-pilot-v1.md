# Development pilot procedure v1

Draft prepared 1 November 2026. This is a procedure, not a completed study or authorization to spend money. The administrator is the sole human annotation reviewer under `admin-review-v1.md`.

## Before running

Obtain the actual administrator review of the gold-free 24-item pack covering both contexts. Preserve the submitted review, guide hash, corrections and rationale. Reviewing the sample does not establish review of all 144 development items. Publish corrections in a new version; never edit a manifest-bound release in place.

Record which reviewed cases are eligible for the pilot and why. Keep intent families together. The current development material is author-exposed and may support development diagnostics only. A fresh confirmatory release requires separate authorship, custody and leakage evidence.

Select the provider/model and obtain any required paid-call budget. Fill every required configuration field: provider, model, schema, prompt and few-shot versions, explicit decoding settings, timeout, retry limit and repetition count. Record the dataset manifest hash, software revision, execution environment and prompt/few-shot hashes. Do not store credentials in configuration or results. Model choice, budget, repetition count and acceptance thresholds remain undecided.

## Execute and measure

Export only input text and its supplied context to the chosen adapter. Never send expected labels as part of a request. Preserve the original response and each attempt's outcome separately from validated output. Associate every prediction with its source item and repetition; do not pool repeated IDs into one scoring file.

Report all selected items in the denominator. Missing responses, exhausted retries and invalid outputs remain failures; do not silently discard them or replace them with gold. Record observed elapsed latency, attempts and provider-reported token usage. Report unavailable usage or cost as missing, not zero. Any estimated cost must identify the pricing source and date separately from measured billing.

Score raw predictions before correction. Preserve administrator correction time, changed fields and final interpretation separately, then score post-review predictions as a distinct stage. Human-corrected output cannot be presented as raw model accuracy.

Summarize end-to-end and per-field correctness, clarification/unsupported decisions, invalid outputs and errors by language/context. Report family-clustered uncertainty with the method and seed. Avoid treating four translations of a family or repeated calls as independent samples. With only one human reviewer, do not report inter-annotator agreement.

## After the development pilot

Document failure categories and changes to the guide, prompt or examples. Any such change gets a new version and change note. Use development evidence to propose acceptance thresholds and repetitions; record the actual approved values before any confirmatory scoring. This procedure does not select numeric thresholds on the owner's behalf.

Freeze the complete configuration and dependencies before protected-label access. A technical freeze is necessary but does not establish independent custody, blind data, institutional validity or research acceptance. Report results only after actual model runs and actual administrator review exist.

Phase 5 remains open until its research prerequisites are evidenced. Phase 6 is planned; adapter and approval-flow implementation can use deterministic test doubles, whose results are software checks rather than model-performance evidence.
