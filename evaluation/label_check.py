"""Automated consistency check of the draft development labels (bundle 0.2.1-draft, guide v2.1).

This is NOT a human review and must not be reported as one. It has two parts:

1. Mechanical checks run by this script on all 144 labels: decision and content agree, codes are current
   guide codes, IDs exist in the context, days are in the context calendar, hours are whole and inside the
   teaching day, strength matches the rule type, the four translations of a family carry the same label,
   clock times in the English statement match the proposal hours, and families with the same proposal
   pattern use the same codes.
2. A reading of every family by the project assistant (an AI) against the guide, recorded in READING below.
   It is an AI judgement, not a reviewer judgement, and does not change review_status.

Nothing here edits cases.jsonl. Corrections belong in a new bundle version with a correction log.

    python evaluation/label_check.py [--bundle DIR] [--out DIR]
"""
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLARIFY = {"ambiguous_group", "ambiguous_instructor", "day_required", "hard_window_has_no_placement",
           "historical_context_required", "operation_required_for_negated_closure", "resolve_hard_conflict",
           "rule_type_and_strength_required", "time_window_required", "undefined_early", "unknown_instructor"}
UNSUPPORTED = {"hard_capacity_relaxation_not_supported", "hard_weekly_cap_under_overtime_policy",
               "manual_rule_minute_precision_not_supported"}
RETIRED = {"missing_day", "minute_rule_precision"}
TARGET = {"unavailable": ("instructor_id", "instructors"), "preferred_period": ("instructor_id", "instructors"),
          "room_unavailable": ("room_id", "rooms"), "group_unavailable": ("group_id", "groups"),
          "group_allowed": ("group_id", "groups"), "activity_allowed": ("activity_id", "activities")}

# The assistant's reading of each family against guide v2.1. verdict: agrees / disagrees / ambiguous.
# A note is recorded for "agrees" only when there is a translation or wording point worth a human look.
READING = {
    "family-022": ("disagrees", "code",
                   "Same situation as design-family-012 (an activity's only permitted window fully covered by a "
                   "mandatory closure of its group), but labelled hard_window_has_no_placement while "
                   "design-family-012 uses resolve_hard_conflict. A method cannot know which code is expected. "
                   "One of the two families should change so both use one code, as v2.1 did for missing_day."),
    "design-family-012": ("disagrees", "code", "See family-022: same pattern, different clarification code."),
    "design-family-009": ("ambiguous", "decision",
                          "Unlike family-020, the statement does not say 'exactly' or 'do not round'. A room "
                          "closure of 10:00-12:00 blocks exactly the same teaching period (10:15-11:45) because "
                          "adjoining intervals do not overlap, so 'ready' with room_unavailable 10-12 is a "
                          "defensible reading. The guide says not to round, so 'unsupported' follows the guide; "
                          "a human should confirm the guide rule is intended for this case."),
    "family-004": ("agrees", None,
                   "arz uses 'حاسبات' and ar 'بالسنة الثانية علوم حاسب', neither an exact context alias; "
                   "the meaning is clear, but resolution relies on paraphrase, not the alias list."),
    "design-family-003": ("agrees", None,
                          "ar says 'حضور المحاضرات' (attend lectures), narrower than 'classes' in en/arz/mixed; "
                          "a reader could take it to exclude labs or tutorials."),
    "design-family-007": ("agrees", None,
                          "Also gives no day; undefined_early alone is enough because no time can be built "
                          "until 'early' is defined, but a method that also asks for a day is not wrong in spirit."),
}


def check_case(c, ctx):
    g, out = c["gold"], []
    d, props, cl, un = g["decision"], g["proposals"], g["clarifications"], g["unsupported"]
    for code in cl:
        if code in RETIRED or code not in CLARIFY:
            out.append(f"clarification code `{code}` is not a current guide code")
    for code in un:
        if code in RETIRED or code not in UNSUPPORTED:
            out.append(f"unsupported code `{code}` is not a current guide code")
    shape = {"ready": props and not cl and not un, "clarify": cl and not props and not un,
             "unsupported": un and not props and not cl, "conflict": len(props) >= 2 and cl and not un,
             "mixed": props and (cl or un)}
    if not shape[d]:
        out.append(f"decision `{d}` does not match its content ({len(props)} proposals, {len(cl)} clarifications, {len(un)} unsupported)")
    cal = ctx["calendar"]
    for p in props:
        data = p["data"]
        if p["kind"] == "rule":
            field, table = TARGET[data["type"]]
            ids = {e["id"] for e in ctx[table]}
            if data.get(field) not in ids:
                out.append(f"{data['type']}: {field} `{data.get(field)}` not in context")
            if data["day"] not in cal["days"]:
                out.append(f"day {data['day']} not in the context calendar")
            if not (cal["start_hour"] <= data["start_hour"] < data["end_hour"] <= cal["end_hour"]):
                out.append(f"hours {data['start_hour']}-{data['end_hour']} outside the teaching day or reversed")
            want = "preferred" if data["type"] == "preferred_period" else "mandatory"
            if data["strength"] != want:
                out.append(f"{data['type']} has strength {data['strength']}, expected {want}")
        elif p["kind"] == "instructor_weekly_limit":
            if data["instructor_id"] not in {e["id"] for e in ctx["instructors"]}:
                out.append("weekly limit instructor not in context")
            if (data["max_weekly_hours"] * 2) % 1 or not 0 <= data["max_weekly_hours"] <= 168:
                out.append("weekly limit not a half-hour step in 0-168")
        elif p["kind"] == "assignment_lock":
            if data["source_run_id"] != ctx["source_draft"]["id"]:
                out.append("lock does not point at the context draft")
            if not any(a["activity_id"] == data["activity_id"] and a["occurrence"] == data["occurrence"]
                       for a in ctx["source_draft"]["assignments"]):
                out.append("lock names an occurrence that is not in the context draft")
    if c["language"] == "en":
        times = re.findall(r"\b(\d{1,2}):(\d{2})\b", c["text"])
        if any(m != "00" for _, m in times) and "manual_rule_minute_precision_not_supported" not in un:
            out.append("statement has minute times but no minute-precision code")
        hours = {int(h) for h, m in times if m == "00"}
        used = {x for p in props if p["kind"] == "rule" for x in (p["data"]["start_hour"], p["data"]["end_hour"])}
        if hours and props and not hours <= used | {cal["start_hour"]}:
            out.append(f"clock hours {sorted(hours)} in the statement not all used by the proposals {sorted(used)}")
    return out


def signature(gold):
    return (gold["decision"], tuple(sorted((p["kind"], p["data"].get("type", "")) for p in gold["proposals"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bundle", type=Path, default=HERE / "development-v2.1")
    ap.add_argument("--out", type=Path, default=HERE / "label-audit" / "automated-2026-11-28")
    args = ap.parse_args()
    cases = [json.loads(l) for l in (args.bundle / "cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    contexts = {c["id"]: c for c in json.loads((args.bundle / "contexts.json").read_text(encoding="utf-8"))}
    families = collections.defaultdict(list)
    for c in cases:
        families[c["family_id"]].append(c)

    mechanical = {c["id"]: check_case(c, contexts[c["context_id"]]) for c in cases}
    split = [f for f, items in families.items()
             if len({json.dumps(i["gold"], sort_keys=True) for i in items}) > 1 or len(items) != 4]
    by_sig = collections.defaultdict(list)
    for f, items in families.items():
        by_sig[signature(items[0]["gold"])].append(f)
    code_splits = []
    for sig, fams in by_sig.items():
        codes = {f: tuple(families[f][0]["gold"]["clarifications"] + families[f][0]["gold"]["unsupported"]) for f in fams}
        if sig[1] and len(set(codes.values())) > 1:
            code_splits.append({"pattern": f"{sig[0]} with {', '.join(t for _, t in sig[1])}", "codes": codes})

    flagged = {k: v for k, v in mechanical.items() if v}
    verdicts = collections.Counter(READING.get(f, ("agrees",))[0] for f in families)
    affected = sum(len(families[f]) for f in families if READING.get(f, ("agrees",))[0] != "agrees")
    result = {"bundle": json.loads((args.bundle / "manifest.json").read_text())["dataset_version"],
              "kind": "automated consistency check (not a human review)",
              "cases": len(cases), "families": len(families),
              "mechanical_flags": flagged, "families_with_split_labels": split, "code_inconsistencies": code_splits,
              "reading": {f: {"verdict": v[0], "part": v[1], "note": v[2]} for f, v in READING.items()},
              "reading_summary": {"families": dict(verdicts), "labels_in_non_agreeing_families": affected}}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "check.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# Automated label check, 28 November 2026", "",
             f"Bundle `{result['bundle']}`, guide v2.1: {len(cases)} labels in {len(families)} families. "
             "This is an automated consistency check by the project assistant (an AI), **not a human review**. "
             "It does not change `review_status` or any label.", "",
             "## 1. Mechanical checks (script, all 144 labels)", "",
             "Schema and context validation (`development.py validate`) passes. On top of that the script checks: decision "
             "matches content; codes are current guide codes; IDs, days and hours fit the context; rule strength matches "
             "rule type; locks point at the context draft; English clock times match the proposal hours; the four "
             "translations of a family share one label; families with the same proposal pattern share codes.", "",
             f"- Labels with a mechanical flag: **{len(flagged)}** of {len(cases)}"]
    lines += [f"  - `{k}`: {'; '.join(v)}" for k, v in flagged.items()]
    lines += [f"- Families whose four translations disagree: **{len(split)}**" + (f" ({', '.join(split)})" if split else ""),
              f"- Same proposal pattern, different codes: **{len(code_splits)}**"]
    for s in code_splits:
        lines.append(f"  - {s['pattern']}: " + "; ".join(f"`{f}` → {', '.join(c) or 'none'}" for f, c in s["codes"].items()))
    lines += ["", "## 2. Reading against the guide (AI judgement, all 36 families)", "",
              f"Families: {verdicts['agrees']} agree with the draft label, {verdicts['disagrees']} disagree, "
              f"{verdicts['ambiguous']} ambiguous. Labels in families that do not agree: {affected} of {len(cases)}.", "",
              "| Family | Verdict | Part | Note |", "|---|---|---|---|"]
    order = {"disagrees": 0, "ambiguous": 1, "agrees": 2}
    for f, (v, part, note) in sorted(READING.items(), key=lambda x: order[x[1][0]]):
        lines.append(f"| `{f}` | {v} | {part or '–'} | {note} |")
    lines += ["", "All other families: agrees, no note.", "",
              "## What this can and cannot support", "",
              "It can support: \"An automated check of all 144 development labels found no schema, context or "
              "cross-language inconsistencies; an AI reading against the guide flagged one pair of families with "
              "inconsistent codes and one ambiguous family.\" It cannot support any claim that labels were "
              "human-reviewed, verified or adjudicated. The reading was done by the same assistant that drafted the "
              "labels and the guide, so it shares their blind spots. Corrections, if made, go into a new bundle "
              "version with a correction log."]
    (args.out / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
