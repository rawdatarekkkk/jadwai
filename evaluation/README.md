# Phase 5 — offline evaluation materials

This is a provider-neutral dataset and scorer for the verified manual proposal boundary. It makes no network requests, calls no model, incurs no API cost and changes no website data.

The initial release has **128 synthetic statements in 32 translated intent families**: 96 development items and 32 reserved items, with English, formal Arabic, Egyptian Arabic and mixed language in each family. Labels are **draft and unreviewed**. Reserved material is accessible to the author and must not be described as a blind confirmatory test set.

Read [annotation-guide.md](annotation-guide.md) before labelling or scoring. [proposal-contract.schema.json](proposal-contract.schema.json) describes the output shape. The runner also performs context/entity/time/unit checks beyond JSON shape.

## Validate and export

From the JadwAI directory:

```sh
python3 evaluation/runner.py validate
python3 evaluation/runner.py validate --include-reserved --allow-reserved --reason 'Corpus integrity review before annotation'
python3 evaluation/runner.py export-inputs --output /tmp/jadwai-dev-inputs.jsonl
backend/.venv/bin/python -m unittest discover -s evaluation/tests -v
```

Exports contain only item ID, language, text and context ID, plus a companion context file. They omit expected outputs, family labels and review metadata. Default commands never read reserved cases. Explicit reserved access is logged in `access-log.jsonl`; that guard is a reproducibility convention, not a security boundary. File names must be fresh: existing outputs are not overwritten.

## Score actual predictions later

A JSONL prediction row has an `id`, an `output` matching the proposal contract, and optional measured `metadata` (`latency_ms`, `attempts`, `input_tokens`, `output_tokens`, `cost_usd`). Keep raw responses and provider errors in the actual experiment record; this offline tool does not create them. Failed requests may have null output and count as failed cases. Unknown/duplicate IDs are rejected; missing expected IDs remain failures.

Copy `run-config.template.json` to a run-specific config and replace placeholders with the actual provider/model, prompt/schema versions and decoding/retry/repetition settings. Do not include API keys. Then:

```sh
python3 evaluation/runner.py score --predictions /path/to/raw-predictions.jsonl --config /path/to/frozen-run-config.json --stage raw --output /tmp/jadwai-raw-score.json
python3 evaluation/runner.py score --predictions /path/to/reviewed-predictions.jsonl --config /path/to/frozen-run-config.json --stage post_review --output /tmp/jadwai-reviewed-score.json
```

The scorer saves manifest, configuration, prediction and scorer hashes, full denominators and item-level errors. Raw and declared post-review results remain separate. No real predictions or model-performance results are supplied in this release. Tests that copy expected labels are explicitly oracle self-tests of software arithmetic.

## Release procedure

The original corpus is reproducibly packaged by `build_corpus.py`. It is source authoring, not an extractor. After human review, version the authoring source, corrections and annotation guide together; retain the old release before rebuilding. The manifest freezes data, contract, annotation instructions and scorer/authoring code. Do not regenerate this draft over an adjudicated release.

Pending before research use: supervisor agreement on size/sampling and institutional definitions; actual administrator multilingual review with its single-annotator limitation; development pilot; frozen thresholds; fresh confirmatory data; actual provider adapter and measured runs; repeated-run and confidence-interval analysis. Paid model selection/spending has not been authorised.

## Phase 5 harness extensions — 1 November 2026

`harness.py` adds an append-only version registry, frozen run configurations, logged denial/approval of reserved-scoring requests, reviewer agreement arithmetic, and 95% percentile bootstrap intervals that resample complete intent families. It wraps the unchanged original scorer and manifest. It does not create a new dataset release or make the existing reserved material blind.

Development scoring now has a stricter recommended entry point:

```sh
backend/.venv/bin/python evaluation/harness.py score --mode development --predictions /path/to/predictions.jsonl --file /path/to/actual-run-config.json --output output/development-score.json
```

Use the actual provider/model/prompt/schema identifiers in the run configuration; template placeholders are rejected. Supply measured predictions, not copied gold, for model experiments. The runner remains a legacy corpus-validation/arithmetic tool. Its explicit reserved opt-in is not the stricter harness authorization mechanism.

For a future authorized reserved run, first register the exact approved prompt and few-shot files as distinct immutable versions:

```sh
backend/.venv/bin/python evaluation/harness.py register --kind prompt --version approved-prompt-v1 --purpose confirmatory --file /path/to/approved-prompt.txt --note 'Approved configuration for the declared experiment'
backend/.venv/bin/python evaluation/harness.py register --kind fewshot --version approved-fewshot-v1 --purpose confirmatory --file /path/to/approved-examples.json --note 'Approved examples for the declared experiment'
backend/.venv/bin/python evaluation/harness.py freeze --version experiment-v1 --file /path/to/complete-config.json --note 'Freeze before accessing reserved labels'
```

The complete config requires provider, model, matching schema_version, registered prompt_version and fewshot_version, a nonempty explicit decoding object, nonnegative retry_limit, positive repetitions and positive timeout_seconds. A development-only artifact cannot authorize reserved scoring. `score --mode reserved --version experiment-v1 --reason 'Declared purpose of this reserved run' ...` validates all frozen hashes before reading reserved cases. Denied attempts are also logged. No such model configuration has been frozen in the real project by these implementation tests.

Files use exclusive creation, safe version identifiers and integrity hashes. A user with filesystem access can still alter files or call the legacy loader: this is an auditable research workflow, not a security boundary. Do not place credentials in configurations. Both successful and denied accesses appear in `guard-access-log.jsonl`; the original loader retains its separate access log.

Intervals cover whole-case accuracy, decision accuracy and precision/recall/F1 diagnostics. Undefined classes remain null. A single family has no interval. Perfect oracle scores can have degenerate intervals and are only scorer checks. Family bootstrapping does not make synthetic convenience data representative. `harness.agreement` computes raw agreement and Cohen's kappa for matching reviewer item sets; no human agreement figures are claimed.

See `PHASE5_STATUS.md` for the remaining research requirements.

## Development bundle 0.2.0-draft

`development-v2/` is a separate immutable development-only bundle: 144 items, 36 whole intent families, two fictional institutional contexts. It carries forward only the original 96 development examples and adds 48 design-school statements with English, formal Arabic, Egyptian Arabic and mixed-language wording. Each item has draft provenance and category tags. The old release and its reserved data remain unchanged. `guides/annotation-guide-v2.md` explains the context-specific historical weekly-cap boundary versus the second context's Saturday/overtime semantics. No independent human review is claimed.

Validate and prepare a gold-free reviewer sample:

```sh
backend/.venv/bin/python evaluation/development.py validate
backend/.venv/bin/python evaluation/development.py export-review --families 6 --seed 42 --output output/reviewer-pack.json
```

A prepared six-family/24-item pack is available at `output/phase5-review-pack-v2.json`; its sample includes both contexts. The administrator reviews this pack under `protocols/admin-review-v1.md`. A second human review is optional; only if obtained, give that reviewer the same gold-free pack independently. Each actual reviewer fills every item's `annotation` with a complete proposal envelope and adds a nonempty `rationale`. Save a separate annotated file. The export contains context and original wording, not expected labels. A JSON record template is intentionally blank; copying draft gold is a software test, not annotation.

Import the administrator’s completed review without changing gold labels. The second import and comparison below are optional and require a genuine second review:

```sh
backend/.venv/bin/python evaluation/development.py import-review --pack output/reviewer-pack.json --annotations /path/to/reviewer-a-annotations.json --reviewer reviewer-a --output output/reviewer-a-record.json
backend/.venv/bin/python evaluation/development.py import-review --pack output/reviewer-pack.json --annotations /path/to/reviewer-b-annotations.json --reviewer reviewer-b --output output/reviewer-b-record.json
backend/.venv/bin/python evaluation/development.py compare --first output/reviewer-a-record.json --second output/reviewer-b-record.json --output output/reviewer-agreement.json
```

Imports reject missing, duplicate or unknown IDs, changed source wording/context, invalid semantic output, missing rationale and wrong bundle hashes. Records retain declared reviewer IDs and separate hashes. Reviewer identity/independence is not verified by the software. Agreement reports both decision-category kappa and IDs of full-semantic disagreements; it does not adjudicate them or promote a release. Every output uses exclusive file creation.

The new bundle can be scored with `evaluation/harness.py score --dataset evaluation/development-v2 ...`. It has no reserved path. Its manifest binds contexts, cases, guide and proposal-contract hashes. Any correction requires a separate release rather than editing a manifest-protected source file.

`development.py screen --fingerprints /path/to/independently-prepared-fingerprints.json --output output/leakage-flags.json` performs exact normalized-hash and token-trigram lexical screening without displaying protected reference text or IDs. Fingerprint format: `leakage-fingerprints-v1`, with a `families` array of `exact_hashes` and `shingle_hashes` arrays. Strings use Unicode NFKC normalization, lowercase/casefold and collapsed whitespace; token trigrams are SHA-256 hashed. Threshold is Jaccard ≥ 0.65 or an exact hash match. A flag is not proof of leakage; lack of a flag is not proof of semantic independence. An independent data custodian must prepare fresh held-out fingerprints. No protected confirmatory reference set has been created or screened in this development milestone.

After reviewing disagreement IDs, an adjudicator can supply a JSON array containing exactly those IDs, a complete `annotation`, and a nonempty `rationale` for each. Save an immutable resolution record:

```sh
backend/.venv/bin/python evaluation/development.py adjudicate --first output/reviewer-a-record.json --second output/reviewer-b-record.json --resolutions /path/to/resolutions.json --reviewer adjudicator-id --output output/adjudication-record.json
```

Agreed items are retained; unresolved disagreements, duplicate decisions, invalid outputs and attempts to override agreed items are refused. The record binds both reviewer-file hashes, the guide/dataset version, declared adjudicator identity, and original/decided annotation hashes. It does not overwrite gold or automatically certify/promote a reviewed dataset release.

## Website review workspace

The local website's administrator **Evaluation** section exposes bundle counts and guide/review-pack downloads. A completed JSON file can be uploaded, validated and saved as a separate immutable PostgreSQL review record, with the submitting account and a caller-generated request key. The server checks the fixed pack's complete ID set, original wording/context, manifest, supported proposal semantics and rationales. It does not change gold, approve scheduling constraints, update academic-input versions or call providers.

Review records can be downloaded for `development.py compare` and `development.py adjudicate`. PostgreSQL rejects UPDATE/DELETE/TRUNCATE; runtime access has only SELECT/INSERT. Tests save synthetic review fixtures only in disposable test schemas. No live human review records are created by implementation verification. Reviewer identity and independence remain operator-declared. Reserved labels and expected development answers are not included in review-pack or status responses.

### Compare saved reviews in the website

Evaluation → Compare annotation reviews accepts two saved records from different declared reviewer IDs. The server rejects self-comparison, unknown records, mismatched packs or dataset versions, and unavailable archived source bundles. It reports decision agreement and Cohen's kappa separately from complete-semantic agreement, and lists only disputed statements with their supplied annotations, rationales and relevant context. Draft gold is never returned. Comparison reports can be downloaded as JSON; comparison performs no database write and cannot promote gold or mark reviews adjudicated. A null kappa remains undefined. Declared reviewer IDs do not establish independence.

### Save adjudication decisions in the website

After comparing two reviews, **Record adjudication decisions** lets an administrator enter a separate pseudonymous adjudicator ID, choose either submitted interpretation or a custom corrected annotation, and explain every disputed item. The server validates all annotations against the bound context and requires exactly the dispute-ID set; agreed items cannot be overridden. The website requires a declared adjudicator ID distinct from both declared reviewers, including case-insensitive comparisons. This is an ID rule, not verification of real-world independence.

Submissions are idempotent and produce an append-only `evaluation_adjudication` record linked by foreign keys to the two immutable source reviews. Exports bind reviewer-record hashes, original/decided annotation hashes, the guide/dataset version and rationales. PostgreSQL rejects updates/deletes/truncation; no operational input version, gold file or dataset-release status is changed. A decision on fully agreeing reviews may be recorded with an empty resolution list. Saved history remains available in Evaluation after reloading. Independent research sign-off and promotion of a corrected dataset remain separate work.

### Annotate the current pack directly in the browser

Evaluation → **Start in-browser review** opens the same gold-free 24-item pack. The reviewer chooses a decision, adds one structured rule per supported fragment, supplies clarification/unsupported codes where required, and writes a rationale. Rule builders select only context-defined entities and teaching days, use integer-hour bounds, and never infer missing details. The editor has no suggested decisions or copied gold labels. It covers time-rule proposals used by this review pack; JSON import remains the route for other proposal kinds.

Navigation between statements preserves annotations and shows completion progress. The submit button stays disabled until all statements pass local envelope/rule checks and have rationales, and a reviewer ID is supplied. Submission uses the existing source-bound review-validation API, which remains authoritative. No scheduling rule is approved by annotating a statement. Successful submissions are immutable records, and retries use the same request key. Starting a new review clears every annotation.

Unsaved work stays only in the current browser workspace's memory, scoped to the authenticated account. It survives sidebar navigation, but not a refresh, closing the tab or signing out; the page warns before unloading a dirty draft. No draft is written to persistent browser storage. A different account cannot restore the in-memory draft. Draft collection is separate from independent identity verification and research sign-off.

## Administrator-review decision

The user selected administrator review on 1 November 2026. Use `protocols/admin-review-v1.md`: one administrator supplies the human annotations, and the single-annotator limitation must be reported. A second human review and adjudication are optional; do not create multiple identities to simulate independent reviewers. Current draft labels and research outcomes stay unconfirmed until real administrator review is submitted.

## Future dataset lifecycle tooling

`dataset_lifecycle.py` prepares deterministic, context-stratified pilot/development/reserved splits at whole-family level. Each context needs at least three complete four-language families, so the integer allocation leaves at least one family per split/context. The default requested proportions are 20% pilot, 60% development and the remaining 20% reserved; actual family counts are recorded and can differ through rounding. Ratios and seed are explicit plan inputs, not approved research sample sizes.

An incoming source JSON must declare `format: evaluation-source-v1`, a release `dataset_version`, `contexts`, and `items`. Each item carries `id`, `family_id`, `context_id`, `language`, `text`, nonempty `tags`, and `provenance` with `author_id` and `kind` (`synthetic` or `consented_institutional`; institutional wording requires `consent_reference`). The proposal schema is `proposal-contract-v1`. Planning can precede annotation. Exact duplicated wording across families and incomplete language families are rejected.

```sh
backend/.venv/bin/python evaluation/dataset_lifecycle.py plan --source /path/to/new-source.json --seed 42 --output /path/to/split-plan.json
```

Before sealing, each item must have finalized `gold` and `review_status: reviewed` for the single-annotator protocol, or `review_status: adjudicated` for the dual-annotator protocol. Single-admin review does not require an adjudicator. Put actual annotation metadata in the root `review_declaration`, without changing plan-bound wording/context/author provenance:

- `protocol`: `single_annotator` with exactly one declared reviewer, or `dual_annotator_adjudicated` with two reviewers and a distinct adjudicator.
- `reviewer_ids`, and `adjudicator_id` for the dual protocol.
- `guide_version`, `guide_sha256` of the reviewed guide's bytes, and a real `review_reference`.

A separate `independence_declaration` requires `fresh_confirmatory_material: true`, `developer_exposed_to_reserved: false`, and a `custodian_id`. These declarations require real external evidence. They are not verified identities, consent checks or proof of blindness. Existing assistant-authored development/reserved material must not be relabelled to satisfy them.

```sh
backend/.venv/bin/python evaluation/dataset_lifecycle.py seal --source /path/to/reviewed-new-source.json --plan /path/to/split-plan.json --guide /path/to/reviewed-guide.md --output /path/to/fresh-release
backend/.venv/bin/python evaluation/dataset_lifecycle.py validate-development --release /path/to/fresh-release
```

Sealing binds guide/contract files, exact case hashes, split membership and the recorded protocol, and publishes a new non-overwriting release directory. Reserved labels are stored separately under `protected/`. Default development loads do not read that file. Reserved loading through `harness.py` requires a complete frozen configuration and logged reason before reading its contents; allowed and denied attempts are logged with timestamps. A frozen configuration is bound to the entire manifest, and modified files/items are rejected.

The technical seal deliberately retains `research_ready: false`, `independently_adjudicated: false`, and `reserved_is_blind: false`. It does not certify operator declarations or institutional research acceptance. The local file loader is a workflow boundary, not protection against a person with filesystem access. Lexical and semantic leakage review still applies. Single-annotator limitations remain in the manifest.

Only temporary synthetic fixtures have exercised sealing. No new real protected dataset has been created, and neither existing draft release has been rewritten.

## Development pilot procedure

See `protocols/development-pilot-v1.md` for review prerequisites, observed measurements, failure handling and the decisions that remain open before a real experiment. The configuration template matches the current harness fields but deliberately remains incomplete; copying it does not authorize or freeze an experiment.
