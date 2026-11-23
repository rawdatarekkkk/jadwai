# Changes to review: answers grounded in the guide (2026-11-22)

Only the families listed here need a new approval. Everything else is unchanged and still approved.
Check that each new answer is correct for JadwAI and uses only what the guide entries in its prompt say
(see `backend/app/assistant_guide.py`). Full prompts are in `data/REVIEW.md` and the JSONL files.

## New families (4)

### not-sure-sis (test)
- Questions: can JadwAI pull students straight from the university system? | does it connect to our student information system? | ينفع JadwAI يسحب الطلاب من سيستم الجامعة على طول؟
- EN: I am not sure about a direct connection; nothing I have mentions one. What I do know is that the import page imports a CSV file atomically, every row or none, so exporting the data as CSV from that system is the safe route.
- AR: مش متأكد إن فيه ربط مباشر، مفيش حاجة عندي بتقول كده. اللي أعرفه إن صفحة الاستيراد بتستورد ملف CSV مرة واحدة، يا كل الصفوف يا ولا واحد، فالأضمن إنك تصدر البيانات من السيستم ده كـ CSV.

### not-sure-travel-time
- Questions: does JadwAI account for travel time between campuses? | will the timetable leave time to walk between buildings? | الجدول بيحسب وقت المشي بين المباني؟
- EN: I am not sure. The information I have about JadwAI does not cover travel time between buildings or campuses, so I would rather not guess. I can tell you which rooms this group uses on each day, if that helps.
- AR: مش متأكد. المعلومات اللي عندي عن JadwAI مش بتقول حاجة عن وقت التنقل بين المباني، فمش عايز أخمن. أقدر أقولك الجروب ده بيستخدم أنهي قاعات كل يوم لو ده يفيدك.

### not-sure-user-limit
- Questions: how many people can use JadwAI at the same time? | is there a maximum number of users? | كام واحد يقدر يستخدم النظام في نفس الوقت؟
- EN: I am not sure. I have no verified information about a limit on users at the same time. Whoever runs this server would know. Is there something in Draft 3 I can help with meanwhile?
- AR: مش متأكد. معنديش معلومة مؤكدة عن حد أقصى لعدد المستخدمين في نفس الوقت. اللي مسؤول عن السيرفر ده هيعرف. فيه حاجة في Draft 3 أقدر أساعدك فيها؟

### notifications
- Questions: will students get an email when I publish? | does JadwAI send notifications to instructors? | الطلاب هيوصلهم إيميل لما أنشر؟ | هل يرسل النظام إشعاراً للطلاب عند النشر؟
- EN: No. JadwAI has no email, SMS or push notifications. After you publish, each person sees their timetable in their own portal and can download it as CSV, so you may want to tell them yourself that it is published.
- AR: لا. JadwAI مفيهوش إيميل أو SMS أو إشعارات. بعد ما تنشر، كل واحد بيشوف جدوله في البوابة بتاعته ويقدر ينزله CSV، فممكن تبلغهم إنت إنه اتنشر.


## Answer rewritten (11)

### advising-students
- Before (EN): Students whose courses differ from their group's, such as retakes, drops or electives, are added under Academic data, Student groups, Advising students. Each keeps their group's sessions minus dropped courses, plus the added courses with the chosen group. None of their sessions may overlap, they count toward room seats, and each is treated as an exam cohort. Which student do you have in mind?
- After (EN): Advising students are students whose courses differ from their group's, such as retakes or courses from another plan; an administrator adds them from the Student groups page. Each keeps their group's sessions except dropped courses and joins another group for added courses. None of their sessions may overlap, and each is an exam cohort of their own. Which student do you have in mind?
- After (AR): طلاب الإرشاد هما الطلاب اللي موادهم مختلفة عن جروبهم، زي الشايلين مادة أو واخدين مادة من خطة تانية، والأدمن بيضيفهم من صفحة Student groups. كل طالب بياخد حصص جروبه ناقص المواد اللي سابها، وبيحضر مع جروب تاني المواد المضافة. ممنوع حصصه تتعارض، وبيتعامل كمجموعة امتحانات لوحده. بتفكر في أنهي طالب؟
- Added question: كيف يتم التعامل مع طالب يعيد مادة مع مجموعة أخرى؟

### back-to-back-exams
- Before (EN): The planner avoids consecutive exam days for one cohort, but with 12 courses between 21 and 30 November some may be unavoidable. The result reports how many back-to-back days the chosen dates make unavoidable. To reduce them, extend the exam period or allow another exam per day; each has a cost for students. Which would you rather consider?
- After (EN): The planner avoids back-to-back exam days for a cohort, but with 12 courses between 21 and 30 November some may be unavoidable, and it reports when they are. More exam dates or halls usually help, for example extending the period. Would you like to look at extending the dates?
- After (AR): المخطط بيحاول يتجنب امتحانات في أيام ورا بعض لنفس الطلاب، بس مع 12 مادة بين 21 و30 نوفمبر ممكن بعضها ميتجنبش، وبيقولك لما ده يحصل. زيادة أيام أو قاعات الامتحانات غالباً بتساعد، زي إنك تمد الفترة. تحب نشوف نمد التواريخ؟

### capabilities
- Before (EN): I can explain how JadwAI builds timetables, help you set up rooms, instructors, groups and courses, prepare constraints for your approval, and discuss the trade-offs in a draft. I prepare one change at a time, and nothing happens until you confirm it. Your workspace has no records yet, so the semester settings are a good first step. Shall we start there?
- After (EN): I only help with JadwAI: timetables, records, constraints, exams, publishing and accounts. I can explain how things work, discuss trade-offs in a draft, and prepare one website change at a time; nothing happens until you confirm it. Your workspace has no records yet. Would you like me to explain where to start?
- After (AR): أنا بساعد في JadwAI بس: الجداول والبيانات والقيود والامتحانات والنشر والحسابات. أقدر أشرحلك الحاجات بتشتغل إزاي، ونناقش البدائل في أي مسودة، وأجهز تعديل واحد على الموقع في المرة، ومفيش حاجة بتتنفذ غير لما تأكد. الـ workspace لسه مفيهوش بيانات. تحب أشرحلك تبدأ منين؟

### convenience-score
- Before (EN): The default profile weighs, in order: missed instructor preferences, two sessions of one activity on the same day, student gaps, instructor gaps, days on campus, the busiest day, teaching beyond four and a half hours a day, first or last period sessions, and uneven workload. Each term is recounted independently before a draft is kept. Lower is more convenient, but it does not prove no better timetable exists.
- After (EN): It counts missed instructor preferences, the same activity twice on one day, student and instructor gaps, days on campus, the busiest day, long teaching days, first or last periods and uneven workload. Lower is better. Passing validation is not proof that no better timetable exists. Which of these matters most to you?
- After (AR): بيحسب تفضيلات المحاضرين اللي متحققتش، ونفس النشاط مرتين في يوم واحد، وفراغات الطلاب والمحاضرين، وأيام الحضور، وأتقل يوم، والأيام الطويلة، والحصص في أول أو آخر فترة، وعدم توازن العبء. كل ما الرقم يقل يبقى أحسن، بس إن الجدول عدى الفحص مش دليل إن مفيش أحسن منه. أنهي بند يهمك أكتر؟
- Added question: كيف يتم قياس راحة الجدول؟

### doctors-and-tas
- Before (EN): Each instructor is either a Doctor or a TA. Doctors teach lectures; TAs teach tutorials and labs. Course setup, input checks, the solver and the validator all enforce this, and every TA must be given at least one session. An instructor saved before roles existed stays unclassified, shown as a warning until edited.
- After (EN): Each instructor is either a Doctor or a TA. Doctors teach lectures; TAs teach tutorials and labs, and every TA must get at least one session. A TA's load depends on which activities list them as eligible. Is there an instructor whose role you want to check?
- After (AR): كل محاضر يا إما Doctor يا إما TA. الدكاترة بيدرسوا المحاضرات، والمعيدين بيدرسوا السكاشن والمعامل، ولازم كل معيد ياخد حصة واحدة على الأقل. عبء المعيد بيعتمد على الأنشطة اللي هو مسموحله يديها. فيه محاضر معين عايز تتأكد من دوره؟
- Added question: ما الفرق بين الدكتور والمعيد في JadwAI؟

### exam-halls
- Before (EN): Each exam gets one or more rooms marked Exam hall whose capacity covers its students, from group sizes or the course's expected students. Every hall needs a free TA invigilator, respecting days off and approved unavailability. The planner places dates and slots first, then assigns halls slot by slot. If halls or TAs run short, adding exam halls or dates is usually the fix.
- After (EN): Each exam gets halls marked Exam hall that together seat its students, and each hall needs a free TA invigilator. The planner avoids back-to-back exam days for a cohort and reports when they are unavoidable. If halls or TAs run short, more exam dates or halls usually help. Is a particular exam causing trouble?
- After (AR): كل امتحان بياخد قاعات متعلم عليها Exam hall تكفي طلابه، وكل قاعة محتاجة معيد مراقب فاضي. المخطط بيحاول يتجنب امتحانات في أيام ورا بعض لنفس الطلاب، وبيقولك لو مينفعش. لو القاعات أو المعيدين مش كفاية، زيادة أيام أو قاعات الامتحانات غالباً بتحل. فيه امتحان معين عامل مشكلة؟
- Added question: كيف يتم توزيع قاعات الامتحانات والمراقبين؟

### generation-failed
- Before (EN): Usually the mandatory inputs contradict each other or leave too little space: more sessions than suitable rooms at the free times, an instructor whose unavailability blocks every slot, a TA with no possible session, or a very narrow time window. Run Check inputs first; it names many of these problems. Then relax one mandatory rule at a time. Shall we go through the inputs together?
- After (EN): Generation fails when the mandatory inputs contradict each other or leave too little space: for example more sessions than suitable rooms at the free times, unavailability blocking every slot, or a TA with no possible session. Check inputs names many of these problems, but it cannot prove a timetable exists. Then relax one mandatory rule at a time. Shall we go through the inputs together?
- After (AR): التوليد بيفشل لما القيود الإجبارية تتعارض مع بعض أو متسيبش مساحة كفاية: مثلاً حصص أكتر من القاعات المناسبة في الأوقات الفاضية، أو عدم إتاحة قافل كل الفترات، أو معيد مفيش أي حصة ينفع ياخدها. Check inputs بيقولك على كتير من المشاكل دي، بس مش بيضمن إن فيه جدول ممكن. وبعدين خفف قيد إجباري واحد في المرة. نراجع المدخلات سوا؟
- Added question: لماذا فشل توليد الجدول؟

### room-pool
- Before (EN): Usually it is not a problem. Rooms with the same capacity, types and features that no rule or lock names are treated as one pool during the search; the concrete room is assigned afterwards. So two drafts can place a session in different but equivalent rooms. If it must stay in one specific room, pin it with a rule or lock that session.
- After (EN): Usually it is not a problem. Equivalent rooms are interchangeable, so the concrete room may differ between drafts. If the tutorial must always use one particular room, a rule can pin the activity to that room. Should it stay in a specific room?
- After (AR): غالباً مش مشكلة. القاعات المتساوية بتتبادل مع بعض، فالقاعة الفعلية ممكن تختلف من مسودة للتانية. لو السكشن لازم يبقى دايماً في قاعة معينة، ينفع rule يثبت النشاط في القاعة دي. هو لازم يفضل في قاعة معينة؟

### ta-workload
- Before (EN): Workload follows eligibility: a TA eligible for more activities can be given more sessions, and some sessions can only go to the few TAs free at that time. Uneven workload is penalised in steps above 3, 6 and 12 weekly hours, but it is the last term in the convenience score. Widening eligibility usually balances it best. Which TAs are you comparing?
- After (EN): A TA's load depends on which activities list them as eligible, so a TA eligible for more activities can get more sessions. Uneven weekly load is penalised above 3, 6 and 12 hours, but it is a preference, not a rule. Widening eligibility usually balances it best. Which TAs are you comparing?
- After (AR): عبء المعيد بيعتمد على الأنشطة اللي هو مسموحله يديها، فالمعيد المسموحله أنشطة أكتر ممكن ياخد حصص أكتر. عدم التوازن الأسبوعي عليه غرامة فوق 3 و6 و12 ساعة، بس ده تفضيل مش قاعدة. توسيع الأهلية غالباً أحسن طريقة للتوازن. بتقارن بين أنهي معيدين؟

### typed-constraint-flow
- Before (EN): No. A typed constraint is interpreted into draft rules, and you review and approve them before they affect generation. If a name is ambiguous or a detail such as the time or strength is missing, I ask first. Approved rules apply to the next generated draft; existing drafts do not change.
- After (EN): No. A typed constraint becomes draft rules that you review and approve before they affect the next generation. If a name is ambiguous or a detail such as the time or strength is missing, I ask first. What constraint do you want to add?
- After (AR): لا. القيد اللي بتكتبه بيتحول لـ rules مسودة، وانت بتراجعها وتوافق عليها قبل ما تأثر على التوليد الجاي. لو فيه اسم مش واضح أو تفصيلة ناقصة زي الوقت أو إجباري ولا مفضل، بسألك الأول. عايز تضيف قيد إيه؟
- Added question: هل يطبق القيد الذي أكتبه فوراً؟

### unavailability-vs-preference
- Before (EN): Those are two different things. Thursday is unavailability: once approved, the solver never places her sessions then. Mornings are a preferred teaching period: the solver tries to honour it, and a missed preference is the first term in the convenience score. Both belong to her instructor record and need approval. Shall we start with the Thursday unavailability?
- After (EN): Those are two different things. Thursday is unavailability: it is recorded on her instructor record, approved, and then never violated. Mornings are a preferred teaching period, honoured when possible; a missed preference costs convenience. Shall we start with the Thursday unavailability?
- After (AR): دول حاجتين مختلفين. الخميس ده عدم إتاحة: بيتسجل في بيانات المحاضرة، ويتعتمد، وبعدها عمره ما بيتكسر. الصبح ده فترة تدريس مفضلة، بتتحقق لما ينفع، والتفضيل اللي مايتحققش بيقلل الراحة. نبدأ بعدم الإتاحة يوم الخميس؟
- Added question: كيف أسجل أن الدكتورة سلمى تفضل الصباح ولا تحضر يوم الخميس؟


## Formal-Arabic wording added (answer unchanged) (16)

- **check-inputs**: ما فائدة Check inputs قبل التوليد؟
- **compare-drafts**: كيف أعرف أن Draft 3 أفضل من Draft 2؟
- **confirming-changes**: كيف أؤكد التعديل الذي تقترحه؟
- **csv-in-chat**: هل يمكنني رفع ملف إكسل في المحادثة؟
- **daily-limit**: هل يمكن تحديد ساعات المجموعة في اليوم؟
- **days-vs-load**: أيهما أفضل للطلاب: أيام حضور أقل أم أيام أخف؟
- **delete-used-room**: ماذا يحدث إذا حذفت القاعة H12؟
- **getting-started**: من أين أبدأ إعداد النظام؟
- **hard-vs-soft**: ما الفرق بين القيد الإجباري والقيد المفضل؟
- **is-optimal**: هل هذا أفضل جدول ممكن؟
- **is-published**: هل تم نشر هذا الجدول؟
- **salma-unavailable**: ماذا لو أصبحت الدكتورة سلمى نبيل غير متاحة يوم الأحد؟
- **solver-simply**: كيف يقوم النظام ببناء الجدول؟
- **spanning-periods**: كيف يوضع معمل مدته ثلاث ساعات والفترة 90 دقيقة؟
- **stale-published**: لماذا يظهر أن الجدول المنشور قديم؟
- **unpublish-effect**: ماذا يحدث إذا ألغيت نشر الجدول؟

## Only the guide text in the prompt changed (13)

- free-days
- identity
- move-shared
- no-early-classes
- password-help
- privacy
- pronoun-follow-up
- room-closure
- sunday-gap
- ta-one-session
- viewer-role
- which-lecture
- who-teaches-lab
