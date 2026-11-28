# Label audit, Part B: is the draft label right?

Open this only after Part A is complete. For each statement, judge the draft label against the guide and context:

- **correct**: this is the right answer.
- **wrong**: a decision, rule, value or code is wrong, missing or extra. Tick what is wrong and write the right answer.
- **ambiguous**: the statement honestly has more than one reasonable reading. Say which.

You may change your mind from Part A; do not edit Part A afterwards.

## What the labels mean (annotation guide v2.1, short version)

- **ready**: every part becomes a supported rule; nothing is missing.
- **clarify**: something must be asked first (missing day or hours, unknown or ambiguous name, undefined word like "early", reference to rules not in the context). Never guess.
- **unsupported**: the request cannot be expressed faithfully (minute times, ignoring room capacity, a hard weekly cap where overtime is allowed). Never approximate.
- **conflict**: understood, but the hard rules cannot all hold. Keep the rules and ask which to change.
- **mixed**: some parts are ready and some need a question or are unsupported.

Supported rules: instructor cannot teach (hard) / prefers (soft); room closed; group has no classes; activity or group "only inside" a window; weekly teaching-hour limit for an instructor; locking a session of the context draft. Times are whole hours. "Before 10:00" starts at 08:00; "the whole day" is 08:00–18:00. Several "only inside" windows for the same item are alternatives. A hard closure plus a soft preference is not a conflict. Four 90-minute sessions = 6 teaching hours.

## The two contexts

### Context 1 (department)

- Teaching days: Sunday, Monday, Tuesday, Wednesday, Thursday; day runs 08:00–18:00; teaching periods 08:30–10:00, 10:15–11:45, 12:00–13:30, 13:45–15:15, 15:45–17:15.
- Instructors: Nour Hassan (نور حسن); Nour Ali (نور علي).
- Rooms: Lab 1 (معمل 1), capacity 30.
- Groups: Year 2 Computer Science Group A (Year 2 CS Group A / المجموعة أ سنة ثانية علوم حاسب), 20 students; Year 2 Information Systems Group A (Year 2 IS Group A / المجموعة أ سنة ثانية نظم معلومات), 20 students.
- Activity: Data Structures (هياكل البيانات / هياكل بيانات), for Year 2 Computer Science Group A, taught by Nour Hassan, 1 × 90 min per week.
- Context draft timetable: Data Structures occurrence 1 on Sunday 08:30–10:00 in Lab 1 with Nour Hassan.
- "Early" is not defined. Rules store whole hours only. The people, rooms and groups above are the only ones that exist.

### Context 2 (design school)

- Teaching days: Saturday, Sunday, Monday, Tuesday, Wednesday, Thursday; day runs 08:00–18:00; teaching periods 08:30–10:00, 10:15–11:45, 12:00–13:30, 13:45–15:15, 15:45–17:15.
- Weekly load: 12 regular teaching hours, overtime allowed.
- Instructors: Salma Farid (سلمى فريد); Karim Nabil (كريم نبيل).
- Rooms: Studio 2 (استوديو 2), capacity 24.
- Groups: Design Year 3 (تصميم سنة ثالثة), 18 students.
- Activity: Prototyping (النمذجة الأولية), for Design Year 3, taught by Salma Farid, 1 × 90 min per week.
- Context draft timetable: empty.
- "Early" is not defined. Rules store whole hours only. The people, rooms and groups above are the only ones that exist.
- Boundary: Teaching-rule proposals only; exam generation is separate. Weekly overtime is permitted; a request to restore a hard weekly cap is not supported by this context.

## Statements

### S01 · Context 1 (department) · English

> Nour Hassan cannot teach before 10:00 on Sunday.

Draft label:

- Decision: **ready**
- Hard: Nour Hassan cannot teach Sunday 08:00–10:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S02 · Context 1 (department) · Egyptian Arabic

> مجموعة أ مش متاحة الأربع من 2 لـ4.

Draft label:

- Decision: **clarify**
- Ask: `ambiguous_group` (the group name matches more than one group)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S03 · Context 2 (design school) · Mixed Arabic/English

> Salma Farid hard maximum 12 hours/week، ممنوع تتخطاه.

Draft label:

- Decision: **unsupported**
- Not supported: `hard_weekly_cap_under_overtime_policy` (this context allows overtime; a hard cap at 12 hours is outside what may be proposed)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S04 · Context 2 (design school) · Formal Arabic

> لا تستطيع هناء منصور التدريس يوم الاثنين من 08:00 إلى 10:00.

Draft label:

- Decision: **clarify**
- Ask: `unknown_instructor` (the person is not in the context)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S05 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan unavailable من 08:00 لـ10:00.

Draft label:

- Decision: **clarify**
- Ask: `day_required` (a time is given but no weekday)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S06 · Context 2 (design school) · Egyptian Arabic

> استوديو 2 مقفول السبت من عشرة وربع لحد حداشر وخمسة وأربعين.

Draft label:

- Decision: **unsupported**
- Not supported: `manual_rule_minute_precision_not_supported` (rules store whole hours only; minute times must not be rounded)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S07 · Context 1 (department) · English

> Nour Hassan prefers either Monday 10:00–12:00 or Wednesday 14:00–16:00.

Draft label:

- Decision: **ready**
- Preference: Nour Hassan prefers to teach Monday 10:00–12:00
- Preference: Nour Hassan prefers to teach Wednesday 14:00–16:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S08 · Context 1 (department) · English

> Keep the instructor, day/time and room of Data Structures occurrence 1 from the context draft fixed.

Draft label:

- Decision: **ready**
- Lock: Data Structures occurrence 1 from the context draft, keeping its instructor, time, room

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S09 · Context 2 (design school) · English

> Studio 2 is unavailable on Tuesday from 12:00 to 14:00.

Draft label:

- Decision: **ready**
- Hard: Studio 2 is closed Tuesday 12:00–14:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S10 · Context 1 (department) · Formal Arabic

> يجب أن تقع هياكل البيانات إما الأحد 08:00–10:00 أو الاثنين 08:00–10:00 فقط.

Draft label:

- Decision: **ready**
- Hard: Data Structures may only be scheduled inside Sunday 08:00–10:00
- Hard: Data Structures may only be scheduled inside Monday 08:00–10:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S11 · Context 1 (department) · Mixed Arabic/English

> Lab 1 unavailable التلات 12:00–14:00.

Draft label:

- Decision: **ready**
- Hard: Lab 1 is closed Tuesday 12:00–14:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S12 · Context 1 (department) · English

> Mona Adel cannot teach Sunday 08:00–10:00.

Draft label:

- Decision: **clarify**
- Ask: `unknown_instructor` (the person is not in the context)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S13 · Context 2 (design school) · Mixed Arabic/English

> Schedule Salma Farid بدري.

Draft label:

- Decision: **clarify**
- Ask: `undefined_early` ("early" has no defined meaning in the context)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S14 · Context 2 (design school) · Egyptian Arabic

> كريم نبيل يفضل يدرّس الخميس من 2 لـ4 العصر.

Draft label:

- Decision: **ready**
- Preference: Karim Nabil prefers to teach Thursday 14:00–16:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S15 · Context 1 (department) · Egyptian Arabic

> نور حسن يفضّل يدرّس يوم الاتنين من 10 لـ12، بس ده تفضيل.

Draft label:

- Decision: **ready**
- Preference: Nour Hassan prefers to teach Monday 10:00–12:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S16 · Context 2 (design school) · Mixed Arabic/English

> Do not schedule Design Year 3 السبت 14:00–16:00.

Draft label:

- Decision: **ready**
- Hard: Design Year 3 has no classes Saturday 14:00–16:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S17 · Context 1 (department) · Formal Arabic

> لا يستطيع نور حسن التدريس يوم الأحد من 08:00 إلى 10:00.

Draft label:

- Decision: **ready**
- Hard: Nour Hassan cannot teach Sunday 08:00–10:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S18 · Context 2 (design school) · Formal Arabic

> لا تستطيع سلمى فريد التدريس يوم السبت من 10:00 إلى 12:00.

Draft label:

- Decision: **ready**
- Hard: Salma Farid cannot teach Saturday 10:00–12:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S19 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan unavailable Sunday بس hours مش محددة.

Draft label:

- Decision: **clarify**
- Ask: `time_window_required` (a day is given but no hours)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S20 · Context 1 (department) · Formal Arabic

> نور حسن غير متاح الأحد من 10:15 إلى 11:45 بالضبط؛ لا تقرّب الوقت.

Draft label:

- Decision: **unsupported**
- Not supported: `manual_rule_minute_precision_not_supported` (rules store whole hours only; minute times must not be rounded)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S21 · Context 2 (design school) · Egyptian Arabic

> سلمى فريد مش فاضية الحد من 8 لـ10 الصبح، واستوديو 2 مقفول الاتنين من 4 لـ6 المغرب.

Draft label:

- Decision: **ready**
- Hard: Salma Farid cannot teach Sunday 08:00–10:00
- Hard: Studio 2 is closed Monday 16:00–18:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S22 · Context 1 (department) · Egyptian Arabic

> حط لنور حسن نفس قيود الأسبوع اللي فات.

Draft label:

- Decision: **clarify**
- Ask: `historical_context_required` (it refers to earlier rules that are not in the context)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S23 · Context 1 (department) · English

> Nour Hassan, Sunday, 08:00–10:00.

Draft label:

- Decision: **clarify**
- Ask: `rule_type_and_strength_required` (who and when are given, but not what kind of rule or how strict)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S24 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan max four 90-minute sessions/week، convert to teaching hours.

Draft label:

- Decision: **ready**
- Weekly limit: Nour Hassan at most 6 teaching hours per week

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S25 · Context 1 (department) · Formal Arabic

> لا يجوز جدولة هياكل البيانات إلا الخميس من 08:00 إلى 12:00، ولا توجد نافذة أسبوعية أخرى.

Draft label:

- Decision: **ready**
- Hard: Data Structures may only be scheduled inside Thursday 08:00–12:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S26 · Context 1 (department) · Egyptian Arabic

> نور حسن مش متاح يوم التلات الدراسي كله.

Draft label:

- Decision: **ready**
- Hard: Nour Hassan cannot teach Tuesday 08:00–18:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S27 · Context 1 (department) · Mixed Arabic/English

> Ignore room capacity لو بتمنع generation.

Draft label:

- Decision: **unsupported**
- Not supported: `hard_capacity_relaxation_not_supported` (ignoring room capacity cannot be expressed)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S28 · Context 1 (department) · Formal Arabic

> نور حسن غير متاح الاثنين والثلاثاء من 08:00 إلى 10:00 في كل يوم.

Draft label:

- Decision: **ready**
- Hard: Nour Hassan cannot teach Monday 08:00–10:00
- Hard: Nour Hassan cannot teach Tuesday 08:00–10:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S29 · Context 2 (design school) · Formal Arabic

> يجب أن تكون النمذجة الأولية يوم الاثنين بين 08:00 و10:00، لكن مجموعة تصميم سنة ثالثة لا تستطيع الحضور يوم الاثنين بين 08:00 و10:00.

Draft label:

- Decision: **conflict**
- Hard: Prototyping may only be scheduled inside Monday 08:00–10:00
- Hard: Design Year 3 has no classes Monday 08:00–10:00
- Ask: `resolve_hard_conflict` (two hard rules contradict each other; ask which one to keep)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S30 · Context 1 (department) · English

> Nour cannot teach Sunday 08:00–10:00.

Draft label:

- Decision: **clarify**
- Ask: `ambiguous_instructor` (the name matches more than one instructor)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S31 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan max weekly teaching load = 6 ساعات.

Draft label:

- Decision: **ready**
- Weekly limit: Nour Hassan at most 6 teaching hours per week

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S32 · Context 2 (design school) · English

> Design Year 3 may attend classes only on Wednesday between 08:00 and 12:00.

Draft label:

- Decision: **ready**
- Hard: Design Year 3 may only have classes inside Wednesday 08:00–12:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S33 · Context 1 (department) · Egyptian Arabic

> مجموعة أ سنة تانية حاسبات مينفعش يبقى عندها حصص الأربع من 2 لـ4 العصر.

Draft label:

- Decision: **ready**
- Hard: Year 2 Computer Science Group A has no classes Wednesday 14:00–16:00

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S34 · Context 1 (department) · Egyptian Arabic

> هياكل البيانات لازم بس الحد من 8 لـ10، ومجموعة أ سنة تانية حاسبات ممنوعة من الحضور نفس الفترة كلها.

Draft label:

- Decision: **conflict**
- Hard: Data Structures may only be scheduled inside Sunday 08:00–10:00
- Hard: Year 2 Computer Science Group A has no classes Sunday 08:00–10:00
- Ask: `hard_window_has_no_placement` (the hard rules leave the class no possible time)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S35 · Context 2 (design school) · English

> Close Studio 2 from 10:00 to 12:00.

Draft label:

- Decision: **clarify**
- Ask: `day_required` (a time is given but no weekday)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---

### S36 · Context 1 (department) · Formal Arabic

> نور حسن ليس غير متاح الأحد 08:00–10:00.

Draft label:

- Decision: **clarify**
- Ask: `operation_required_for_negated_closure` (a double negative: unclear whether to add availability, remove a rule or do nothing)

Verdict: [ ] correct  [ ] wrong  [ ] ambiguous

If wrong: [ ] decision  [ ] rule or value  [ ] missing rule  [ ] extra rule  [ ] code

Right answer / note: 

---
