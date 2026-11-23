"""Verified product knowledge for JAI's local model.

The local model invents plausible but wrong details about how JadwAI works (measured in the
fine-tuning evaluation, see finetuning/RESULTS.md). Instead of relying on what it memorised,
the few entries relevant to the user's message are put into its prompt as facts['guide'].
Every statement here must match the code; keep entries short, general and free of IDs or API paths.
"""
import re

# (topic, keywords matched in the lower-cased message and recent user turns, verified text)
GUIDE = (
    ('privacy', ('cloud', 'privacy', 'private', 'my data', 'chatgpt', 'openai', 'internet', 'stored', 'what model', 'which model', 'are you', 'برة', 'بره', 'كلاود', 'سحاب', 'بياناتي', 'خصوصي', 'شات جي بي تي'),
     'JAI runs on a language model hosted on this server. Conversations and records are not sent to a cloud model. Changes are saved only in the JadwAI database, and only after the user confirms them.'),
    ('scope', ('poem', 'joke', 'story', 'song', 'weather', 'recipe', 'football', 'what can you do', 'can you help', 'how can you help', 'تساعدني', 'تقدر تعمل', 'تعمل إيه', 'شعر', 'قصيدة', 'نكتة', 'قصة', 'غنية', 'الطقس',
               'rain', 'capital of', 'world cup', 'homework', 'essay', 'equation', 'الجو هيبقى', 'كاس العالم', 'كأس العالم', 'عاصمة', 'واجب'),
     'JAI only helps with JadwAI: timetables, records, constraints, exams, publishing and accounts. For anything else it says it is outside what it can help with and offers to help with the timetable.'),
    ('confirming', ('confirm', 'save', 'saved', 'did you', 'propose', 'proposal', 'أؤكد', 'تأكيد', 'undo', 'cancel', 'اتحفظ', 'حفظت', 'أكد', 'اكد', 'الغي', 'إلغاء'),
     'JAI prepares one website change at a time. Nothing is saved until the user presses the confirm button or replies explicitly, such as "yes, do it"; "cancel" rejects it. The website re-checks permissions and the data version before saving, and refuses the change if someone else changed the data in between.'),
    ('roles', ('viewer', 'role', 'permission', 'admin', 'can\'t edit', 'cannot edit', 'edit records', 'colleague', 'password', 'باسورد', 'كلمة السر', 'يعدل', 'صلاحي', 'أدمن', 'ادمن', 'مش قادر يعدل'),
     'Administrators can change data. Viewers can read but not change anything. Students and instructors only use their personal portal. An administrator changes roles on the accounts page. Passwords are never handled in chat; the account page has the reset workflow.'),
    ('portals', ('portal', 'students see', 'student see', 'instructors see', 'after i publish', 'after publishing', 'download', 'الطلاب هيشوفوا', 'الطالب بيشوف', 'بوابة', 'بعد النشر', 'ينزل'),
     'After publishing, each student sees only their own published sessions and published exams; each instructor sees only their own teaching, and TAs also their invigilation duties. Each can download their own timetable as CSV. Nobody sees drafts, other people\'s timetables or unpublished changes, and portal users cannot edit timetables.'),
    ('publishing', ('publish', 'unpublish', 'stale', 'out of date', 'take it down', 'already see', 'نشر', 'انشر', 'منشور', 'اتنشر', 'قديم'),
     'Publishing re-validates a draft against the current approved inputs; only one teaching timetable and one exam timetable can be published at a time. Unpublishing removes it from the portals and keeps the draft. Stale means approved inputs changed after the timetable was generated; students still see it until another one is published.'),
    ('drafts', ('draft', 'regenerate', 'generate', 'مسودة', 'مسوده', 'توليد', 'ولد'),
     'Each generation creates a new draft that keeps its own copy of the data it was built from. Changing records, rules or availability never changes existing drafts; it applies to the next generated draft. A separate validator rechecks every mandatory rule before a draft is kept, so an invalid draft is never saved.'),
    ('solver-time', ('long', 'slow', 'time limit', 'workers', 'how long', 'faster', 'speed', 'وقت', 'بطيء', 'بياخد وقت', 'أسرع', 'اسرع'),
     'The solver first finds a valid timetable, then keeps improving the convenience score until its time limit. Default search settings are 30 seconds and 4 workers, or 240 seconds and 8 workers for more than 150 weekly sessions. Many mandatory rules, fine time grids and large shared lectures make the search harder. A shorter limit is faster but may give a less convenient draft.'),
    ('constraints', ('constraint', 'rule', 'mandatory', 'preferred', 'hard', 'soft', 'guarantee', 'early', 'first period', 'typed', 'type ', 'applied', '8:30', 'كتبت', 'بيتطبق', 'ضمان', 'تضمن', 'بدري', 'أول فترة', 'قيد', 'قيود', 'إجباري', 'اجباري', 'مفضل'),
     'A mandatory constraint holds in every valid draft; if it cannot be satisfied, no draft is produced. A preferred constraint is a wish the solver honours when it can, and breaking it costs convenience. Typed constraints become draft rules that the user reviews and approves before they affect the next generation.'),
    ('generation-failed', ('fail', 'failed', 'no timetable', 'no valid', 'infeasible', 'impossible', 'فشل', 'مستحيل', 'مالقاش', 'مفيش جدول'),
     'Generation fails when mandatory inputs contradict each other or leave too little space, for example more sessions than suitable rooms at the free times, unavailability blocking every slot, or a TA with no possible session. Check inputs names many of these problems before generating, but it cannot prove a timetable exists; relax one mandatory rule at a time.'),
    ('rooms', ('room', 'lab', 'hall', 'feature', 'capacity', 'reserved', 'classroom', 'identical', 'قاعة', 'قاعات', 'معمل', 'سعة', 'مميزات', 'مدرج'),
     'Rooms have a capacity, room types and optional features such as Data Science Lab or GPU. An activity can require features; only rooms with every required feature, enough seats and a suitable type are considered. A rule can pin an activity to particular rooms, and a room can be reserved for chosen programmes or courses. Equivalent rooms are interchangeable, so the concrete room may differ between drafts.'),
    ('instructors', ('doctor', 'ta ', 'tas ', 'ta?', 'instructor', 'workload', 'prefer', 'teaching only', 'only one', 'only has one', 'likes', 'morning', 'الصبح', 'الصباح', 'who teaches', 'بيدرس', 'دكتور', 'معيد', 'محاضرين', 'عبء', 'يفضل', 'بتحب', 'واخد'),
     'Each instructor is a Doctor (teaches lectures) or a TA (teaches tutorials and labs), and every TA must get at least one session. Unavailability is never violated once approved; a preferred teaching period is honoured when possible. A TA\'s load depends on which activities list them as eligible; uneven weekly load is penalised above 3, 6 and 12 hours.'),
    ('convenience', ('convenien', 'score', 'best', 'optimal', 'gap', 'empty slot', 'empty period', 'compar', 'better', 'fewer teaching days', 'days on campus', 'fewer days', 'lighter days', 'shorter days', 'أحسن', 'احسن', 'أفضل', 'قارن', 'فراغ', 'مقارنة', 'راحة', 'مريح', 'أيام حضور', 'أخف'),
     'The convenience score counts missed instructor preferences, same-day repeats of an activity, student and instructor gaps, days on campus, the busiest day, long teaching days, first or last periods and uneven workload; lower is better. Passing validation is not proof that no better timetable exists. Scenario comparison shows the moved sessions and the metrics of two drafts side by side.'),
    ('shared-lectures', ('shared', 'move', 'moving', 'moved', 'free day', 'day off', 'مشترك', 'انقل', 'ننقل', 'نقل', 'يوم إجازة', 'اجازة'),
     'A shared lecture is one session attended by several groups, so moving it moves it for all of them and all must be free. Giving a group a free day schedules the same sessions on the remaining days, which makes those days heavier. A scenario edit is saved only if the validator passes.'),
    ('import', ('upload', 'import', 'csv', 'excel', 'spreadsheet', 'file', 'student information system', 'university system', 'سيستم الجامعة', 'ملف', 'إكسل', 'اكسل', 'ارفع'),
     'Files cannot be uploaded through the chat. The import page imports a CSV file atomically: every row is saved or none is. A spreadsheet must be saved as CSV first.'),
    ('exams', ('exam', 'midterm', 'final', 'quiz', 'invigilat', 'consecutive', 'back-to-back', 'proctor', 'امتحان', 'امتحانات', 'ميدتيرم', 'مراقب'),
     'Exam timetables are planned separately for quizzes, midterms and finals. Each exam gets halls marked Exam hall that seat its students, and each hall needs a free TA invigilator. The planner avoids back-to-back exam days for a cohort and reports when they are unavoidable; more exam dates or halls usually help.'),
    ('solver', ('solver', 'how does jadwai', 'make the schedule', 'builds a timetable', 'build a timetable', 'بناء الجدول', 'يبني الجدول', 'بيتعمل إزاي', 'بيعمل الجدول', 'بيتعمل ازاي'),
     'The solver first finds a quick valid timetable that respects every mandatory rule for rooms, instructors, groups and times. Then, within its time limit, it keeps searching for placements with a better convenience score. A separate validator rechecks every mandatory rule before a draft is kept, so an invalid draft is never saved.'),
    ('setup', ('where do i start', 'start?', 'empty system', 'order of setup', 'set up', 'setup', 'أبدأ', 'ابدأ', 'فاضي، أبدأ'),
     'Setup order: semester settings (teaching days, hours and periods); then rooms, instructors with their Doctor or TA role, student groups, and courses with their lectures, tutorials and labs (the import page can load CSV files); then constraints; then Check inputs; then generate a draft.'),
    ('check-inputs', ('check inputs', 'check input', 'before generating', 'قبل التوليد'),
     'Check inputs reviews the data before generation and names problems the solver would hit, such as a TA who cannot be given any session, an activity no room can host, or an instructor without a Doctor or TA role. It does not prove that a timetable exists; only the solver can find one.'),
    ('unavailability', ('unavailab', 'closed', 'maintenance', "can't come", 'cannot come', "can't teach", 'away', 'مقفول', 'صيانة', 'مش هتقدر', 'مش متاح', 'غير متاح', 'مش بتيجي', 'لا تحضر', 'لا يحضر'),
     'Unavailability is recorded on the instructor or room record and approved like other changes. Once approved it is never violated: the next generated draft places affected sessions elsewhere, or generation fails if no suitable alternative is free. Existing drafts keep their own copy of the data and do not change.'),
    ('daily-limits', ('daily', 'per day', 'a day', 'hours a day', 'في اليوم', 'يوميا'),
     'There are daily hour limits for a student group and for an instructor, and a limit on an instructor\'s teaching days. As a mandatory rule a limit holds in every valid draft, but the same sessions must still fit, so with few teaching days it can make generation fail. As a preferred rule it is honoured when possible.'),
    ('periods', ('period', 'minutes', 'hour lab', '3-hour', 'longer than', 'spanning', 'الفترة', 'دقيقة', 'ساعات يتحط'),
     'With named teaching periods, a session covers consecutive periods whose teaching minutes add up exactly to its duration, for example a three-hour lab over two 90-minute periods. A break of up to 30 minutes between them stays inside the session; a longer break ends the run, so a session never spans it.'),
    ('advising', ('advising', 'retake', 'retaking', 'elective', 'another group', 'شايل', 'يعيد مادة', 'مجموعة أخرى', 'إرشاد', 'ارشاد', 'جروب تاني'),
     'Advising students are students whose courses differ from their group\'s, such as retakes or courses from another plan; an administrator adds them from the Student groups page. Each keeps their group\'s sessions except dropped courses and joins another group for added courses. None of their sessions may overlap, and each is an exam cohort of their own.'),
    ('deleting', ('delete', 'deleting', 'remove h', 'remove a room', 'remove a record', 'مسح', 'امسح', 'أمسح', 'حذف'),
     'JadwAI refuses to delete a record while other records or rules still refer to it. Existing drafts keep their own copy of the data they were built from, so deleting never changes them; new drafts can only use the remaining records.'),
    ('unknown-features', ('email', 'e-mail', 'notif', 'sms', 'whatsapp', 'google calendar', 'outlook', 'sync', 'إيميل', 'ايميل', 'إشعار', 'اشعار', 'رسالة'),
     'JadwAI has no email, SMS or push notifications and no calendar sync. After publishing, people see their timetable in their own portal and can download it as CSV.'),
)

MAX_ENTRIES = 3


def _pattern(word):
    # English keywords match at a word start ("convenien" -> "convenience"); a trailing space means a
    # whole word ("ta " must not match "data"). Arabic keywords match anywhere (attached prefixes).
    if re.search(r'[a-z]', word):
        return re.compile(r'(?<![a-z])' + re.escape(word.strip()) + (r'(?![a-z])' if word.endswith(' ') else ''))
    return re.compile(re.escape(word))


PATTERNS = [(body, [_pattern(w) for w in words]) for _, words, body in GUIDE]


def guide(text):
    """The verified entries most relevant to the message (most keyword hits first, at most three)."""
    text = (text or '').lower()
    scored = []
    for order, (body, patterns) in enumerate(PATTERNS):
        hits = sum(1 for p in patterns if p.search(text))
        if hits:
            scored.append((-hits, order, body))
    return [body for _, _, body in sorted(scored)[:MAX_ENTRIES]]
