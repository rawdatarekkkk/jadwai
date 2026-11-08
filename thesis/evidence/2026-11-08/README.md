# Evidence for Chapter 4 (8 November 2026)

Measured on an Intel Core i5-1038NG7 (4 cores, 8 threads), 16 GB, macOS 26.5.1, Python 3.14.5, OR-Tools 9.15.6755, 8 search workers, seed 42. Code: commits `e4771a1`, `4137b96` and the parser correction committed with this folder.

| File | What it is |
|---|---|
| `score_parser.py` | Runs the built-in parser on `evaluation/development-v2` and scores it with the project's scorer (family bootstrap, 1,000 replicates, seed 42). Run from the repository: `backend/.venv/bin/python thesis/evidence/2026-11-08/score_parser.py`. |
| `parser_score.json` | Its output for the reported run (after aligning the parser with annotation guide v2): full scorer result and every prediction. Labels are draft and unreviewed. |
| `parser_score_first_run.json` | The first run, before that alignment (Table 4.3, "First run"). |
| `university_parts.py`, `university_parts.log` | The six-part university-scale run and its log. Needs `fullsnap.json`, built offline from the filled Winter 2026 template, which is not included (institutional data). The script applies the documented adjustments (placeholder TAs and rooms, oversized lectures and idle TAs set aside, daily policies off with `nopolicy`). |
| `repair_demo.py` | The offline repair diagnosis on the 448-session demonstration snapshot (not included). |

The demonstration-workspace runs (Sections 4.2, 4.5 and 4.6) were made through the running application; their saved runs are in the demonstration database, not in this folder.
