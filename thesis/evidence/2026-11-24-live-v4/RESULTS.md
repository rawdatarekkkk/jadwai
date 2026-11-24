# Live chat test: v4 on the four v3 live questions (24 Nov 2026)

App on 127.0.0.1:5180 started with `JADWAI_LOCAL_MODEL=jai-candidate-v4` for this run only (`.env` unchanged, it
names `jai-candidate-v3`), code at commit 947b018, demo workspace, CPU laptop. The four questions are the ones
asked of `jai-candidate-v3` in one chat on 23 Nov 2026 (taken from the app's `assistant_message` table), in the
same order and in one chat, plus the exam publish request. Script: `ask_live.py`; raw replies: `replies.jsonl`.

| Question | v3, 23 Nov | v4, 24 Nov | Time (v4) |
|---|---|---|---|
| المعمل اللي محتاج GPU بيتحط في أنهي قاعة؟ | Wrong words for rooms ("moons", "pens"); asks which room | Correct rule (all required features, enough seats, suitable type), then drifts into a repeated sentence about the solver and room availability | 347 s |
| write me a poem about exams | Wrote a poem | Declines and offers exam-timetable help | 214 s |
| زهقت، مفيش حاجة شغالة | Drifted into Chinese mid-sentence | Stays in Egyptian Arabic, but no acknowledgement; continues the exam topic of the previous turn, partly incoherent | 596 s |
| can JadwAI pull students straight from the university system? | Asked for a rule ID from the earlier topic | Asks for "the CSV contents in the request body"; points towards CSV import but in internal terms and without saying no | 550 s |
| ممكن تنشر جدول الامتحانات؟ (added) | not asked | Built-in route (no model): lists the unpublished exam drafts and asks which one | 2 s |

Read by hand: v4 fixed the poem and the Chinese drift and used correct room vocabulary; topic changes within one
chat are still weak (two replies carry over the previous topic) and the reply safeguard did not remove a
near-duplicate sentence. Single run, one rater (the agent), not blind.
