# Research questions against the evidence (23 November 2026)

Working note for agreeing the final scope with the supervisor. It changes nothing in `main.tex`.
"Evidence" means something measured and kept in the repository; plans and passing software tests are listed separately.

## Summary

| Question (as in `main.tex`) | Evidence that exists | Status | Suggested action |
|---|---|---|---|
| **RQ1** LLM extraction of formal constraints from natural language | Rule-based baseline on 144 development statements (Ch. 4: 0.326 exact, decision accuracy 0.597). A local `qwen2.5:7b-instruct` run on the same set stopped at 116/144 and is not in the thesis. GPT-5.4 mini adapter built, never called (no budget). Labels are draft; no human annotation submitted. | **Not answerable as designed** | Reframe as a development-level comparison: finish the local run (28 items, about 30 min), check its scoring, and report parser vs local model on development data with the draft-label limitation. Drop the confirmatory held-out claim. |
| **RQ2** Asking for clarification instead of guessing | Parser clarification F1 0.351 (Ch. 4). JAI asks for missing details before preparing a change (tested workflow); the fine-tuning test set has "vague request", "unknown person" and "I'm not sure" cases, with results for each round in `finetuning/RESULTS.md`. | **Partial, small samples** | Keep, answered with the parser figures plus the JAI cases, reported as exploratory. |
| **RQ3** AI-assisted vs manual entry with participants | None. No study approval, no participants. | **No evidence** | Move to future work, unless a small pilot (3–5 administrators) can still be approved and run before the deadline. |
| **RQ4** Comparing candidate LLMs (accuracy, latency, cost) | Strongest model evidence in the project: the base local model vs fine-tuned v1, v2, v3 on the same held-out JAI questions (automatic checks, latency per answer), plus a blind human rating of v1 vs v3 (274 vs 244 of 380). Cost is zero per call (local); training ran on a free GPU. | **Answerable if reframed** | Reframe from "cloud LLMs" to "a locally hosted base model vs the same model fine-tuned on reviewed, guide-grounded examples". Add round 4 if it finishes in time. |
| **Engineering question** validator and approval keep the model honest | Ch. 4: department and university scale timetables, exams, repair diagnosis, reports, 393+71+47 tests (now more). JAI never executes a change without confirmation; replies are cleaned (repetition, cut-off, wrong-language rewrite, Chinese-drift cut). | **Well supported** | Keep; update test counts and add the JAI safeguards. |

## Work done since 8 November that the thesis does not mention

- The JAI chat assistant: built-in answers, the local model, one confirmed website action at a time.
- The verified guide (`backend/app/assistant_guide.py`, 25 entries) and its effect on the base model.
- Three fine-tuning rounds (QLoRA on Qwen2.5-7B, free Colab/Kaggle GPU, merge into Ollama), including the round that made things worse and why (`finetuning/RESULTS.md`).
- The blind human rating, and the live test of v3 with its failures (poem, topic switch, Arabic vocabulary, Chinese drift).
- The Arabic display fix for mixed Arabic/English text, and the Arabic-reply rewrite.

## Statements in `main.tex` that are now inconsistent

- Scope lists examination timetabling and repair suggestions as *deferred*, but Chapter 4 reports both as implemented.
- Methodology says "No fine-tuning (outside initial scope)".
- Chapter 3 is titled "(proposed)" and has 21 `[TBD]` items. "Organisation of the thesis" says later chapters are not drafted.
- The title page has the month `[TBD]`, and the abstract is `[TBD]`.

## Decisions needed (supervisor)

1. Accept reframing RQ1 to development-level evidence, and RQ4 to base vs fine-tuned local model?
2. RQ3: future work, or a small pilot (who, ethics approval, when)?
3. Does the JAI fine-tuning work become its own section/chapter, or part of RQ4?
4. Submission deadline, university template and length limit.

## Caution before reporting the local extraction run

The partial run scores 0 exact and decision accuracy 0.069 in *every* language. Identical figures across all four languages suggest a format or scoring mismatch rather than a real result, so the run must be checked before any number from it appears in the thesis.
