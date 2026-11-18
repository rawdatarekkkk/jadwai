# Lecture order

The global mandatory `lecture_before_tutorial` rule requires every weekly lecture to finish before any tutorial of the same catalogue course for overlapping student groups. The teaching calendar defines week order. Same-day adjacency is allowed; labs and unrelated courses are unaffected. Legacy activities without a catalogue reference match by exact course name and overlapping groups.

The parser recognises “a lecture should be before a tutorial in any schedule”. Save and approve the resulting rule to enable it. The current test workspace has this rule approved at the user’s request.

Full generation, regeneration and combined partial drafts enforce the rule in CP-SAT. Partial scope automatically includes prerequisite lectures; carried-over sessions are constrained too. Independent validation checks chronological precedence and identifies violating sessions. Existing saved timetables are historical snapshots and need regeneration after approval.

Migration 0034 extends rule constraints. Downgrade refuses to discard ordering rules. The local model shares the updated extraction schema and instructions; the built-in parser handles the reported sentence without a model call.
