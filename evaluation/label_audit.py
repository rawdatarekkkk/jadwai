"""Human audit of a sample of the draft development labels.

build: writes a two-part review sheet for one statement per intent family
       (36 statements, 9 per language), plus a key file.
       Part A is blind (no draft label shown); Part B shows the draft label to judge.
score: reads the filled sheets and reports agreement with the draft labels.

The sheets are filled in by a person. This script never fills them in.

    python evaluation/label_audit.py build [--out DIR]
    python evaluation/label_audit.py score [--out DIR]
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE / "development-v2.1"
DEFAULT_OUT = HERE / "label-audit" / "2026-11-24"
SEED = 42
LANGS = ["en", "ar", "arz", "mixed"]
LANG_NAME = {"en": "English", "ar": "Formal Arabic", "arz": "Egyptian Arabic", "mixed": "Mixed Arabic/English"}
CONTEXT_NAME = {"synthetic-dept-v1": "Context 1 (department)", "synthetic-design-school-v2": "Context 2 (design school)"}
DECISIONS = ["ready", "clarify", "unsupported", "conflict", "mixed"]
VERDICTS = ["correct", "wrong", "ambiguous"]

CODE_MEANING = {
    "ambiguous_group": "the group name matches more than one group",
    "ambiguous_instructor": "the name matches more than one instructor",
    "day_required": "a time is given but no weekday",
    "hard_window_has_no_placement": "the hard rules leave the class no possible time",
    "historical_context_required": "it refers to earlier rules that are not in the context",
    "operation_required_for_negated_closure": "a double negative: unclear whether to add availability, remove a rule or do nothing",
    "resolve_hard_conflict": "two hard rules contradict each other; ask which one to keep",
    "rule_type_and_strength_required": "who and when are given, but not what kind of rule or how strict",
    "time_window_required": "a day is given but no hours",
    "undefined_early": "\"early\" has no defined meaning in the context",
    "unknown_instructor": "the person is not in the context",
    "hard_capacity_relaxation_not_supported": "ignoring room capacity cannot be expressed",
    "hard_weekly_cap_under_overtime_policy": "this context allows overtime; a hard cap at 12 hours is outside what may be proposed",
    "manual_rule_minute_precision_not_supported": "rules store whole hours only; minute times must not be rounded",
}


def load():
    cases = [json.loads(line) for line in (BUNDLE / "cases.jsonl").open(encoding="utf-8")]
    contexts = {c["id"]: c for c in json.loads((BUNDLE / "contexts.json").read_text(encoding="utf-8"))}
    return cases, contexts


def sample(cases):
    """One statement per family; languages rotated within each context (seeded)."""
    by_family = collections.defaultdict(dict)
    family_context = {}
    for c in cases:
        by_family[c["family_id"]][c["language"]] = c
        family_context[c["family_id"]] = c["context_id"]
    rng = random.Random(SEED)
    chosen = []
    for ctx in sorted(set(family_context.values())):
        fams = sorted(f for f, cx in family_context.items() if cx == ctx)
        rng.shuffle(fams)
        for i, fam in enumerate(fams):
            chosen.append(by_family[fam][LANGS[i % 4]])
    rng.shuffle(chosen)
    return chosen


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def names(ctx):
    out = {}
    for key in ("instructors", "rooms", "groups", "activities"):
        for e in ctx.get(key, []):
            out[e["id"]] = e["name"]
    return out


def render_proposal(p, ctx):
    n = names(ctx)
    d = p["data"]
    if p["kind"] == "instructor_weekly_limit":
        return f"Weekly limit: {n.get(d['instructor_id'], d['instructor_id'])} at most {d['max_weekly_hours']} teaching hours per week"
    if p["kind"] == "assignment_lock":
        keep = [k for k in ("instructor", "time", "room") if d.get(f"keep_{k}")]
        return (f"Lock: {n.get(d['activity_id'], d['activity_id'])} occurrence {d['occurrence'] + 1} "
                f"from the context draft, keeping its {', '.join(keep)}")
    when = f"{d['day']} {d['start_hour']:02d}:00–{d['end_hour']:02d}:00"
    t = d["type"]
    if t == "unavailable":
        return f"Hard: {n[d['instructor_id']]} cannot teach {when}"
    if t == "preferred_period":
        return f"Preference: {n[d['instructor_id']]} prefers to teach {when}"
    if t == "room_unavailable":
        return f"Hard: {n[d['room_id']]} is closed {when}"
    if t == "group_unavailable":
        return f"Hard: {n[d['group_id']]} has no classes {when}"
    if t == "activity_allowed":
        return f"Hard: {n[d['activity_id']]} may only be scheduled inside {when}"
    if t == "group_allowed":
        return f"Hard: {n[d['group_id']]} may only have classes inside {when}"
    return json.dumps(p, ensure_ascii=False)


def render_gold(g, ctx):
    lines = [f"- Decision: **{g['decision']}**"]
    for p in g["proposals"]:
        lines.append(f"- {render_proposal(p, ctx)}")
    for code in g["clarifications"]:
        lines.append(f"- Ask: `{code}` ({CODE_MEANING.get(code, '?')})")
    for code in g["unsupported"]:
        lines.append(f"- Not supported: `{code}` ({CODE_MEANING.get(code, '?')})")
    return "\n".join(lines)


def render_context(ctx):
    cal = ctx["calendar"]
    periods = ", ".join(f"{hhmm(p['start'])}–{hhmm(p['end'])}" for p in cal["teaching_periods"])
    lines = [f"### {CONTEXT_NAME[ctx['id']]}", "",
             f"- Teaching days: {', '.join(cal['days'])}; day runs {cal['start_hour']:02d}:00–{cal['end_hour']:02d}:00; "
             f"teaching periods {periods}."]
    if "weekly_load_policy" in cal:
        w = cal["weekly_load_policy"]
        lines.append(f"- Weekly load: {w['standard_hours']} regular teaching hours, overtime "
                     f"{'allowed' if w['allow_overtime'] else 'not allowed'}.")
    for key, label in (("instructors", "Instructors"), ("rooms", "Rooms"), ("groups", "Groups")):
        items = []
        for e in ctx[key]:
            extra = f" ({' / '.join(e['aliases'])})" if e.get("aliases") else ""
            if key == "rooms":
                extra += f", capacity {e['capacity']}"
            if key == "groups":
                extra += f", {e['size']} students"
            items.append(f"{e['name']}{extra}")
        lines.append(f"- {label}: " + "; ".join(items) + ".")
    n = names(ctx)
    for a in ctx["activities"]:
        lines.append(f"- Activity: {a['name']} ({' / '.join(a['aliases'])}), for "
                     f"{', '.join(n[g] for g in a['group_ids'])}, taught by "
                     f"{', '.join(n[i] for i in a['eligible_instructors'])}, {a['sessions']} × {a['duration']} min per week.")
    draft = ctx["source_draft"]
    if draft["assignments"]:
        for s in draft["assignments"]:
            lines.append(f"- Context draft timetable: {n[s['activity_id']]} occurrence {s['occurrence'] + 1} on "
                         f"{s['day']} {hhmm(s['start_minute'])}–{hhmm(s['end_minute'])} in {n[s['room_id']]} with {n[s['instructor_id']]}.")
    else:
        lines.append("- Context draft timetable: empty.")
    lines.append("- \"Early\" is not defined. Rules store whole hours only. The people, rooms and groups above are the only ones that exist.")
    if ctx["definitions"].get("proposal_boundary"):
        lines.append(f"- Boundary: {ctx['definitions']['proposal_boundary']}")
    return "\n".join(lines)


GUIDE_SUMMARY = """## What the labels mean (annotation guide v2.1, short version)

- **ready**: every part becomes a supported rule; nothing is missing.
- **clarify**: something must be asked first (missing day or hours, unknown or ambiguous name, undefined word like "early", reference to rules not in the context). Never guess.
- **unsupported**: the request cannot be expressed faithfully (minute times, ignoring room capacity, a hard weekly cap where overtime is allowed). Never approximate.
- **conflict**: understood, but the hard rules cannot all hold. Keep the rules and ask which to change.
- **mixed**: some parts are ready and some need a question or are unsupported.

Supported rules: instructor cannot teach (hard) / prefers (soft); room closed; group has no classes; activity or group "only inside" a window; weekly teaching-hour limit for an instructor; locking a session of the context draft. Times are whole hours. "Before 10:00" starts at 08:00; "the whole day" is 08:00–18:00. Several "only inside" windows for the same item are alternatives. A hard closure plus a soft preference is not a conflict. Four 90-minute sessions = 6 teaching hours.
"""


def build(out: Path):
    cases, contexts = load()
    chosen = sample(cases)
    out.mkdir(parents=True, exist_ok=True)
    key = []
    ctx_block = "\n\n".join(render_context(contexts[c]) for c in sorted(contexts))
    a = [
        "# Label audit, Part A (blind): what should the answer be?",
        "",
        "Fill this in **before** opening Part B. Do not look up the statements in `cases.jsonl`.",
        "For each statement: tick one decision (change `[ ]` to `[x]`) and write in one line what the answer should be:",
        "the rules (who, day, hours, hard or preference), or what must be asked, or why it is not supported.",
        "Use the context of the statement only. About 1 minute per statement.",
        "",
        GUIDE_SUMMARY,
        "## The two contexts",
        "",
        ctx_block,
        "",
        "## Statements",
        "",
    ]
    b = [
        "# Label audit, Part B: is the draft label right?",
        "",
        "Open this only after Part A is complete. For each statement, judge the draft label against the guide and context:",
        "",
        "- **correct**: this is the right answer.",
        "- **wrong**: a decision, rule, value or code is wrong, missing or extra. Tick what is wrong and write the right answer.",
        "- **ambiguous**: the statement honestly has more than one reasonable reading. Say which.",
        "",
        "You may change your mind from Part A; do not edit Part A afterwards.",
        "",
        GUIDE_SUMMARY,
        "## The two contexts",
        "",
        ctx_block,
        "",
        "## Statements",
        "",
    ]
    for i, c in enumerate(chosen, 1):
        sid = f"S{i:02d}"
        key.append({"sheet_id": sid, "case_id": c["id"], "family_id": c["family_id"],
                    "language": c["language"], "context_id": c["context_id"], "gold": c["gold"]})
        head = f"### {sid} · {CONTEXT_NAME[c['context_id']]} · {LANG_NAME[c['language']]}"
        quote = f"> {c['text']}"
        a += [head, "", quote, "",
              "Decision: " + "  ".join(f"[ ] {d}" for d in DECISIONS), "",
              "Answer: ", "",
              "Notes: ", "", "---", ""]
        b += [head, "", quote, "", "Draft label:", "", render_gold(c["gold"], contexts[c["context_id"]]), "",
              "Verdict: " + "  ".join(f"[ ] {v}" for v in VERDICTS), "",
              "If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code", "",
              "Right answer / note: ", "", "---", ""]
    (out / "part-a-blind.md").write_text("\n".join(a), encoding="utf-8")
    (out / "part-b-check.md").write_text("\n".join(b), encoding="utf-8")
    (out / "key.json").write_text(json.dumps({"bundle": "0.2.1-draft", "seed": SEED, "items": key},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
    counts = collections.Counter(c["language"] for c in chosen)
    decisions = collections.Counter(c["gold"]["decision"] for c in chosen)
    print(f"wrote {len(chosen)} statements to {out}")
    print("languages:", dict(counts))
    print("draft decisions:", dict(decisions))


SECTION = re.compile(r"^### (S\d\d)\b.*?$(.*?)(?=^### S\d\d\b|\Z)", re.M | re.S)


def ticked(block, label, options):
    m = re.search(rf"^{label}:(.*)$", block, re.M)
    if not m:
        return []
    return [o for o in options if re.search(rf"\[[xX]\]\s*{re.escape(o)}\b", m.group(1))]


def field(block, label):
    m = re.search(rf"^{label}:[ \t]*(.*?)(?=^\w[\w /]*:|^---|\Z)", block, re.M | re.S)
    return m.group(1).strip() if m else ""


def kappa(pairs, labels):
    n = len(pairs)
    if not n:
        return None
    po = sum(x == y for x, y in pairs) / n
    ca = collections.Counter(x for x, _ in pairs)
    cb = collections.Counter(y for _, y in pairs)
    pe = sum(ca[l] * cb[l] for l in labels) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def score(out: Path):
    key = {k["sheet_id"]: k for k in json.loads((out / "key.json").read_text(encoding="utf-8"))["items"]}
    a = {m.group(1): m.group(2) for m in SECTION.finditer((out / "part-a-blind.md").read_text(encoding="utf-8"))}
    b = {m.group(1): m.group(2) for m in SECTION.finditer((out / "part-b-check.md").read_text(encoding="utf-8"))}
    problems, rows = [], []
    for sid, k in key.items():
        da = ticked(a.get(sid, ""), "Decision", DECISIONS)
        vb = ticked(b.get(sid, ""), "Verdict", VERDICTS)
        if len(da) != 1:
            problems.append(f"{sid}: Part A needs exactly one decision (found {len(da)})")
        if len(vb) != 1:
            problems.append(f"{sid}: Part B needs exactly one verdict (found {len(vb)})")
        if vb == ["wrong"] and not field(b.get(sid, ""), "Right answer / note"):
            problems.append(f"{sid}: marked wrong but no right answer written")
        rows.append({**k, "reviewer_decision": da[0] if len(da) == 1 else None,
                     "verdict": vb[0] if len(vb) == 1 else None,
                     "wrong_parts": ticked(b.get(sid, ""), "If wrong", ["decision", "rule or value", "missing rule", "extra rule", "code"]),
                     "answer_a": field(a.get(sid, ""), "Answer"), "note_b": field(b.get(sid, ""), "Right answer / note")})
    if problems:
        print("Sheets not complete yet:")
        print("\n".join("  " + p for p in problems))
    done_a = [r for r in rows if r["reviewer_decision"]]
    pairs = [(r["reviewer_decision"], r["gold"]["decision"]) for r in done_a]
    agree = sum(x == y for x, y in pairs)
    report = {"statements": len(rows), "part_a_complete": len(done_a)}
    if pairs:
        report["decision_agreement"] = agree / len(pairs)
        report["decision_kappa"] = kappa(pairs, DECISIONS)
        report["confusion_reviewer_vs_draft"] = {f"{x} vs {y}": n for (x, y), n in collections.Counter(pairs).items() if x != y}
    done_b = [r for r in rows if r["verdict"]]
    report["part_b_complete"] = len(done_b)
    if done_b:
        v = collections.Counter(r["verdict"] for r in done_b)
        report["verdicts"] = dict(v)
        lo, hi = wilson(v["wrong"], len(done_b))
        report["wrong_rate"] = v["wrong"] / len(done_b)
        report["wrong_rate_95ci_wilson"] = [lo, hi]
        by_lang = collections.defaultdict(collections.Counter)
        for r in done_b:
            by_lang[r["language"]][r["verdict"]] += 1
        report["verdicts_by_language"] = {l: dict(by_lang[l]) for l in LANGS if l in by_lang}
        report["not_correct"] = [{"sheet_id": r["sheet_id"], "case_id": r["case_id"], "verdict": r["verdict"],
                                  "wrong_parts": r["wrong_parts"], "note": r["note_b"]}
                                 for r in done_b if r["verdict"] != "correct"]
    (out / "score.json").write_text(json.dumps({"report": report, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "score"])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()
    build(args.out) if args.cmd == "build" else score(args.out)


if __name__ == "__main__":
    main()
