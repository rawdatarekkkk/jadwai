# Automated label check, 28 November 2026

Bundle `0.2.1-draft`, guide v2.1: 144 labels in 36 families. This is an automated consistency check by the project assistant (an AI), **not a human review**. It does not change `review_status` or any label.

## 1. Mechanical checks (script, all 144 labels)

Schema and context validation (`development.py validate`) passes. On top of that the script checks: decision matches content; codes are current guide codes; IDs, days and hours fit the context; rule strength matches rule type; locks point at the context draft; English clock times match the proposal hours; the four translations of a family share one label; families with the same proposal pattern share codes.

- Labels with a mechanical flag: **0** of 144
- Families whose four translations disagree: **0**
- Same proposal pattern, different codes: **1**
  - conflict with activity_allowed, group_unavailable: `family-022` → hard_window_has_no_placement; `design-family-012` → resolve_hard_conflict

## 2. Reading against the guide (AI judgement, all 36 families)

Families: 33 agree with the draft label, 2 disagree, 1 ambiguous. Labels in families that do not agree: 12 of 144.

| Family | Verdict | Part | Note |
|---|---|---|---|
| `family-022` | disagrees | code | Same situation as design-family-012 (an activity's only permitted window fully covered by a mandatory closure of its group), but labelled hard_window_has_no_placement while design-family-012 uses resolve_hard_conflict. A method cannot know which code is expected. One of the two families should change so both use one code, as v2.1 did for missing_day. |
| `design-family-012` | disagrees | code | See family-022: same pattern, different clarification code. |
| `design-family-009` | ambiguous | decision | Unlike family-020, the statement does not say 'exactly' or 'do not round'. A room closure of 10:00-12:00 blocks exactly the same teaching period (10:15-11:45) because adjoining intervals do not overlap, so 'ready' with room_unavailable 10-12 is a defensible reading. The guide says not to round, so 'unsupported' follows the guide; a human should confirm the guide rule is intended for this case. |
| `family-004` | agrees | – | arz uses 'حاسبات' and ar 'بالسنة الثانية علوم حاسب', neither an exact context alias; the meaning is clear, but resolution relies on paraphrase, not the alias list. |
| `design-family-003` | agrees | – | ar says 'حضور المحاضرات' (attend lectures), narrower than 'classes' in en/arz/mixed; a reader could take it to exclude labs or tutorials. |
| `design-family-007` | agrees | – | Also gives no day; undefined_early alone is enough because no time can be built until 'early' is defined, but a method that also asks for a day is not wrong in spirit. |

All other families: agrees, no note.

## What this can and cannot support

It can support: "An automated check of all 144 development labels found no schema, context or cross-language inconsistencies; an AI reading against the guide flagged one pair of families with inconsistent codes and one ambiguous family." It cannot support any claim that labels were human-reviewed, verified or adjudicated. The reading was done by the same assistant that drafted the labels and the guide, so it shares their blind spots. Corrections, if made, go into a new bundle version with a correction log.
