"""Course-by-course and cohort-by-cohort comparison of a JadwAI run with the real GIU timetable.

Real cells name courses in short forms ("CS II", "RM", "ACC 9"); each is matched, within its cohort
(faculty and semester), to the JadwAI course whose name it fits best: whole words, word beginnings
("Math" -> "Mathematics"), initials ("RM" -> "Research Methodology") and roman numerals must agree.
Then, per matched course, the days and periods are compared; per cohort, the weekly pattern of
session-periods (6 days x 5 periods) is compared by cosine similarity.

    JADWAI_URL=... JADWAI_EMAIL=... JADWAI_PASSWORD=... python scripts/compare_giu_sessions.py REAL.xlsx --run RUN_ID [--out report.md]
"""
import argparse
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from read_giu_timetable import read, ROOM  # noqa: E402
from compare_giu_timetable import jadwai, DAYS  # noqa: E402

ROMAN = {'i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii'}
STOP = {'and', 'of', 'the', 'to', 'in', 'for', '&', 'lab', 'labs', 'lecture', 'tutorial', 'project'}


def course_text(text):
    t = ROOM.sub(' ', text)
    t = re.sub(r'\([^)]*\)', ' ', t)
    t = re.sub(r'(?:\b[TP]\s?|\blab\s+|\s)\d{1,2}(?:\s*/\s*\d{1,2})*\s*$', '', t.strip(), flags=re.I)
    return re.sub(r'\s+', ' ', t).strip(' -|/')


def words(name):
    return [w for w in re.findall(r'[a-z]+', name.lower()) if w not in STOP]


def score(real, cand):
    r, c = words(real), words(cand)
    if not r or not c:
        return 0.0
    rr, cr = {w for w in r if w in ROMAN}, {w for w in c if w in ROMAN}
    if rr and cr and rr != cr:  # numerals must agree only when both names have one
        return 0.0
    plain_c = [w for w in c if w not in ROMAN]
    # Initials of any run of consecutive words: "CS" -> Computer Science, "RM" -> Research Methodology.
    runs = {''.join(x[0] for x in plain_c[i:j]) for i in range(len(plain_c)) for j in range(i + 2, len(plain_c) + 1)}
    hit = 0
    for w in (w for w in r if w not in ROMAN):
        if w in plain_c or (len(w) >= 3 and any(x.startswith(w) or w.startswith(x[:max(3, len(x))]) for x in plain_c)) or (len(w) >= 2 and w in runs):
            hit += 1
    real_plain = [w for w in r if w not in ROMAN]
    return hit / len(real_plain) if real_plain else 0.0


def cosine(a, b):
    keys = set(a) | set(b)
    num = sum(a.get(k, 0) * b.get(k, 0) for k in keys)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('real'); ap.add_argument('--run', required=True); ap.add_argument('--out')
    args = ap.parse_args()
    real, _ = read(args.real)
    run_id, gen = jadwai(os.environ.get('JADWAI_URL', 'http://127.0.0.1:8012'), args.run)
    teach = [s for s in real if s['kind'] == 'teaching' and s['faculty'] and s['semester']]
    cands = defaultdict(set)
    gslots = defaultdict(set)
    for s in gen:
        for f, sem, _ in s['groups']:
            cands[(f, sem)].add(s['course'])
            gslots[(f, sem, s['course'])].add((s['day'], s['period']))
    match, unmatched = {}, Counter()
    for s in teach:
        name = course_text(s['text'])
        key = (s['faculty'], s['semester'], name)
        if key not in match:
            best = max(((score(name, c), c) for c in cands[(s['faculty'], s['semester'])]), default=(0, None))
            match[key] = best[1] if best[0] >= 0.6 else None
        if not match[key]:
            unmatched[key] += 1
    matched = [s for s in teach if match[(s['faculty'], s['semester'], course_text(s['text']))]]
    rslots = defaultdict(set)
    for s in matched:
        rslots[(s['faculty'], s['semester'], match[(s['faculty'], s['semester'], course_text(s['text']))])].add((s['day'], s['period']))
    pairs = sorted(set(rslots) & set(gslots))
    same_day = [len({d for d, _ in rslots[k]} & {d for d, _ in gslots[k]}) / len({d for d, _ in rslots[k]}) for k in pairs]
    same_slot = [len(rslots[k] & gslots[k]) / len(rslots[k]) for k in pairs]
    # Cohort weekly pattern
    rc, gc = defaultdict(Counter), defaultdict(Counter)
    for s in teach:
        rc[(s['faculty'], s['semester'])][(s['day'], s['period'])] += 1
    for s in gen:
        for f, sem, _ in s['groups'][:1]:
            gc[(f, sem)][(s['day'], s['period'])] += 1
    cohorts = sorted(set(rc) & set(gc), key=str)
    sims = {k: cosine(rc[k], gc[k]) for k in cohorts}
    day_sims = {k: cosine(Counter({d: sum(v for (dd, _), v in rc[k].items() if dd == d) for d in DAYS}),
                          Counter({d: sum(v for (dd, _), v in gc[k].items() if dd == d) for d in DAYS})) for k in cohorts}
    lines = [f'# Course by course: JadwAI run `{run_id}` and the real timetable', '',
             f'Real teaching cells in cohorts with a semester: {len(teach)}. Matched to a JadwAI course: {len(matched)} '
             f'({100 * len(matched) / len(teach):.0f}%), {len(pairs)} course-cohort pairs. Unmatched cells: {sum(unmatched.values())} '
             f'(most common: {", ".join(f"{n} ({c})" for (f, sem, n), c in unmatched.most_common(8))}).', '',
             '## Same days and periods, per matched course', '',
             '| | Mean over courses | Courses where all real days are also JadwAI days | Courses with no day in common |', '|---|---|---|---|',
             f'| Real days that JadwAI also uses for the course | {100 * statistics.mean(same_day):.0f}% | {sum(1 for x in same_day if x == 1)} of {len(pairs)} | {sum(1 for x in same_day if x == 0)} |',
             f'| Real (day, period) slots that JadwAI also uses | {100 * statistics.mean(same_slot):.0f}% | {sum(1 for x in same_slot if x == 1)} of {len(pairs)} | {sum(1 for x in same_slot if x == 0)} |', '',
             'For comparison: with 6 days, a course placed on random days would share a given day about 1 time in 6 (17%), '
             'and a given (day, period) slot about 1 time in 30 (3%) per session.', '',
             '## Weekly pattern per cohort (cosine similarity, 1 = identical shape)', '',
             '| Cohort | Days only | Days and periods |', '|---|---|---|']
    lines += [f'| {f} sem {sem} | {day_sims[(f, sem)]:.2f} | {sims[(f, sem)]:.2f} |' for f, sem in cohorts]
    lines += ['', f'Mean: days only {statistics.mean(day_sims.values()):.2f}, days and periods {statistics.mean(sims.values()):.2f}.', '',
              '## Least similar courses (real slots shared)', '', '| Cohort | Course | Real days | JadwAI days | Shared slots |', '|---|---|---|---|---|']
    worst = sorted(pairs, key=lambda k: (len(rslots[k] & gslots[k]) / len(rslots[k]), -len(rslots[k])))[:12]
    short = lambda cells: ', '.join(d[:3] for d in DAYS if d in {x for x, _ in cells})
    lines += [f'| {f} {sem} | {c[:40]} | {short(rslots[(f, sem, c)])} | {short(gslots[(f, sem, c)])} | {len(rslots[(f, sem, c)] & gslots[(f, sem, c)])} of {len(rslots[(f, sem, c)])} |' for f, sem, c in worst]
    text = '\n'.join(lines)
    if args.out:
        Path(args.out).write_text(text)
    print(text)


if __name__ == '__main__':
    main()
