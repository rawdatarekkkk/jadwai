# JAI fine-tuning — results (first run 2026-11-21, guide 2026-11-22)

## What was done

- **Data:** 279 fictional examples in 93 families (English, Arabic, Egyptian Arabic): 210 train, 69 held out.
  180 rows teach conversation (explaining JadwAI, answering from timetable facts, asking one focused
  question, refusing off-topic requests, replying in the user's language). Approvals were a bulk owner
  approval, not an independent per-item review.
- **Training:** QLoRA (rank 16) on `Qwen/Qwen2.5-7B-Instruct`, 2 epochs, Google Colab T4
  (`colab_train.ipynb`). Average training loss 1.62.
- **Merge:** the adapter was merged on the Mac into Ollama's own `qwen2.5:7b-instruct` weights
  (`merge_candidate.sh`). A first merge back to Q4 silently erased ~98% of the training: the change is
  only ~0.5% per weight and snapped back onto the same quantization grid. Fixed by re-quantizing each
  tensor to a different grid (Q4_K→Q6_K, Q6_K→Q5_K); `check_merge.py` confirms ~95% of the training
  is present in every trained matrix. Result: `jai-candidate` (6.1 GB).
- **Repetition fix (withdrawn):** `jai-candidate-rp` added `repeat_penalty 1.15`. It stopped loops but made
  the model return empty replies, so it was removed; repetition is now handled in the app (see below).

## Results on held-out cases (never seen in training)

Same prompts as the live chat (built by the production `facts()` code), temperature 0, this Mac (CPU).

| Action picking (5 cases) | Original | Tuned |
|---|---|---|
| Correct action / correctly no action | 3 | **5** |

The original wrongly chose "edit user" for an unknown person and "edit workspace" for a discussion question.

| Conversation (16 cases) | Original | Tuned | Tuned + repeat penalty* |
|---|---|---|---|
| Valid answer | 16 | 14 | 6/6 |
| No wrong action | 13 | 13 | 6/6 |
| Reply in the user's language | 15 | 12 | 6/6 |
| ≤ 80 words | 15 | 9 | 6/6 |
| Mean seconds per answer | 290 | 314 | ~190 |

\* Re-run only on the 6 cases that failed for the tuned model, so not directly comparable to the full 16.

## What improved

- **Egyptian Arabic.** The original answers in formal Arabic, once in Chinese and sometimes mixes in English.
  The tuned model answers in Egyptian dialect ("البيانات بتتحفظ على السيرفر ده").
- **Stays on topic.** Asked for a poem about exams, the original wrote a 120-word poem. The tuned model
  declines and offers to explain the exam workflow.
- **Short clarifying questions.** "This is useless, nothing works" → original proposes editing records and
  chooses a database update; tuned asks "Which part is not working, and what happens instead?"
- **Fewer unsafe actions.** It no longer reaches for update/lock/publish operations during discussions
  (action picking 5/5 vs 3/5).

## What is still wrong

- **Invented facts.** Both models still invent details: "hosted by a third-party provider",
  "212! possibilities", instructors "can edit" the published timetable, made-up solver timings.
  The training taught tone and behaviour more than JadwAI's facts.
- **Repetition loops** in long Arabic answers (now reduced in the app, see the second evaluation).
- **Occasional wrong language / off-topic** (2 Arabic questions answered in English by the tuned model).
- Small sample: 16 + 5 cases, synthetic labels, automatic checks only. Reply quality still needs the
  blind human rating in `runs/rating-sheet-20261121.md` (key in `rating-sheet-20261121.key.json`).

## Second evaluation: verified guide + reply safeguards (2026-11-22)

Changes made in the app, no retraining:
- `backend/app/assistant_guide.py`: 16 short, code-checked statements about how JadwAI works. The (at most 3)
  entries matching the user's message are put into the prompt as `facts.guide`, and the system prompt tells
  JAI to use only those facts for questions about JadwAI and to say it is not sure otherwise.
- `clean_reply` drops repeated sentences; `salvage_reply` keeps the complete sentences of a reply that was
  cut off mid-loop instead of failing. No repeat penalty.

Same 16 held-out conversation cases, both models with the guide (`runs/*-guide-conversation-20261122.jsonl`):

| Conversation (16 cases) | Original + guide | Tuned + guide |
|---|---|---|
| Valid answer | 16 | 16 |
| No wrong action | 15 | **16** |
| Reply in the user's language | **16** | 13 |
| ≤ 80 words | 14 | **16** |
| Mean seconds per answer | 198 | **135** |

What the guide fixed:
- **English answers are now correct.** Privacy, room features, solver time (30 s / 4 workers, 240 s / 8),
  and portals are answered with the verified facts instead of invented ones (no "third-party provider",
  no "instructors can edit"). This holds for both models; the tuned one follows the guide more closely.
- **No empty replies and no broken JSON** in either run.
- The tuned model still refuses off-topic requests and asks short clarifying questions; the original
  still wrote a 117-word poem and proposed a lock for a discussion question.

What is still wrong (tuned model, Arabic only):
- **Arabic answers still invent things** — a "daily backup", "Add session / Edit session" buttons — and
  repeat near-identical phrases that the exact-repeat filter cannot catch.
- **3 of 8 Arabic questions answered in English** (it copies the English guide text).
- The original model answers Arabic correctly in language but in formal Arabic and with some invented
  details of its own ("212 sessions" reasoning, offering to delete a session).

Why: the model was trained without `facts.guide` in its prompts, so it never learned to translate and
stick to it in Arabic. The training data has now been rebuilt with the guide in every prompt.

## Second training round (2026-11-22): guide in prompts, 3 epochs — worse

Same 210 approved rows rebuilt with `facts.guide` in the prompts (`exports/reviewed-v2`), 3 epochs,
final loss 1.11 (was 1.62). Merged as `jai-candidate-v2`; `check_merge.py`: 95–97% of the training kept.

| Conversation (16 cases), all with the guide | Original | Tuned v1 | Tuned v2 |
|---|---|---|---|
| Valid answer | 16 | 16 | 16 |
| No wrong action | 15 | **16** | 15 |
| Reply in the user's language | **16** | 13 | 12 |
| ≤ 80 words | 14 | **16** | 12 |
| Mean seconds per answer | 198 | **135** | 237 |

Action picking (5 cases): v2 5/5, same as v1.

v2 invents *more*, not less: "snapshots on the cloud", "8 workers / 16 workers", "the solver picks the room
with the fewest sessions", and it answered the exam-poem request with made-up exam facts instead of declining.
One Arabic reply broke into an unwanted record-edit action.

Why: the training answers were written before the guide existed and were not changed, so the model was
trained to see the guide and then answer in its own words anyway. More epochs on the same 210 rows mainly
made it memorise those answers (lower loss) while generalising worse. Training cannot teach "use the guide"
unless the target answers actually follow the guide.

## Third training round (2026-11-23): guide-grounded answers, 2 epochs — mixed, slightly better

Rewritten data (`exports/reviewed-v3`: 243 training rows, 222 with the guide, 6 "I'm not sure" rows),
2 epochs on a Kaggle T4, final loss 1.18. Merged as `jai-candidate-v3`; `check_merge.py`: 94–97% kept.
v1 was re-run on the same prompts (the guide changed), so both columns use identical questions.

| Conversation (16 cases), all with the guide | Tuned v1 | Tuned v3 |
|---|---|---|
| Valid answer | 16 | 16 |
| No wrong action | 16 | 16 |
| Reply in the user's language | 13 | **14** |
| ≤ 80 words | **16** | 14 |
| Mean seconds per answer | **308** | 358 |

Action picking (5 cases): v3 4/5. It chose to publish the *teaching* timetable when the user was on an
exam timetable and said "publish it"; v1 got this right. Treat as a regression to fix with more exam rows.

Held-out "can JadwAI pull students from the university system?" (3 wordings, new family, never trained):
neither model opens with "I'm not sure". v3 is closer in English (says it has no verified information
and points to CSV import), but one English reply invents "I would prepare the connection" and the Arabic
reply drifts to an unrelated topic. v1 states "no" and adds invented details (a firewall, "cannot add groups").

Read by hand:
- Better in v3: no looping in Arabic replies; a fed-up user gets an apology and a question; the Arabic
  privacy question is answered in Arabic (v1 answered in English); for "no classes at 8:30" v1 claimed
  8:30 sessions are forbidden, v3 correctly says there is no mandatory rule against them; it says
  "I am not sure" instead of inventing a feasibility result.
- Still wrong in both: the exam-poem request is not declined (v1 offers to write it, v3 talks about
  exams); one Arabic shared-lecture answer invents details; some Arabic drifts to other dialects.

Blind side-by-side sheet for a human rater (19 cases, key kept separately):
`runs/rating-sheet-v1-v3-20261123.md` / `.key.json`.

Blind rating (filled in by the project owner 2026-11-23, who had read a short summary of some replies
beforehand; scores 1–5 on correct, logical, helpful, natural, so 20 per case):

| | Tuned v1 | Tuned v3 |
|---|---|---|
| Total (19 cases, max 380) | 244 | **274** |
| Mean per case (max 20) | 12.8 | **14.4** |
| Correct / logical / helpful / natural | 3.3 / 3.3 / 3.1 / 3.2 | **3.7 / 3.6 / 3.6 / 3.5** |
| Cases won | 3 | **8** (8 ties) |

Biggest v3 gains are Arabic (privacy 8→16, search time 12→18, no early classes 7→20). Six cases scored
4/20 for both models (poem request, shared lectures, fed-up user in Arabic, crowded draft, special rooms
in Arabic): these are the targets for the next round.

## Recommendation

Not ready to replace the production model for Arabic users. For an English demo, `jai-candidate` with the
guide is clearly better (`JADWAI_LOCAL_MODEL=jai-candidate` in `.env`, restart the API; roll back with
`qwen2.5:7b-instruct`). The guide and safeguards also improve the original model, so they help either way.

Keep `jai-candidate` (v1) with the guide; do not use `jai-candidate-v2`. `jai-candidate-v3` is a modest
improvement in conversation (less looping, fewer invented facts) but picked the wrong publish action once;
the blind rating prefers v3 (274 vs 244 of 380), so v3 is the candidate to try with the guide.

Next training round, most valuable first:
1. ~~Rewrite the explanation answers so every JadwAI fact comes from that row's `facts.guide`, plus
   "I'm not sure" rows.~~ Done 2026-11-22: 9 guide entries added (25 in total), 11 answers rewritten,
   4 new families, 23 formal-Arabic wordings; the builder now checks guide coverage. Trained as v3 (above).
2. More Arabic explanation examples (300–500 rows in total), new families rather than paraphrases.
3. Polite-decline rows for off-topic requests (poems etc.) and more exam-timetable action rows.
   Round 4 (2026-11-23), aimed at the v3 live-test failures: 26 new families / 87 rows (off-topic
   declines, topic switches with history, Arabic room/lab explanations, exam-timetable publish actions;
   4 held-out test families, one per failure). `switch-complaint-to-import` was dropped at review.
   Bulk-approved by the owner after reading `data/CHANGES-round4.md` (not row by row) and **exported as
   `exports/reviewed-v4`** (317 train / 85 test rows, 95 / 28 families, hashes verified). Not trained yet.
4. Back to 2 epochs unless there is much more data; compare with the same evaluation and the blind rating.
