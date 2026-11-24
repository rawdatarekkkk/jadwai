# Research questions against the evidence (23 November 2026)

Working note for agreeing the final scope with the supervisor. It changes nothing in `main.tex`.
"Evidence" means something measured and kept in the repository; plans and passing software tests are listed separately.

## Summary

| Question (as in `main.tex`) | Evidence that exists | Status | Suggested action |
|---|---|---|---|
| **RQ1** LLM extraction of formal constraints from natural language | Rule-based baseline on 144 development statements (Ch. 4: 0.326 exact, decision accuracy 0.597). Local `qwen2.5:7b-instruct`, two full runs (Results, Section evidence-llm): application prompt 0.090 exact, decision 0.479, 18/144 valid; contract prompt 0.167 exact, decision 0.556, 122/144 valid. Parser still higher; intervals overlap for exact and decision accuracy. GPT-5.4 mini adapter built, never called (no budget). Labels are draft; no human annotation submitted. | **Not answerable as designed** | Reframe as a development-level comparison (done: parser vs local model with two prompts, draft-label limitation stated). Drop the confirmatory held-out claim. |
| **RQ2** Asking for clarification instead of guessing | Parser clarification F1 0.351; local model 0.000 (application prompt) and 0.104 (contract prompt), which recognised 25/44 clarify cases but also asked on 16/76 clear ones. JAI asks for missing details before preparing a change (tested workflow); the fine-tuning test set has "vague request", "unknown person" and "I'm not sure" cases, with results for each round in `finetuning/RESULTS.md`. | **Partial, small samples** | Keep, answered with the parser figures plus the JAI cases, reported as exploratory. |
| **RQ3** AI-assisted vs manual entry with participants | None. No study approval, no participants. | **No evidence** | Move to future work, unless a small pilot (3–5 administrators) can still be approved and run before the deadline. |
| **RQ4** Comparing candidate LLMs (accuracy, latency, cost) | Strongest model evidence in the project: the base local model vs fine-tuned v1, v2, v3, v4 on the same held-out JAI questions (automatic checks, latency per answer), plus a blind human rating of v1 vs v3 (274 vs 244 of 380). Cost is zero per call (local); training ran on a free GPU. | **Answerable if reframed** | Reframe from "cloud LLMs" to "a locally hosted base model vs the same model fine-tuned on reviewed, guide-grounded examples". Round 4 added (v4: same as v3 on old cases, all replies ≤ 80 words, 13 new held-out cases within 1–2 of v3; exam publishing in conversation still missed). Blind rating v3 vs v4: 461 vs 524 of 640 (v4 wins 14, v3 6, 12 ties). Exam publishing moved to a built-in route. |
| **Engineering question** validator and approval keep the model honest | Ch. 4: department and university scale timetables, exams, repair diagnosis, reports, 558+106+50 tests (24 Nov). JAI never executes a change without confirmation; replies are cleaned (repetition, cut-off, wrong-language rewrite, Chinese-drift cut). | **Well supported** | Keep; add the JAI safeguards. |

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
