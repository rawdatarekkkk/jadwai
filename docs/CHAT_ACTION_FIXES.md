# Chat action corrections

Exam generation calls POST /api/exam-schedules, retains the programme/year/group/course scope across date follow-ups, and sends selected catalogue course IDs. Shared courses retain their full participant lists. Unknown scopes and empty scoped course sets require clarification instead of generating for everyone. Explicit Friday, hall, invigilation, daily exam limit and second-chance options are preserved.

Chat reports incomplete or infeasible exam attempts as such and remembers the resulting exam ID. Exam publication follow-ups use that exam; exam unpublication is executable in chat.

Constraint requests use the same local interpreter as the Constraints page. The assistant previews the exact validated hard/soft rules; only human confirmation creates and approves them. Confirmation imports the reviewed proposal rather than reinterpreting changed text. This does not add the earlier first-slot constraint.

A contract regression checks literal chat HTTP routes against OpenAPI; the existing capability catalogue tracks non-credential website routes. File picking and credential entry still use their browser controls.
