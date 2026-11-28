# Label audit, Part A (blind): what should the answer be?

Fill this in **before** opening Part B. Do not look up the statements in `cases.jsonl`.
For each statement: tick one decision (change `[ ]` to `[x]`) and write in one line what the answer should be:
the rules (who, day, hours, hard or preference), or what must be asked, or why it is not supported.
Use the context of the statement only. About 1 minute per statement.

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

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S02 · Context 1 (department) · Egyptian Arabic

> مجموعة أ مش متاحة الأربع من 2 لـ4.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S03 · Context 2 (design school) · Mixed Arabic/English

> Salma Farid hard maximum 12 hours/week، ممنوع تتخطاه.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S04 · Context 2 (design school) · Formal Arabic

> لا تستطيع هناء منصور التدريس يوم الاثنين من 08:00 إلى 10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S05 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan unavailable من 08:00 لـ10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S06 · Context 2 (design school) · Egyptian Arabic

> استوديو 2 مقفول السبت من عشرة وربع لحد حداشر وخمسة وأربعين.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S07 · Context 1 (department) · English

> Nour Hassan prefers either Monday 10:00–12:00 or Wednesday 14:00–16:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S08 · Context 1 (department) · English

> Keep the instructor, day/time and room of Data Structures occurrence 1 from the context draft fixed.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S09 · Context 2 (design school) · English

> Studio 2 is unavailable on Tuesday from 12:00 to 14:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S10 · Context 1 (department) · Formal Arabic

> يجب أن تقع هياكل البيانات إما الأحد 08:00–10:00 أو الاثنين 08:00–10:00 فقط.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S11 · Context 1 (department) · Mixed Arabic/English

> Lab 1 unavailable التلات 12:00–14:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S12 · Context 1 (department) · English

> Mona Adel cannot teach Sunday 08:00–10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S13 · Context 2 (design school) · Mixed Arabic/English

> Schedule Salma Farid بدري.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S14 · Context 2 (design school) · Egyptian Arabic

> كريم نبيل يفضل يدرّس الخميس من 2 لـ4 العصر.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S15 · Context 1 (department) · Egyptian Arabic

> نور حسن يفضّل يدرّس يوم الاتنين من 10 لـ12، بس ده تفضيل.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S16 · Context 2 (design school) · Mixed Arabic/English

> Do not schedule Design Year 3 السبت 14:00–16:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S17 · Context 1 (department) · Formal Arabic

> لا يستطيع نور حسن التدريس يوم الأحد من 08:00 إلى 10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S18 · Context 2 (design school) · Formal Arabic

> لا تستطيع سلمى فريد التدريس يوم السبت من 10:00 إلى 12:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S19 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan unavailable Sunday بس hours مش محددة.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S20 · Context 1 (department) · Formal Arabic

> نور حسن غير متاح الأحد من 10:15 إلى 11:45 بالضبط؛ لا تقرّب الوقت.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S21 · Context 2 (design school) · Egyptian Arabic

> سلمى فريد مش فاضية الحد من 8 لـ10 الصبح، واستوديو 2 مقفول الاتنين من 4 لـ6 المغرب.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S22 · Context 1 (department) · Egyptian Arabic

> حط لنور حسن نفس قيود الأسبوع اللي فات.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S23 · Context 1 (department) · English

> Nour Hassan, Sunday, 08:00–10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S24 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan max four 90-minute sessions/week، convert to teaching hours.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S25 · Context 1 (department) · Formal Arabic

> لا يجوز جدولة هياكل البيانات إلا الخميس من 08:00 إلى 12:00، ولا توجد نافذة أسبوعية أخرى.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S26 · Context 1 (department) · Egyptian Arabic

> نور حسن مش متاح يوم التلات الدراسي كله.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S27 · Context 1 (department) · Mixed Arabic/English

> Ignore room capacity لو بتمنع generation.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S28 · Context 1 (department) · Formal Arabic

> نور حسن غير متاح الاثنين والثلاثاء من 08:00 إلى 10:00 في كل يوم.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S29 · Context 2 (design school) · Formal Arabic

> يجب أن تكون النمذجة الأولية يوم الاثنين بين 08:00 و10:00، لكن مجموعة تصميم سنة ثالثة لا تستطيع الحضور يوم الاثنين بين 08:00 و10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S30 · Context 1 (department) · English

> Nour cannot teach Sunday 08:00–10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S31 · Context 1 (department) · Mixed Arabic/English

> Nour Hassan max weekly teaching load = 6 ساعات.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S32 · Context 2 (design school) · English

> Design Year 3 may attend classes only on Wednesday between 08:00 and 12:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S33 · Context 1 (department) · Egyptian Arabic

> مجموعة أ سنة تانية حاسبات مينفعش يبقى عندها حصص الأربع من 2 لـ4 العصر.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S34 · Context 1 (department) · Egyptian Arabic

> هياكل البيانات لازم بس الحد من 8 لـ10، ومجموعة أ سنة تانية حاسبات ممنوعة من الحضور نفس الفترة كلها.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S35 · Context 2 (design school) · English

> Close Studio 2 from 10:00 to 12:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---

### S36 · Context 1 (department) · Formal Arabic

> نور حسن ليس غير متاح الأحد 08:00–10:00.

Decision: [ ] ready  [ ] clarify  [ ] unsupported  [ ] conflict  [ ] mixed

Answer: 

Notes: 

---
