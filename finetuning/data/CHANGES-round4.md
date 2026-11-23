# Round 4 fine-tuning changes (for owner review)

Agent-authored fictional drafts aimed at four failures seen live in `jai-candidate-v3`. **Nothing is approved, exported, trained or committed.**

## Summary

- **26 new families, 87 new rows** (22 train families / 74 rows; 4 held-out test families / 13 rows, one per failure type, placed at the end of `FAMILIES`).
- **Dropped at review (2026-11-23):** `switch-complaint-to-import` (3 rows) was removed from `conversations.py` and `GUIDE_TOPICS` at the owner's request, so the held-out `not-sure-sis` stays unseen. Its text is kept below, struck through, for the record.
- Dataset now: **402 rows** (317 train / 85 test), 123 families; 303 conversation rows.
- **All 315 existing rows are byte-identical** (same sha256), so existing approvals in `reviews.local.json` remain valid.
- Backup of the previous file: `finetuning/exports/conversations.before-round4.py`.

## Code and guide changes

- `finetuning/conversations.py`: new families + `GUIDE_TOPICS` entries; three new scenarios in `view()`:
  - `exam-published`: the `exam` scenario with Computing midterms already published.
  - `exam-and-draft`: exam timetable on screen, teaching Draft 3 also exists (not on screen).
  - `draft-and-exam`: teaching Draft 3 on screen, the exam timetable remembered in memory.
- `finetuning/build_dataset.py`: a conversation family may set `operation`; its target then is that operation (with a short confirm-question reply) instead of `""`. Used for the exam/teaching publish families.
- `finetuning/test_toolkit.py`: row counts 315→402 and 216→303; conversation operation must equal the family's `operation`; new test `test_exam_timetable_publish_uses_the_exam_route` (exam publish only when the facts carry an exam timetable; teaching publish only in the teaching-only scenario).
- `backend/app/assistant_guide.py`, `scope` entry: **keywords only** added (body unchanged): `rain`, `capital of`, `world cup`, `homework`, `essay`, `equation`, `الجو هيبقى`, `كاس العالم`, `كأس العالم`, `عاصمة`, `واجب`. Without them the weather/trivia/homework wordings got no `scope` entry. None of the existing 315 prompts changed.

## Things to judge carefully

- **`exam-already-published`** labels "publish it" on an already-published exam as conversation (operation `""`), saying it is already published. The backend would actually accept a re-publish (it just re-stamps it), so reject this family if you prefer JAI to prepare the publish anyway.
- **Topic switches and the guide:** the guide is matched on the new message *plus earlier user turns*, top 3 entries. In these families the old topic's entry is often still present (e.g. `constraints` next to `import`); the reply must ignore it. That is realistic, but it is also a production weakness: a long history could push the new topic's entry out entirely. Weighting the current message higher in `guide()` would be a separate backend change.
- Formal Arabic wordings get the Egyptian reply, as in earlier rounds.
- New room replies say مقاعد (seats); older families (`special-rooms`, `delete-used-room`) still say كراسي. Not changed, to keep their approvals.
- In the toolkit `evaluate --task conversation` summary, the field `no_action` now really means "operation matched" for the publish rows.

## 1. Off-topic requests

### `offtopic-poem` (train, scenario `exam`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `scope`
- Wordings: "can you write a short poem for students about their midterms?" / "compose a funny poem about exam stress" / "اكتبلي شعر عن الامتحانات"
- **EN:** Sorry, writing poems is outside what I can help with; I only help with JadwAI. I can help with the exam timetable on your screen: Computing midterms is ready but not published yet. Would you like to review it before publishing?
- **AR:** معلش، كتابة الشعر برة اللي أقدر أساعد فيه، أنا بساعد في JadwAI بس. أقدر أساعدك في جدول الامتحانات اللي قدامك: Computing midterms جاهز بس لسه متنشرش. تحب نراجعه قبل النشر؟

### `offtopic-joke` (train, scenario `week`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `scope`
- Wordings: "tell me a joke" / "say something funny, a joke maybe?" / "قولي نكتة تضحكني"
- **EN:** Jokes are outside what I can help with; I only help with JadwAI. If you like, I can walk you through Draft 3 for Applied Computing II G1, for example its busiest day. Shall we look at it?
- **AR:** النكت برة اللي أقدر أساعد فيه، أنا بساعد في JadwAI بس. لو تحب، أقدر أوريك Draft 3 بتاع Applied Computing II G1، زي أتقل يوم فيه. نبص عليه؟

### `offtopic-weather` (train, scenario `week`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `scope`
- Wordings: "will it rain in Cairo tomorrow?" / "what's the weather like this weekend?" / "الجو هيبقى عامل إيه بكرة؟"
- **EN:** I cannot check the weather; I only help with JadwAI. I can tell you which days Applied Computing II G1 has classes in Draft 3, if that helps you plan the week. Would that help?
- **AR:** مقدرش أعرف حالة الجو، أنا بساعد في JadwAI بس. أقدر أقولك Applied Computing II G1 عنده حصص أنهي أيام في Draft 3، لو ده هيساعدك تخطط للأسبوع. ده يفيدك؟

### `offtopic-trivia` (train, scenario `week`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `scope`
- Wordings: "what's the capital of Australia?" / "who won the World Cup in 2022?" / "مين كسب كاس العالم آخر مرة؟" / "ما هي عاصمة أستراليا؟"
- **EN:** General knowledge questions are outside what I can help with; I only help with JadwAI: timetables, records, constraints, exams, publishing and accounts. Is there something in Draft 3 you would like to check?
- **AR:** أسئلة المعلومات العامة برة اللي أقدر أساعد فيه، أنا بساعد في JadwAI بس: الجداول والبيانات والقيود والامتحانات والنشر والحسابات. فيه حاجة في Draft 3 تحب نشوفها؟

### `offtopic-homework` (train, scenario `empty`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `scope`
- Wordings: "solve this equation for me: 2x + 3 = 11" / "can you write my essay on climate change?" / "حللي الواجب ده لو سمحت" / "هل يمكنك حل هذا الواجب؟"
- **EN:** Homework and essays are outside what I can help with; I only help with JadwAI. Your workspace has no records yet, so a good next step is setting up the semester. Would you like me to explain where to start?
- **AR:** الواجبات والمقالات برة اللي أقدر أساعد فيه، أنا بساعد في JadwAI بس. الـ workspace لسه مفيهوش بيانات، فخطوة كويسة إنك تجهز الترم. تحب أشرحلك تبدأ منين؟

### `offtopic-story` (**test (held out)**, scenario `stale`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `scope`
- Wordings: "tell me a bedtime story" / "write a short story about a lost student" / "احكيلي قصة قبل النوم"
- **EN:** Stories are outside what I can help with; I only help with JadwAI. Your published timetable, Fall teaching v2, is marked stale. Would you like to know what that means?
- **AR:** القصص برة اللي أقدر أساعد فيه، أنا بساعد في JadwAI بس. الجدول المنشور Fall teaching v2 متعلم عليه إنه stale. تحب تعرف ده معناه إيه؟

## 2. Topic switches (history about one thing, new message about another)

### ~~`switch-complaint-to-import`~~ DROPPED at review (was train, scenario `week`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `import`
- History (English): *user:* this is so annoying, I've typed the same constraint three times → *assistant:* Sorry it has been frustrating. What did you type, and what message did you see after it?
- History (Arabic): *user:* زهقت، كتبت نفس القيد تلات مرات → *assistant:* آسف إنها متعبة. كتبت إيه بالظبط، وظهرلك رسالة إيه بعدها؟
- Wordings: "different question: can JadwAI import students directly from our registration system?" / "unrelated, but does it connect to the university system to get students?" / "سؤال تاني: ينفع JadwAI ياخد الطلاب من سيستم الجامعة مباشرة؟"
- **EN:** I am not sure; I have no information about a direct link to another system. What I do know is that the import page loads a CSV file atomically: every row is saved or none is. Exporting the data from the university system as CSV is the safe route.
- **AR:** مش متأكد، معنديش معلومة عن ربط مباشر بسيستم تاني. اللي أعرفه إن صفحة الاستيراد بتستورد ملف CSV مرة واحدة: يا كل الصفوف تتحفظ يا ولا صف. فالأضمن إنك تصدر البيانات من سيستم الجامعة كـ CSV.

### `switch-rule-to-notifications` (train, scenario `week`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `unknown-features`
- History (English): *user:* delete the rule that keeps labs off Thursdays → *assistant:* I cannot find a rule about labs on Thursdays. Which rule do you mean? You can describe what it restricts.
- History (Arabic): *user:* امسح القيد اللي بيمنع المعامل يوم الخميس → *assistant:* مش لاقي قيد عن المعامل يوم الخميس. تقصد أنهي قيد؟ ممكن توصفلي هو بيمنع إيه.
- Wordings: "forget that. will students get an email or a notification when I publish?" / "never mind the rule; does JadwAI send SMS or email notifications?" / "سيبك من القيد. الطلاب بيوصلهم إيميل أو إشعار لما أنشر؟"
- **EN:** No. JadwAI has no email, SMS or push notifications. After you publish, people see their timetable in their own portal and can download it as CSV, so you may want to tell them yourself.
- **AR:** لا. JadwAI مفيهوش إيميل ولا SMS ولا إشعارات. بعد النشر كل واحد بيشوف جدوله في البوابة بتاعته ويقدر ينزله CSV، فممكن تبلغهم إنت.

### `switch-draft-to-roles` (train, scenario `week`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `roles`
- History (English): *user:* which day is the busiest? → *assistant:* Sunday. This group has four sessions then: the Computer Programming lecture at 08:30, its tutorial at 10:15, the Discrete Mathematics lecture at 12:00 and the Digital Media tutorial at 15:45, with the 13:45 period empty. Every other teaching day has one or two sessions.
- History (Arabic): *user:* أنهي يوم أتقل؟ → *assistant:* يوم الحد. الجروب عنده أربع حصص: محاضرة Computer Programming الساعة 08:30، والسكشن بتاعها 10:15، ومحاضرة Discrete Mathematics الساعة 12:00، وسكشن Digital Media الساعة 15:45، وفترة 13:45 فاضية. باقي أيام الدراسة فيها حصة أو اتنين بس.
- Wordings: "ok, other thing: why can't my colleague change any records?" / "separate question, who has permission to edit data in JadwAI?" / "حاجة تانية: زميلي مش قادر يعدل البيانات، ليه؟" / "سؤال آخر: من يملك صلاحية تعديل البيانات؟"
- **EN:** Only administrators can change data. If your colleague has the viewer role, they can read but not change anything; that is intended. An administrator can change their role on the accounts page. Should they be able to edit?
- **AR:** التعديل للأدمن بس. لو زميلك حسابه viewer، يقدر يشوف بس ميعدلش، وده مقصود. الأدمن يقدر يغير الـ role بتاعه من صفحة الحسابات. هو محتاج يعدل؟

### `switch-exam-to-rooms` (train, scenario `exam`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `rooms`
- History (English): *user:* why does the midterm draft still have back-to-back exam days? → *assistant:* The planner avoids back-to-back exam days for a cohort, but with 12 courses between 21 and 30 November some may be unavoidable, and it reports when they are.
- History (Arabic): *user:* ليه لسه فيه امتحانات في أيام ورا بعض في الميدترم؟ → *assistant:* المخطط بيحاول يتجنب امتحانات في أيام ورا بعض لنفس الطلاب، بس مع 12 مادة بين 21 و30 نوفمبر ممكن بعضها ميتجنبش، وبيقولك لما ده يحصل.
- Wordings: "unrelated: how many rooms do we have?" / "different topic, which rooms are in the system?" / "موضوع تاني: عندنا كام قاعة؟"
- **EN:** There are four rooms: H12 and H5 for lectures, Classroom C3.201 for tutorials, and Computer Lab B5.101. Do you want details for one of them?
- **AR:** عندنا أربع قاعات: H12 وH5 للمحاضرات، وC3.201 للسكاشن، ومعمل B5.101. عايز تفاصيل قاعة معينة؟

### `switch-pending-to-doctors` (train, scenario `week`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `instructors` · Pending: `PUT /api/records/{kind}/{ident}`
- History (English): *user:* set C3.201 capacity to 40 → *assistant:* I prepared the change: room C3.201 capacity becomes 40. Please confirm to apply it.
- History (Arabic): *user:* خلي سعة C3.201 أربعين → *assistant:* جهزت التعديل: سعة قاعة C3.201 هتبقى 40. أكد عشان يتنفذ.
- Wordings: "hold on, what is the difference between a Doctor and a TA?" / "wait, who teaches tutorials, doctors or TAs?" / "استنى، إيه الفرق بين الدكتور والمعيد؟"
- **EN:** Each instructor is either a Doctor or a TA. Doctors teach lectures; TAs teach tutorials and labs, and every TA must get at least one session. A TA's load depends on which activities list them as eligible.
- **AR:** كل محاضر يا إما Doctor يا إما TA. الدكاترة بيدرسوا المحاضرات، والمعيدين بيدرسوا السكاشن والمعامل، ولازم كل معيد ياخد حصة واحدة على الأقل. عبء المعيد بيعتمد على الأنشطة اللي هو مسموحله يديها.

### `switch-rule-to-portal` (**test (held out)**, scenario `week`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `portals`
- History (English): *user:* add a mandatory rule: no tutorials at 8:30 → *assistant:* Before I prepare it: should it apply to every group, or just to Applied Computing II G1?
- History (Arabic): *user:* ضيف قيد إجباري: مفيش سكاشن الساعة 8:30 → *assistant:* قبل ما أجهزه: يتطبق على كل الجروبات، ولا على Applied Computing II G1 بس؟
- Wordings: "wait, unrelated: what does a TA see in the portal?" / "different question, what do instructors see in their portal?" / "استنى، سؤال تاني: الطالب بيشوف إيه في البوابة؟"
- **EN:** Each instructor sees only their own teaching, and TAs also see their invigilation duties; students see only their own published sessions and exams. Each can download their own timetable as CSV. Nobody sees drafts or unpublished changes.
- **AR:** كل محاضر بيشوف تدريسه هو بس، والمعيد كمان بيشوف المراقبة بتاعته، والطالب بيشوف حصصه وامتحاناته المنشورة بس. وكل واحد يقدر ينزل جدوله CSV. محدش بيشوف المسودات أو التعديلات اللي متنشرتش.

## 3. Rooms, labs and room features (Egyptian Arabic: قاعة/قاعات، معمل/معامل، مقاعد)

### `rooms-data-science-lab` (train, scenario `empty`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `rooms`
- Wordings: "how do I make a course use a Data Science Lab?" / "what does the Data Science Lab feature do?" / "إزاي أخلي مادة تتحط في Data Science Lab؟" / "كيف أجعل المقرر يستخدم معمل Data Science Lab؟"
- **EN:** Data Science Lab is a room feature. Give that feature to the rooms that have it, then list it as a required feature on the course's activity, such as its lab. The solver then considers only rooms with every required feature, enough seats and a suitable type. Which activity needs it?
- **AR:** Data Science Lab دي ميزة بتتحط على القاعة. حط الميزة دي على المعامل اللي فيها فعلاً، وبعدين حددها كميزة مطلوبة في نشاط المادة، زي المعمل بتاعها. الـ solver هيختار بس من القاعات اللي فيها كل المميزات المطلوبة ومقاعد كفاية ونوع مناسب. أنهي نشاط محتاجها؟

### `rooms-gpu-feature` (train, scenario `week`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `rooms`
- Wordings: "what does the GPU feature on a room mean?" / "do any of our rooms have GPUs?" / "يعني إيه ميزة GPU في القاعة؟"
- **EN:** GPU is an optional room feature. An activity that requires it is placed only in a room with that feature, enough seats and a suitable type. None of the four rooms here lists GPU; Computer Lab B5.101 has only the Computer Lab feature. Do you want to add GPU to a room?
- **AR:** GPU ميزة اختيارية بتتحط على القاعة. النشاط اللي محتاجها بيتحط بس في قاعة فيها الميزة دي ومقاعد كفاية ونوع مناسب. ولا قاعة من الأربعة هنا عليها GPU، ومعمل B5.101 عليه ميزة Computer Lab بس. تحب تضيف GPU لقاعة؟

### `rooms-capacity-seats` (train, scenario `week`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `rooms`
- Wordings: "what happens if a group is bigger than the room capacity?" / "can a 120-student lecture use room H5?" / "لو الجروب أكبر من سعة القاعة إيه اللي بيحصل؟" / "هل يمكن وضع محاضرة لـ 120 طالباً في القاعة H5؟"
- **EN:** A room is considered only if it has enough seats for everyone attending. For example, H5 has 90 seats, so a lecture for 120 students cannot use it, while H12, with 120 seats, can. Which session are you checking?
- **AR:** القاعة بتتاخد في الاعتبار بس لو فيها مقاعد كفاية لكل اللي حاضرين. مثلاً H5 فيها 90 مقعد، فمحاضرة لـ 120 طالب متنفعش فيها، لكن H12 فيها 120 مقعد فتنفع. بتراجع أنهي حصة؟

### `rooms-exam-hall` (train, scenario `exam`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `exams`
- Wordings: "what does it mean when a room is marked Exam hall?" / "why are some rooms never used for exams?" / "يعني إيه القاعة متعلم عليها Exam hall؟"
- **EN:** Exam hall marks the rooms that can host exams. Each exam gets enough Exam halls to seat its students, and each hall needs a free TA invigilator. Rooms without that mark are not used for exams. Is an exam short of halls?
- **AR:** Exam hall علامة على القاعات اللي ينفع يتعمل فيها امتحانات. كل امتحان بياخد قاعات امتحانات مقاعدها تكفي طلابه، وكل قاعة محتاجة معيد مراقب فاضي. القاعات اللي من غير العلامة دي مش بتستخدم في الامتحانات. فيه امتحان مش لاقي قاعات كفاية؟

### `rooms-pin-activity` (train, scenario `week`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `rooms`
- Wordings: "how do I keep the Computer Programming lab in B5.101 every week?" / "can I fix the Discrete Mathematics lecture to room H12?" / "عايز معمل Computer Programming يفضل دايماً في B5.101، أعمل إيه؟" / "كيف أثبت محاضرة Discrete Mathematics في القاعة H12؟"
- **EN:** A rule can pin an activity to particular rooms, so the next drafts keep it there. Without one, equivalent rooms are interchangeable and the room may change between drafts. The room still needs enough seats and a suitable type and features. Should it be pinned to that one room?
- **AR:** فيه rule يقدر يثبت النشاط في قاعات معينة، فالمسودات الجاية هتحطه فيها. من غيره، القاعات المتساوية بتتبدل والقاعة ممكن تتغير من مسودة للتانية. والقاعة لازم يبقى فيها مقاعد كفاية ونوع ومميزات مناسبة. نثبته في القاعة دي بس؟

### `rooms-lab-in-classroom` (train, scenario `week`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `rooms`
- Wordings: "the solver never puts the lab in a normal classroom, is that intended?" / "the programming lab can't go in C3.201?" / "المعمل مش بيتحط في قاعة عادية، ده طبيعي؟" / "هل من الطبيعي ألا يوضع المعمل في قاعة دراسية عادية؟"
- **EN:** Yes, if the lab needs it. Only rooms with a suitable type, every required feature and enough seats are considered. C3.201 is a tutorial classroom with no features, while B5.101 is a lab with the Computer Lab feature. Should this lab be allowed in ordinary classrooms?
- **AR:** أيوه، لو المعمل محتاج كده. بيتاخد في الاعتبار بس القاعات اللي نوعها مناسب وفيها كل المميزات المطلوبة ومقاعد كفاية. C3.201 قاعة سكاشن من غير مميزات، لكن B5.101 معمل عليه ميزة Computer Lab. عايز المعمل ده ينفع يتحط في قاعات عادية؟

### `rooms-new-gpu-lab` (**test (held out)**, scenario `week`, 4 rows)

- Operation: `""` (conversation) · Guide topics: `rooms`
- Wordings: "we got a new lab with GPUs, how do I add it?" / "how should I set up a new GPU lab room?" / "جالنا معمل جديد فيه GPU، أضيفه إزاي؟" / "كيف أضيف معملاً جديداً مزوداً بـ GPU؟"
- **EN:** Add it as a new room with its code, capacity, the lab type and the GPU feature. Activities that require GPU will then consider it, as long as it has enough seats. What are its code and capacity?
- **AR:** ضيفه كقاعة جديدة بالكود والسعة ونوع معمل وميزة GPU. بعد كده الأنشطة اللي محتاجة GPU هتاخده في الاعتبار، طالما فيه مقاعد كفاية. إيه الكود والسعة بتوعه؟

## 4. Exam-timetable actions

### `exam-publish-screen` (train, scenario `exam`, 4 rows)

- Operation: `POST /api/exam-schedules/{ident}/publish` · Guide topics: `publishing`
- Wordings: "publish it now" / "go ahead and publish this" / "انشره" / "أرجو نشر هذا الجدول"
- **EN:** Shall I publish Computing midterms, the exam timetable on your screen? Publishing re-validates it first.
- **AR:** أنشر Computing midterms، جدول الامتحانات اللي قدامك؟ النشر بيراجعه الأول.

### `exam-publish-after-review` (train, scenario `exam`, 3 rows)

- Operation: `POST /api/exam-schedules/{ident}/publish` · Guide topics: `publishing`
- History (English): *user:* what should I check in the midterm draft? → *assistant:* Check that every course appears, no cohort has two exams at once, every hall has an invigilator, and the dates fall inside 21 to 30 November. Computing midterms is not published yet.
- History (Arabic): *user:* أراجع إيه في مسودة الميدترم؟ → *assistant:* اتأكد إن كل المواد موجودة، ومفيش طلاب عندهم امتحانين في نفس الوقت، وكل قاعة ليها مراقب، والأيام جوه الفترة من 21 لـ 30 نوفمبر. Computing midterms لسه متنشرش.
- Wordings: "looks fine, publish it" / "all good, go ahead and publish" / "تمام، انشره"
- **EN:** Shall I publish Computing midterms now? Publishing re-validates it against the current approved inputs first.
- **AR:** أنشر Computing midterms دلوقتي؟ النشر بيراجعه الأول على المدخلات المعتمدة الحالية.

### `exam-publish-after-pdf` (train, scenario `exam`, 3 rows)

- Operation: `POST /api/exam-schedules/{ident}/publish` · Guide topics: `publishing`
- History (English): *user:* download the midterm timetable as a PDF → *assistant:* The confirmed website response returned the PDF for Computing midterms.
- History (Arabic): *user:* نزلي جدول الميدترم PDF → *assistant:* الموقع رجع ملف PDF لـ Computing midterms.
- Wordings: "checked the PDF, publish it" / "ok, now publish the exams" / "راجعت الـ PDF، انشره"
- **EN:** Shall I publish the exam timetable Computing midterms? Publishing re-validates it first.
- **AR:** أنشر جدول الامتحانات Computing midterms؟ النشر بيراجعه الأول.

### `exam-publish-not-teaching` (train, scenario `exam-and-draft`, 3 rows)

- Operation: `POST /api/exam-schedules/{ident}/publish` · Guide topics: `publishing`
- Wordings: "publish this one" / "publish what is on my screen" / "انشر اللي قدامي"
- **EN:** Shall I publish Computing midterms, the exam timetable on your screen? Draft 3, the teaching draft, is not affected.
- **AR:** أنشر Computing midterms، جدول الامتحانات اللي قدامك؟ Draft 3، مسودة التدريس، مش هتتأثر.

### `exam-publish-named` (train, scenario `draft-and-exam`, 3 rows)

- Operation: `POST /api/exam-schedules/{ident}/publish` · Guide topics: `publishing`
- Wordings: "publish the midterm exam timetable" / "publish the exams, not the teaching draft" / "انشر جدول الامتحانات مش جدول المحاضرات"
- **EN:** Shall I publish Computing midterms, the exam timetable? Draft 3, the teaching timetable on your screen, stays unpublished.
- **AR:** أنشر Computing midterms، جدول الامتحانات؟ Draft 3، جدول التدريس اللي قدامك، هيفضل متنشرش.

### `teaching-publish-screen` (train, scenario `week`, 3 rows)

- Operation: `POST /api/schedules/{ident}/publish` · Guide topics: `publishing`
- Wordings: "publish this draft" / "ok, publish Draft 3" / "انشر المسودة دي"
- **EN:** Shall I publish Draft 3, the teaching timetable on your screen? Publishing re-validates it first, and only one teaching timetable can be published at a time.
- **AR:** أنشر Draft 3، جدول التدريس اللي قدامك؟ النشر بيراجعه الأول، وجدول تدريس واحد بس ينفع يبقى منشور في نفس الوقت.

### `exam-already-published` (train, scenario `exam-published`, 3 rows)

- Operation: `""` (conversation) · Guide topics: `publishing`
- Wordings: "publish the exams" / "can you publish this?" / "انشر الامتحانات"
- **EN:** Computing midterms is already published, and only one exam timetable can be published at a time. Is there a change you want to make first, or did you mean another timetable?
- **AR:** Computing midterms منشور خلاص، وجدول امتحانات واحد بس ينفع يبقى منشور في نفس الوقت. فيه تعديل عايز تعمله الأول، ولا تقصد جدول تاني؟

### `exam-publish-formal` (**test (held out)**, scenario `exam-and-draft`, 3 rows)

- Operation: `POST /api/exam-schedules/{ident}/publish` · Guide topics: `publishing`
- Wordings: "please publish the exam schedule" / "يرجى نشر جدول الامتحانات" / "ممكن تنشر جدول الامتحانات؟"
- **EN:** Shall I publish Computing midterms, the exam timetable? Publishing re-validates it first.
- **AR:** أنشر جدول الامتحانات Computing midterms؟ النشر بيراجعه الأول.
