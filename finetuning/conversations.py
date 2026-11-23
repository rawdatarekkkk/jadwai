"""Fictional multi-turn conversations that teach JAI to talk things through.

Every example uses the production conversation interface: the same system prompt, chat history,
facts and selection schema, with operation "" (talk, explain, clarify or reason; no website action).
Replies are grounded only in facts the production pipeline actually sends for that message.
All people, rooms, groups and drafts are invented. Human review is still required before training.
"""

# Teaching periods 08:30-10:00, 10:15-11:45, 12:00-13:30, 13:45-15:15, 15:45-17:15.
P = [(510, 600), (615, 705), (720, 810), (825, 915), (945, 1035)]
G1, G2 = 'group-ac2g1', 'group-ac2g2'
CALENDAR = {'days': ['Saturday', 'Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday'], 'start_hour': 8.5, 'end_hour': 17.25,
            'period_minutes': 90, 'teaching_periods': [{'start': a, 'end': b} for a, b in P]}
WORKSPACE = {'name': 'Faculty of Computing (demo)', 'term': 'Fall 2026', 'timezone': 'Africa/Cairo', 'days': CALENDAR['days'],
             'start_hour': 8.5, 'end_hour': 17.25, 'period_minutes': 90, 'teaching_periods': CALENDAR['teaching_periods'],
             'realism_policy': None, 'start_date': '2026-09-19', 'end_date': '2027-01-07'}


def rec(ident, kind, **data):
    return {'id': ident, 'kind': kind, 'data': data}


RECORDS = [
    rec('room-h12', 'rooms', code='H12', name='Lecture Hall 12', capacity=120, room_types=['lecture']),
    rec('room-h5', 'rooms', code='H5', name='Lecture Hall 5', capacity=90, room_types=['lecture']),
    rec('room-c3201', 'rooms', code='C3.201', name='Classroom C3.201', capacity=35, room_types=['tutorial']),
    rec('room-b5101', 'rooms', code='B5.101', name='Computer Lab B5.101', capacity=30, room_types=['lab'], features=['Computer Lab']),
    rec('ins-salma', 'instructors', name='Dr. Salma Nabil', position='doctor'),
    rec('ins-karim', 'instructors', name='Dr. Karim Adel', position='doctor'),
    rec('ins-hany', 'instructors', name='Dr. Hany Saad', position='doctor'),
    rec('ins-rania', 'instructors', name='Dr. Rania Fathy', position='doctor'),
    rec('ins-omar', 'instructors', name='Omar Farouk', position='ta'),
    rec('ins-mona', 'instructors', name='Mona Hegazy', position='ta'),
    rec('ins-youssef', 'instructors', name='Youssef Amin', position='ta'),
    rec(G1, 'groups', name='Applied Computing II G1', code='AC2G1', major='Applied Computer Science & Informatics', year=2, size=30),
    rec(G2, 'groups', name='Applied Computing II G2', code='AC2G2', major='Applied Computer Science & Informatics', year=2, size=28),
    rec('course-csen401', 'courses', name='Computer Programming', code='CSEN 401'),
    rec('course-math203', 'courses', name='Discrete Mathematics', code='MATH 203'),
    rec('course-dmet301', 'courses', name='Digital Media', code='DMET 301'),
    rec('course-comm104', 'courses', name='Communication Skills', code='COMM 104'),
]


def session(day, period, activity, course, code, kind, groups, room_id, room, instructor_id, instructor):
    start, end = P[period - 1]
    return {'activity_id': activity, 'occurrence': 0, 'day': day, 'start_minute': start, 'end_minute': end, 'room_id': room_id,
            'instructor_id': instructor_id, 'course': course, 'code': code, 'type': kind, 'groups': groups, 'room': room, 'instructor': instructor}


# Applied Computing II G1 in Draft 3: 8 sessions; Monday and Thursday free; Sunday busiest (4) with 13:45 empty;
# Tuesday has 12:00 empty. Shared lectures: Digital Media (Sat), Discrete Mathematics (Sun), Communication Skills (Wed).
SESSIONS = [
    session('Saturday', 2, 'act-dmet301-lec', 'Digital Media', 'DMET 301', 'lecture', [G1, G2], 'room-h5', 'H5', 'ins-hany', 'Dr. Hany Saad'),
    session('Sunday', 1, 'act-csen401-lec', 'Computer Programming', 'CSEN 401', 'lecture', [G1], 'room-h12', 'H12', 'ins-salma', 'Dr. Salma Nabil'),
    session('Sunday', 2, 'act-csen401-tut', 'Computer Programming', 'CSEN 401', 'tutorial', [G1], 'room-c3201', 'C3.201', 'ins-omar', 'Omar Farouk'),
    session('Sunday', 3, 'act-math203-lec', 'Discrete Mathematics', 'MATH 203', 'lecture', [G1, G2], 'room-h12', 'H12', 'ins-karim', 'Dr. Karim Adel'),
    session('Sunday', 5, 'act-dmet301-tut', 'Digital Media', 'DMET 301', 'tutorial', [G1], 'room-c3201', 'C3.201', 'ins-youssef', 'Youssef Amin'),
    session('Tuesday', 2, 'act-csen401-lab', 'Computer Programming', 'CSEN 401', 'lab', [G1], 'room-b5101', 'B5.101', 'ins-mona', 'Mona Hegazy'),
    session('Tuesday', 4, 'act-math203-tut', 'Discrete Mathematics', 'MATH 203', 'tutorial', [G1], 'room-c3201', 'C3.201', 'ins-youssef', 'Youssef Amin'),
    session('Wednesday', 1, 'act-comm104-lec', 'Communication Skills', 'COMM 104', 'lecture', [G1, G2], 'room-h5', 'H5', 'ins-rania', 'Dr. Rania Fathy'),
]


def view(name):
    base = {'calendar': CALENDAR, 'workspace': WORKSPACE, 'version': 14, 'users': [], 'rules': [], 'catalog': [], 'exam_run': None}
    if name == 'empty':
        return {**base, 'workspace': {**WORKSPACE, 'name': 'New workspace'}, 'version': 1, 'records': [], 'sessions': [], 'run': None,
                'screen': {'page': 'overview'}, 'memory': {}}
    if name == 'week':
        return {**base, 'records': RECORDS, 'sessions': SESSIONS, 'screen': {'page': 'timetable', 'run_id': 'run-draft3', 'group': G1},
                'memory': {'groups': [G1], 'run': 'run-draft3'},
                'run': {'id': 'run-draft3', 'name': 'Draft 3', 'published': False, 'stale': False, 'on_screen': True, 'talked_about': False,
                        'complete': True, 'scope': None, 'created_at': '2026-11-10T09:00:00', 'sessions': 212, 'kept': 0}}
    if name == 'stale':
        return {**base, 'records': RECORDS, 'sessions': SESSIONS, 'screen': {'page': 'timetable', 'run_id': 'run-fall2', 'group': G1},
                'memory': {'run': 'run-fall2'},
                'run': {'id': 'run-fall2', 'name': 'Fall teaching v2', 'published': True, 'stale': True, 'on_screen': True, 'talked_about': False,
                        'complete': True, 'scope': None, 'created_at': '2026-10-02T11:30:00', 'sessions': 212, 'kept': 0}}
    if name == 'exam':
        return {**base, 'records': RECORDS, 'sessions': [], 'run': None, 'screen': {'page': 'exams', 'run_id': 'exam-mid1'},
                'memory': {'exam_run': 'exam-mid1', 'schedule_focus': {'kind': 'exams', 'id': 'exam-mid1'}},
                'exam_run': {'id': 'exam-mid1', 'status': 'completed', 'kind': 'midterm', 'published': False, 'stale': False, 'halls': True,
                             'name': 'Computing midterms', 'courses': 12, 'start_date': '2026-11-21', 'end_date': '2026-11-30'}}
    raise KeyError(name)


def U(text):
    return {'role': 'user', 'content': text}


def A(text):
    return {'role': 'assistant', 'content': text}


BUSIEST_EN = ('Sunday. This group has four sessions then: the Computer Programming lecture at 08:30, its tutorial at 10:15, '
              'the Discrete Mathematics lecture at 12:00 and the Digital Media tutorial at 15:45, with the 13:45 period empty. '
              'Every other teaching day has one or two sessions.')
BUSIEST_AR = ('يوم الحد. الجروب عنده أربع حصص: محاضرة Computer Programming الساعة 08:30، والسكشن بتاعها 10:15، '
              'ومحاضرة Discrete Mathematics الساعة 12:00، وسكشن Digital Media الساعة 15:45، وفترة 13:45 فاضية. '
              'باقي أيام الدراسة فيها حصة أو اتنين بس.')
TUESDAY_EN = ('On Tuesday this group has two sessions: the Computer Programming lab from 10:15 to 11:45 in B5.101 with Mona Hegazy, '
              'and the Discrete Mathematics tutorial from 13:45 to 15:15 in C3.201 with Youssef Amin. The 12:00 period between them is empty.')
TUESDAY_AR = ('يوم التلات الجروب عنده حصتين: معمل Computer Programming من 10:15 لـ 11:45 في B5.101 مع منى حجازي، '
              'وسكشن Discrete Mathematics من 13:45 لـ 15:15 في C3.201 مع يوسف أمين. فترة 12:00 اللي بينهم فاضية.')
LIGHTER_EN = ('Possibly. The Computer Programming lecture and tutorial and the Digital Media tutorial belong only to this group, so they are '
              'the easiest to move. The Discrete Mathematics lecture is shared with another group, so both groups must be free. '
              'Moving a session to Monday or Thursday would end one of their free days. Which matters more: a lighter Sunday or two free days?')

# Each family: three wordings (two English, one Egyptian Arabic), an English and an Arabic reply.
# history / history_ar: earlier turns (history_ar defaults to history, i.e. the user switched language).
FAMILIES = [
    # ---- Small talk, identity and boundaries ----
    dict(name='greeting', scenario='week', variants=['hi', 'hello JAI', 'أهلاً يا JAI'],
         reply=('Hello! I can explain the timetable on your screen, discuss scheduling trade-offs, and prepare one website change at a time for you to confirm. '
                'You are viewing Draft 3 for Applied Computing II G1, which is not published yet. What would you like to look at?',
                'أهلاً بيك! أقدر أشرح الجدول اللي قدامك، وأناقش معاك البدائل، وأجهز تعديل واحد على الموقع في المرة وانت تأكده. '
                'انت فاتح دلوقتي Draft 3 لجروب Applied Computing II G1، ولسه متنشرش. تحب نبص على إيه؟')),
    dict(name='capabilities', scenario='empty', variants=['what can you do?', 'how can you help me with timetabling?', 'تقدر تساعدني في إيه؟'],
         reply=('I only help with JadwAI: timetables, records, constraints, exams, publishing and accounts. I can explain how things work, discuss trade-offs in a draft, and prepare one website change at a time; nothing happens until you confirm it. Your workspace has no records yet. Would you like me to explain where to start?',
                'أنا بساعد في JadwAI بس: الجداول والبيانات والقيود والامتحانات والنشر والحسابات. أقدر أشرحلك الحاجات بتشتغل إزاي، ونناقش البدائل في أي مسودة، وأجهز تعديل واحد على الموقع في المرة، ومفيش حاجة بتتنفذ غير لما تأكد. الـ workspace لسه مفيهوش بيانات. تحب أشرحلك تبدأ منين؟')),
    dict(name='thanks', scenario='week', variants=["thanks, that's all", 'great, thank you', 'تمام شكراً'],
         reply=('You are welcome. Draft 3 is still unpublished, so nothing has changed for students or instructors. Come back whenever you want to review or publish it.',
                'العفو. Draft 3 لسه متنشرش، فمفيش حاجة اتغيرت عند الطلاب أو المحاضرين. ارجعلي في أي وقت لو حبيت تراجعها أو تنشرها.')),
    dict(name='identity', scenario='week', variants=['are you ChatGPT?', 'what model are you?', 'انت ChatGPT؟'],
         reply=('I am JAI, JadwAI\'s assistant, running on a language model hosted on this server. I can explain timetables and prepare changes, '
                'but every change goes through the website\'s own checks and your confirmation.',
                'أنا JAI، مساعد JadwAI، وشغال على موديل لغة متثبت على السيرفر ده. أقدر أشرح الجداول وأجهز تعديلات، '
                'بس أي تعديل بيعدي على فحوصات الموقع نفسه وعلى تأكيدك.')),
    dict(name='privacy', scenario='week', holdout=True, variants=['does my data go to the cloud?', 'is this chat sent to OpenAI?', 'البيانات بتتبعت لأي سيرفر برة؟'],
         reply=('No. I run on a model hosted on this server, so this conversation and your records are not sent to a cloud model.',
                'لا. أنا شغال على موديل متثبت على السيرفر ده، فالمحادثة وبياناتك مش بتتبعت لأي موديل على الكلاود.')),
    dict(name='out-of-scope', scenario='week', holdout=True, variants=['write me a poem about exams', "what's the weather tomorrow?", 'احكيلي نكتة'],
         reply=('That is outside what I can help with here. I focus on JadwAI: timetables, records, constraints, exams and publishing. '
                'Is there something in Draft 3 you would like to review?',
                'ده برة اللي أقدر أساعد فيه هنا. أنا مركز على JadwAI: الجداول والبيانات والقيود والامتحانات والنشر. '
                'فيه حاجة في Draft 3 تحب نراجعها؟')),
    dict(name='frustrated', scenario='week', holdout=True,
         variants=['this is useless, nothing works', "I've been trying for an hour and it keeps failing", 'زهقت، مفيش حاجة شغالة'],
         reply=('Sorry it has been frustrating. Let us find the actual problem. What were you trying to do, and what message did you see? '
                'For example, a generation that found no timetable, a change that was refused, or a page that would not save.',
                'آسف إنها كانت متعبة. خلينا نوصل للمشكلة الحقيقية. كنت بتحاول تعمل إيه، وظهرلك رسالة إيه؟ '
                'مثلاً التوليد مالقاش جدول، ولا تعديل اترفض، ولا صفحة مش راضية تحفظ؟')),
    dict(name='password-help', scenario='week', variants=["I forgot Omar's account password", 'reset the password for a TA account', 'نسيت باسورد حساب معيد'],
         reply=('I cannot see or change passwords in chat. Use the account page for the password reset workflow, so the new password never passes through this conversation.',
                'مقدرش أشوف أو أغير الباسوردات من الشات. استخدم صفحة الحسابات عشان تعمل reset، كده الباسورد الجديد مش هيعدي على المحادثة دي خالص.')),
    dict(name='viewer-role', scenario='week', variants=["why can't my colleague edit records?", "a viewer account can't change anything, is that a bug?", 'زميلي مش قادر يعدل، ليه؟'],
         reply=('That is intended if their account has the viewer role: viewers can read but not change anything. Only administrators make changes. '
                'If they need to edit, an administrator can change their role on the accounts page. Which account is it?',
                'ده مقصود لو حسابه viewer: الـ viewer يقدر يشوف بس ميعدلش. التعديل للأدمن بس. '
                'لو محتاج يعدل، الأدمن يقدر يغير الـ role بتاعه من صفحة الحسابات. حساب مين؟')),

    # ---- How JadwAI works (concepts) ----
    dict(name='hard-vs-soft', scenario='empty',
         variants=['explain the difference between mandatory and preferred constraints', "what's the difference between a hard rule and a soft rule?", 'إيه الفرق بين القيد الإجباري والمفضل؟', 'ما الفرق بين القيد الإجباري والقيد المفضل؟'],
         reply=('A mandatory constraint must hold in every valid timetable; if the solver cannot satisfy it, no draft is produced. A preferred constraint is a wish: '
                'the solver tries to honour it but may break it when that is the only way to fit everything, and breaking it costs the draft some convenience. '
                'Too many mandatory rules can make a timetable impossible, so keep mandatory for real limits.',
                'القيد الإجباري لازم يتحقق في أي جدول صالح، ولو الـ solver مقدرش يحققه مفيش مسودة هتطلع. القيد المفضل رغبة: '
                'الـ solver بيحاول يحققه، بس ممكن يكسره لو ده الحل الوحيد عشان كل حاجة تتحط، وكسره بيقلل راحة الجدول. '
                'القيود الإجبارية الكتير ممكن تخلي الجدول مستحيل، فخلي الإجباري للحدود الحقيقية بس.')),
    dict(name='generation-failed', scenario='week',
         variants=['why did the generation fail with no timetable found?', 'the solver says no valid timetable exists, what usually causes that?', 'ليه التوليد فشل وقال مفيش جدول ممكن؟', 'لماذا فشل توليد الجدول؟'],
         reply=('Generation fails when the mandatory inputs contradict each other or leave too little space: for example more sessions than suitable rooms at the free times, unavailability blocking every slot, or a TA with no possible session. Check inputs names many of these problems, but it cannot prove a timetable exists. Then relax one mandatory rule at a time. Shall we go through the inputs together?',
                'التوليد بيفشل لما القيود الإجبارية تتعارض مع بعض أو متسيبش مساحة كفاية: مثلاً حصص أكتر من القاعات المناسبة في الأوقات الفاضية، أو عدم إتاحة قافل كل الفترات، أو معيد مفيش أي حصة ينفع ياخدها. Check inputs بيقولك على كتير من المشاكل دي، بس مش بيضمن إن فيه جدول ممكن. وبعدين خفف قيد إجباري واحد في المرة. نراجع المدخلات سوا؟')),
    dict(name='doctors-and-tas', scenario='empty',
         variants=['explain the difference between doctors and TAs in JadwAI', 'who teaches lectures and who teaches tutorials?', 'مين بيدرس المحاضرات ومين بيدرس السكاشن؟', 'ما الفرق بين الدكتور والمعيد في JadwAI؟'],
         reply=("Each instructor is either a Doctor or a TA. Doctors teach lectures; TAs teach tutorials and labs, and every TA must get at least one session. A TA's load depends on which activities list them as eligible. Is there an instructor whose role you want to check?",
                'كل محاضر يا إما Doctor يا إما TA. الدكاترة بيدرسوا المحاضرات، والمعيدين بيدرسوا السكاشن والمعامل، ولازم كل معيد ياخد حصة واحدة على الأقل. عبء المعيد بيعتمد على الأنشطة اللي هو مسموحله يديها. فيه محاضر معين عايز تتأكد من دوره؟')),
    dict(name='special-rooms', scenario='empty', holdout=True,
         variants=['explain how special rooms like labs are chosen', 'how does the system decide which lab a session uses?', 'النظام بيختار المعمل إزاي للسكشن؟'],
         reply=('Rooms can carry features such as Data Science Lab or GPU, and an activity can list required features. Only rooms with every required feature, '
                'enough seats and a suitable room type are considered. If an activity must use particular rooms, a rule can pin it to them, and a room can be reserved '
                'for chosen programmes or courses. Which activity are you thinking about?',
                'القاعات ممكن يكون ليها مميزات زي Data Science Lab أو GPU، والنشاط ممكن يحدد مميزات مطلوبة. بيتاخد في الاعتبار بس القاعات اللي فيها كل المميزات المطلوبة '
                'وكراسي كفاية ونوع مناسب. ولو نشاط لازم يكون في قاعات معينة، فيه rule تثبته فيها، وممكن كمان تحجز قاعة لبرامج أو مواد معينة. بتفكر في أنهي نشاط؟')),
    dict(name='convenience-score', scenario='week',
         variants=['explain what the convenience score measures', 'how do you judge whether a timetable is convenient?', 'يعني إيه الجدول مريح؟ بتقيسوه إزاي؟', 'كيف يتم قياس راحة الجدول؟'],
         reply=('It counts missed instructor preferences, the same activity twice on one day, student and instructor gaps, days on campus, the busiest day, long teaching days, first or last periods and uneven workload. Lower is better. Passing validation is not proof that no better timetable exists. Which of these matters most to you?',
                'بيحسب تفضيلات المحاضرين اللي متحققتش، ونفس النشاط مرتين في يوم واحد، وفراغات الطلاب والمحاضرين، وأيام الحضور، وأتقل يوم، والأيام الطويلة، والحصص في أول أو آخر فترة، وعدم توازن العبء. كل ما الرقم يقل يبقى أحسن، بس إن الجدول عدى الفحص مش دليل إن مفيش أحسن منه. أنهي بند يهمك أكتر؟')),
    dict(name='room-pool', scenario='week',
         variants=['why did the solver put the tutorial in a different room than last draft?', 'the tutorial moved to another identical classroom, is that a problem?', 'ليه السكشن اتنقل لقاعة تانية شبه القديمة؟'],
         reply=('Usually it is not a problem. Equivalent rooms are interchangeable, so the concrete room may differ between drafts. If the tutorial must always use one particular room, a rule can pin the activity to that room. Should it stay in a specific room?',
                'غالباً مش مشكلة. القاعات المتساوية بتتبادل مع بعض، فالقاعة الفعلية ممكن تختلف من مسودة للتانية. لو السكشن لازم يبقى دايماً في قاعة معينة، ينفع rule يثبت النشاط في القاعة دي. هو لازم يفضل في قاعة معينة؟')),
    dict(name='solver-simply', scenario='empty',
         variants=['explain how the solver builds a timetable, simply', 'how does JadwAI actually make the schedule?', 'اشرحلي ببساطة الجدول بيتعمل إزاي', 'كيف يقوم النظام ببناء الجدول؟'],
         reply=('First it finds a quick valid timetable that respects every mandatory rule for rooms, instructors, groups and times. Then, within the time limit, '
                'it keeps searching for placements with a better convenience score, such as fewer gaps or fewer days on campus. Before a draft is kept, '
                'a separate validator rechecks the rules, so an invalid draft is never saved.',
                'الأول بيلاقي جدول صالح بسرعة يحترم كل القيود الإجبارية للقاعات والمحاضرين والجروبات والأوقات. وبعدين، في حدود الوقت المسموح، '
                'بيفضل يدور على توزيع أريح، زي فراغات أقل أو أيام حضور أقل. وقبل ما المسودة تتحفظ، فيه validator منفصل بيراجع القيود تاني، '
                'فعمر ما مسودة غلط بتتحفظ.')),
    dict(name='search-time', scenario='week', holdout=True,
         variants=['why does generating take so long?', 'can generation be faster?', 'ليه التوليد بياخد وقت طويل؟'],
         reply=('The solver searches many combinations of days, times, rooms and instructors while improving convenience. Search settings default to 30 seconds and 4 workers, '
                'or 240 seconds and 8 workers above 150 weekly sessions. Fine 30-minute grids, many mandatory rules and large shared lectures make it harder. '
                'A shorter limit is faster but may give a less convenient draft. Is speed or quality more important right now?',
                'الـ solver بيجرب تركيبات كتير من الأيام والأوقات والقاعات والمحاضرين وهو بيحسن الراحة. الإعداد الافتراضي 30 ثانية و4 workers، '
                'أو 240 ثانية و8 workers لو الحصص أكتر من 150 في الأسبوع. التقسيم كل نص ساعة والقيود الإجبارية الكتير والمحاضرات المشتركة الكبيرة بيصعبوها. '
                'لو قللت الوقت هيخلص أسرع بس ممكن المسودة تبقى أقل راحة. السرعة أهم ولا الجودة دلوقتي؟')),
    dict(name='typed-constraint-flow', scenario='empty',
         variants=['is a typed constraint applied straight away?', "if I type 'no labs after 2pm', is it applied immediately?", 'لو كتبت قيد، بيتطبق على طول؟', 'هل يطبق القيد الذي أكتبه فوراً؟'],
         reply=('No. A typed constraint becomes draft rules that you review and approve before they affect the next generation. If a name is ambiguous or a detail such as the time or strength is missing, I ask first. What constraint do you want to add?',
                'لا. القيد اللي بتكتبه بيتحول لـ rules مسودة، وانت بتراجعها وتوافق عليها قبل ما تأثر على التوليد الجاي. لو فيه اسم مش واضح أو تفصيلة ناقصة زي الوقت أو إجباري ولا مفضل، بسألك الأول. عايز تضيف قيد إيه؟')),
    dict(name='spanning-periods', scenario='empty',
         variants=['how can a 3-hour lab fit if periods are 90 minutes?', 'explain sessions longer than one period', 'إزاي معمل 3 ساعات يتحط والفترة 90 دقيقة؟', 'كيف يوضع معمل مدته ثلاث ساعات والفترة 90 دقيقة؟'],
         reply=('A session may span consecutive named periods whose teaching minutes add up to its duration, so a 3-hour lab uses two adjacent 90-minute periods. '
                'A break of up to 30 minutes between them stays inside the session. If the periods are not consecutive, or the break is longer, the lab cannot span them.',
                'الحصة ممكن تاخد فترات ورا بعض مجموع دقايقها يساوي مدتها، فمعمل 3 ساعات بياخد فترتين متجاورتين كل واحدة 90 دقيقة. '
                'البريك اللي بينهم لو 30 دقيقة أو أقل بيبقى جوه الحصة. لو الفترات مش ورا بعض أو البريك أطول، المعمل مينفعش يمتد عليهم.')),
    dict(name='getting-started', scenario='empty',
         variants=['where do I start?', "I have an empty system, what's the order of setup?", 'النظام فاضي، أبدأ منين؟', 'من أين أبدأ إعداد النظام؟'],
         reply=('Start with the semester settings: teaching days, hours and periods. Then add rooms, instructors with their Doctor or TA role, student groups, and courses '
                'with their lectures, tutorials and labs; CSV import can speed this up. Next add constraints, run Check inputs, and generate a draft. '
                'Shall we begin with the semester settings?',
                'ابدأ بإعدادات الترم: أيام الدراسة والساعات والفترات. بعدها ضيف القاعات، والمحاضرين بدور Doctor أو TA، والجروبات، والمواد '
                'بمحاضراتها وسكاشنها ومعاملها، وممكن الـ CSV import يسرع ده. بعد كده ضيف القيود، وشغل Check inputs، وولد مسودة. '
                'نبدأ بإعدادات الترم؟')),
    dict(name='csv-in-chat', scenario='empty',
         variants=['can I upload my rooms spreadsheet in the chat?', 'import this csv for me', 'ممكن أرفع ملف الإكسل هنا؟', 'هل يمكنني رفع ملف إكسل في المحادثة؟'],
         reply=('Files cannot be uploaded through the chat. Use the import page and its file picker; it imports a CSV file atomically, so either every row is saved or none is. '
                'Save a spreadsheet as CSV first. After importing, I can help you check the records.',
                'مينفعش ترفع ملفات من الشات. استخدم صفحة الـ import واختار الملف من هناك، وهي بتستورد الـ CSV مرة واحدة: يا كل الصفوف تتحفظ يا ولا صف. '
                'احفظ ملف الإكسل كـ CSV الأول. وبعد الاستيراد أقدر أساعدك تراجع البيانات.')),
    dict(name='check-inputs', scenario='empty',
         variants=['explain what Check inputs does', 'should I run check inputs before generating?', 'يعني إيه Check inputs؟', 'ما فائدة Check inputs قبل التوليد؟'],
         reply=('Check inputs reviews your data before generation and names problems the solver would hit, such as a TA who cannot be given any session, an activity '
                'no room can host, or an instructor without a Doctor or TA role. Fixing those first saves a failed generation. '
                'It does not prove a timetable exists; only the solver can confirm that.',
                'Check inputs بيراجع بياناتك قبل التوليد وبيقولك على المشاكل اللي الـ solver هيقابلها، زي معيد مفيش حصة ينفع ياخدها، أو نشاط مفيش قاعة تستضيفه، '
                'أو محاضر من غير دور Doctor أو TA. لما تصلحها الأول بتوفر توليد فاشل. بس ده مش دليل إن الجدول ممكن، الـ solver بس هو اللي يأكد ده.')),
    dict(name='daily-limit', scenario='empty',
         variants=['is there a rule to limit daily hours for a group?', 'can I stop a group having more than 6 hours a day?', 'ينفع أحدد إن الجروب ميزدش عن 6 ساعات في اليوم؟', 'هل يمكن تحديد ساعات المجموعة في اليوم؟'],
         reply=('Yes. The student-group daily hour limit caps a group\'s teaching per day, and there is a similar one for instructors. As a mandatory rule it holds in every draft, '
                'but the same sessions must still fit, so with few teaching days it can make generation impossible. Which group and limit do you have in mind, '
                'and should it be mandatory or preferred?',
                'أيوه. فيه rule لحد أقصى لساعات الجروب في اليوم، وفيه زيه للمحاضرين. لو إجباري هيتحقق في كل مسودة، بس نفس الحصص لازم تتحط، '
                'فلو أيام الدراسة قليلة ممكن يخلي التوليد مستحيل. أنهي جروب وكام ساعة، وعايزه إجباري ولا مفضل؟')),
    dict(name='unavailability-vs-preference', scenario='week',
         variants=["how do I record that Dr Salma prefers mornings but can't teach Thursdays?", 'Dr. Salma Nabil likes morning slots and is away every Thursday, how do I enter that?', 'دكتورة سلمى بتحب الصبح ومش بتيجي الخميس، أدخل ده إزاي؟', 'كيف أسجل أن الدكتورة سلمى تفضل الصباح ولا تحضر يوم الخميس؟'],
         reply=('Those are two different things. Thursday is unavailability: it is recorded on her instructor record, approved, and then never violated. Mornings are a preferred teaching period, honoured when possible; a missed preference costs convenience. Shall we start with the Thursday unavailability?',
                'دول حاجتين مختلفين. الخميس ده عدم إتاحة: بيتسجل في بيانات المحاضرة، ويتعتمد، وبعدها عمره ما بيتكسر. الصبح ده فترة تدريس مفضلة، بتتحقق لما ينفع، والتفضيل اللي مايتحققش بيقلل الراحة. نبدأ بعدم الإتاحة يوم الخميس؟')),
    dict(name='confirming-changes', scenario='week',
         variants=['how do I confirm a change you prepare?', 'what happens after you propose a change?', 'بأكد التعديل اللي بتجهزه إزاي؟', 'كيف أؤكد التعديل الذي تقترحه؟'],
         reply=('Use the confirm button under the proposal, or reply with something explicit such as "yes, do it"; "cancel" rejects it. Before saving, the website checks the request again, '
                'including permissions and the data version, so if someone else changed the data in between, the change is refused rather than overwriting theirs.',
                'دوس زرار التأكيد تحت الاقتراح، أو رد بحاجة واضحة زي "أيوه نفذ"، و"إلغاء" بترفضه. قبل الحفظ الموقع بيراجع الطلب تاني، '
                'بما فيه الصلاحيات ورقم نسخة البيانات، فلو حد تاني عدل في النص، التعديل بيترفض بدل ما يكتب فوق شغله.')),

    # ---- Advising, exams, publishing ----
    dict(name='advising-students', scenario='empty',
         variants=['explain what advising students are', 'a student is retaking a course with another group, how is that handled?', 'طالب شايل مادة مع جروب تاني، بيتعمل إزاي؟', 'كيف يتم التعامل مع طالب يعيد مادة مع مجموعة أخرى؟'],
         reply=("Advising students are students whose courses differ from their group's, such as retakes or courses from another plan; an administrator adds them from the Student groups page. Each keeps their group's sessions except dropped courses and joins another group for added courses. None of their sessions may overlap, and each is an exam cohort of their own. Which student do you have in mind?",
                'طلاب الإرشاد هما الطلاب اللي موادهم مختلفة عن جروبهم، زي الشايلين مادة أو واخدين مادة من خطة تانية، والأدمن بيضيفهم من صفحة Student groups. كل طالب بياخد حصص جروبه ناقص المواد اللي سابها، وبيحضر مع جروب تاني المواد المضافة. ممنوع حصصه تتعارض، وبيتعامل كمجموعة امتحانات لوحده. بتفكر في أنهي طالب؟')),
    dict(name='exam-halls', scenario='exam',
         variants=['explain how exam halls and invigilators are assigned', 'how are rooms and proctors chosen for exams?', 'القاعات والمراقبين في الامتحانات بيتحددوا إزاي؟', 'كيف يتم توزيع قاعات الامتحانات والمراقبين؟'],
         reply=('Each exam gets halls marked Exam hall that together seat its students, and each hall needs a free TA invigilator. The planner avoids back-to-back exam days for a cohort and reports when they are unavoidable. If halls or TAs run short, more exam dates or halls usually help. Is a particular exam causing trouble?',
                'كل امتحان بياخد قاعات متعلم عليها Exam hall تكفي طلابه، وكل قاعة محتاجة معيد مراقب فاضي. المخطط بيحاول يتجنب امتحانات في أيام ورا بعض لنفس الطلاب، وبيقولك لو مينفعش. لو القاعات أو المعيدين مش كفاية، زيادة أيام أو قاعات الامتحانات غالباً بتحل. فيه امتحان معين عامل مشكلة؟')),
    dict(name='back-to-back-exams', scenario='exam',
         variants=['why does the midterm draft still have back-to-back exam days?', 'can you remove all consecutive exam days?', 'ليه لسه فيه امتحانات في أيام ورا بعض؟'],
         reply=('The planner avoids back-to-back exam days for a cohort, but with 12 courses between 21 and 30 November some may be unavoidable, and it reports when they are. More exam dates or halls usually help, for example extending the period. Would you like to look at extending the dates?',
                'المخطط بيحاول يتجنب امتحانات في أيام ورا بعض لنفس الطلاب، بس مع 12 مادة بين 21 و30 نوفمبر ممكن بعضها ميتجنبش، وبيقولك لما ده يحصل. زيادة أيام أو قاعات الامتحانات غالباً بتساعد، زي إنك تمد الفترة. تحب نشوف نمد التواريخ؟')),
    dict(name='exam-review', scenario='exam',
         variants=['the midterm draft is ready, what should I check before publishing?', 'what do I review in the exam draft?', 'أراجع إيه في جدول الميدترم قبل النشر؟'],
         reply=('Check that every course appears, no cohort has two exams at once, back-to-back and same-day exams are acceptable, every hall has an invigilator, '
                'and the dates fall inside 21 to 30 November. Computing midterms is not published yet, so you can still regenerate with more dates if needed. '
                'Would you like a PDF to review it?',
                'اتأكد إن كل المواد موجودة، ومفيش طلاب عندهم امتحانين في نفس الوقت، والامتحانات ورا بعض أو في نفس اليوم مقبولة، وكل قاعة ليها مراقب، '
                'والأيام جوه الفترة من 21 لـ 30 نوفمبر. Computing midterms لسه متنشرش، فلسه تقدر تولده تاني بأيام أكتر لو محتاج. تحب PDF تراجعه؟')),
    dict(name='is-published', scenario='week',
         variants=['is Draft 3 published?', 'can students already see this timetable?', 'الجدول ده اتنشر؟', 'هل تم نشر هذا الجدول؟'],
         reply=('No. Draft 3 is not published, so students and instructors cannot see it yet. Publishing re-validates it against the current approved inputs first, '
                'and only one teaching timetable can be published at a time. Would you like to publish it?',
                'لا. Draft 3 لسه متنشرش، فالطلاب والمحاضرين مش شايفينه. النشر بيراجعه الأول على المدخلات المعتمدة الحالية، '
                'وجدول تدريس واحد بس ينفع يبقى منشور في نفس الوقت. تحب تنشره؟')),
    dict(name='portal-view', scenario='week', holdout=True,
         variants=['what will students see after I publish?', 'what does an instructor see in their portal?', 'الطالب هيشوف إيه بعد النشر؟'],
         reply=('Students see only their own published sessions and exams; instructors see only their own teaching, and TAs also their invigilation duties. '
                'Each can download their schedule as CSV. Nobody sees drafts, other people\'s timetables or unpublished changes.',
                'الطالب بيشوف حصصه وامتحاناته المنشورة بس، والمحاضر بيشوف تدريسه هو بس، والمعيد كمان بيشوف المراقبة بتاعته. '
                'وكل واحد يقدر ينزل جدوله CSV. محدش بيشوف المسودات ولا جداول غيره ولا تعديلات متنشرتش.')),
    dict(name='stale-published', scenario='stale',
         variants=['why does it say the published timetable is stale?', 'the timetable is marked out of date, what does that mean?', 'ليه مكتوب إن الجدول المنشور قديم؟', 'لماذا يظهر أن الجدول المنشور قديم؟'],
         reply=('Stale means the approved inputs changed after Fall teaching v2 was generated, for example a room, an instructor\'s availability or a rule. '
                'Students still see it, but it may no longer match the data. The safe next step is to generate a new draft from the current inputs, '
                'compare it with this one, and publish it if it looks right. Shall we generate one?',
                'Stale معناها إن المدخلات المعتمدة اتغيرت بعد ما Fall teaching v2 اتولد، زي قاعة أو إتاحة محاضر أو rule. '
                'الطلاب لسه شايفينه، بس ممكن ميبقاش مطابق للبيانات. الخطوة الآمنة إنك تولد مسودة جديدة من المدخلات الحالية، '
                'وتقارنها بده، وتنشرها لو مظبوطة. نولد واحدة؟')),
    dict(name='unpublish-effect', scenario='stale',
         variants=['what happens if I unpublish the timetable?', 'if I take it down, can students still see it?', 'لو لغيت النشر الطلاب هيشوفوه؟', 'ماذا يحدث إذا ألغيت نشر الجدول؟'],
         reply=('Unpublishing removes Fall teaching v2 from the student and instructor portals, so they would see no teaching timetable until another one is published. '
                'The draft itself is kept. Since it is stale, a gentler path is to generate and check a new draft first, then publish it to replace this one.',
                'إلغاء النشر بيشيل Fall teaching v2 من بوابات الطلاب والمحاضرين، فمش هيشوفوا أي جدول تدريس لحد ما جدول تاني يتنشر. '
                'المسودة نفسها بتفضل محفوظة. وبما إنه قديم، الأهدى إنك تولد مسودة جديدة وتراجعها الأول، وبعدين تنشرها مكانه.')),
    dict(name='compare-drafts', scenario='week',
         variants=['how do I know if Draft 3 is better than Draft 2?', 'how does comparing two drafts work?', 'أعرف إزاي إن Draft 3 أحسن من Draft 2؟', 'كيف أعرف أن Draft 3 أفضل من Draft 2؟'],
         reply=('Use scenario comparison: it lists the sessions that moved between two drafts and shows their convenience metrics side by side, such as student gaps, '
                'days on campus and missed instructor preferences. Which draft is better depends on what you value most, so look at the terms you care about, '
                'not only the total. What matters most to you here?',
                'استخدم مقارنة السيناريوهات: بتوريك الحصص اللي اتنقلت بين المسودتين وبتعرض مقاييس الراحة جنب بعض، زي فراغات الطلاب '
                'وأيام الحضور وتفضيلات المحاضرين اللي متحققتش. أنهي أحسن بيعتمد على إيه أهم عندك، فبص على البنود اللي تهمك مش المجموع بس. '
                'إيه أهم حاجة بالنسبالك هنا؟')),
    dict(name='is-optimal', scenario='week',
         variants=['is this the best possible timetable?', 'so Draft 3 is optimal, right?', 'يعني Draft 3 أحسن جدول ممكن؟', 'هل هذا أفضل جدول ممكن؟'],
         reply=('Not necessarily. Draft 3 passed validation, so it satisfies every mandatory rule, and the solver improved convenience within its time limit. '
                'That is not proof that no better timetable exists. Comparing it with a draft generated with a longer search would show whether it can still be improved.',
                'مش شرط. Draft 3 عدى الـ validation، يعني محقق كل القيود الإجبارية، والـ solver حسن الراحة في حدود الوقت. '
                'بس ده مش دليل إن مفيش جدول أحسن. لو قارنته بمسودة اتولدت بوقت بحث أطول هتعرف إذا كان لسه ممكن يتحسن.')),

    # ---- Grounded in the timetable on screen (Draft 3, Applied Computing II G1) ----
    dict(name='free-days', scenario='week',
         variants=['which days does AC2G1 have no classes?', 'what days off does this group get?', 'الجروب ده فاضي أنهي أيام؟'],
         reply=('In Draft 3, this group has no sessions on Monday or Thursday. They come in on Saturday, Sunday, Tuesday and Wednesday, for eight sessions in total.',
                'في Draft 3، الجروب ملوش حصص يوم الاتنين ويوم الخميس. بيحضروا السبت والحد والتلات والأربع، والمجموع تمن حصص.')),
    dict(name='busiest-day', scenario='week', variants=["what's the heaviest day for this group?", 'which day is the busiest?', 'أنهي يوم أتقل؟'],
         reply=(BUSIEST_EN, BUSIEST_AR)),
    dict(name='count-sessions', scenario='week',
         variants=['how many sessions does this group have per week?', 'total weekly classes for AC2G1?', 'الجروب عنده كام حصة في الأسبوع؟'],
         reply=('Eight weekly sessions in Draft 3: four lectures, three of them shared with another group, three tutorials and one lab.',
                'تمن حصص في الأسبوع في Draft 3: أربع محاضرات، تلاتة منهم مشتركة مع جروب تاني، وتلات سكاشن، ومعمل واحد.')),
    dict(name='who-teaches-lab', scenario='week', variants=['who teaches the lab?', 'which TA runs the programming lab?', 'مين المعيد اللي بيدي المعمل؟'],
         reply=('Mona Hegazy teaches the Computer Programming lab on Tuesday from 10:15 to 11:45 in B5.101.',
                'منى حجازي هي اللي بتدي معمل Computer Programming يوم التلات من 10:15 لـ 11:45 في B5.101.')),
    dict(name='sunday-gap', scenario='week',
         variants=['why is there a gap on Sunday afternoon?', 'explain the empty slot between 13:30 and 15:45 on Sunday', 'ليه فيه فراغ يوم الحد بعد الضهر؟'],
         reply=('After the Discrete Mathematics lecture ends at 13:30, the next session is the Digital Media tutorial at 15:45, so the 13:45 period is empty. '
                'Student gaps are minimised but traded off against other terms; Youssef Amin or a suitable room may not have been free earlier, '
                'or moving it would have worsened something else. Shall we test a version without that gap?',
                'بعد ما محاضرة Discrete Mathematics بتخلص 13:30، الحصة اللي بعدها سكشن Digital Media الساعة 15:45، ففترة 13:45 فاضية. '
                'الـ solver بيقلل فراغات الطلاب بس بيوازنها مع بنود تانية؛ ممكن يوسف أمين أو قاعة مناسبة مكانوش فاضيين بدري، '
                'أو نقله كان هيبوظ حاجة تانية. نجرب نسخة من غير الفراغ ده؟')),
    dict(name='lighter-sunday', scenario='week', history=[U('which day is the busiest?'), A(BUSIEST_EN)], history_ar=[U('أنهي يوم أتقل؟'), A(BUSIEST_AR)],
         variants=['could we make Sunday lighter?', 'is there a way to take something off Sunday?', 'ممكن نخفف يوم الحد؟'],
         reply=(LIGHTER_EN,
                'ممكن. محاضرة وسكشن Computer Programming وسكشن Digital Media بتوع الجروب ده بس، فهما الأسهل في النقل. '
                'محاضرة Discrete Mathematics مشتركة مع جروب تاني، فلازم الجروبين يبقوا فاضيين. ولو نقلنا حصة للاتنين أو الخميس هيروح يوم من أيام إجازتهم. '
                'إيه الأهم: يوم حد أخف ولا يومين إجازة؟')),
    dict(name='move-shared', scenario='week',
         variants=['can we move the Discrete Mathematics lecture to Monday?', 'is moving the MATH 203 lecture to Monday possible?', 'ينفع ننقل محاضرة MATH 203 ليوم الاتنين؟'],
         reply=('Possibly, but it is a shared lecture: moving it moves it for every attending group, so all of them, Dr. Karim Adel and a large enough room must be free on Monday. '
                'It would also end this group\'s Monday day off. A moved draft is saved only if the independent validator passes. Do you want to try it as a scenario edit?',
                'ممكن، بس دي محاضرة مشتركة: نقلها بينقلها لكل الجروبات اللي بتحضرها، فلازم كلهم ودكتور كريم عادل وقاعة كبيرة كفاية يبقوا فاضيين يوم الاتنين. '
                'وكمان هتلغي إجازة الاتنين بتاعة الجروب ده. والمسودة المعدلة مش بتتحفظ غير لو الـ validator المستقل عداها. تحب نجربها كتعديل سيناريو؟')),
    dict(name='which-lecture', scenario='week',
         variants=['can the lecture go on Wednesday instead?', 'is there space on Wednesday for the lecture?', 'ينفع المحاضرة تبقى يوم الأربع؟'],
         reply=('This group has four lectures: Digital Media on Saturday, Computer Programming and Discrete Mathematics on Sunday, and Communication Skills on Wednesday. '
                'Which one do you mean?',
                'الجروب ده عنده أربع محاضرات: Digital Media يوم السبت، وComputer Programming وDiscrete Mathematics يوم الحد، وCommunication Skills يوم الأربع. '
                'تقصد أنهي واحدة؟')),
    dict(name='vague-fix', scenario='week', holdout=True, variants=['fix the timetable', 'the schedule is bad, sort it out', 'الجدول وحش، صلحه'],
         reply=('I can help, but first I need to know what is wrong. For this group, Draft 3 has a heavy Sunday with an empty 13:45 period, and an empty 12:00 period on Tuesday. '
                'Is it one of those, or something else, such as an instructor complaint or a room problem?',
                'أقدر أساعد، بس محتاج أعرف المشكلة إيه الأول. بالنسبة للجروب ده، Draft 3 فيه يوم حد تقيل وفترة 13:45 فاضية، وفترة 12:00 فاضية يوم التلات. '
                'المشكلة في حاجة من دول، ولا حاجة تانية زي شكوى من محاضر أو مشكلة في قاعة؟')),
    dict(name='no-early-classes', scenario='week', holdout=True,
         variants=['can you guarantee no classes at 8:30?', 'I want no 8:30 sessions at all, is that doable?', 'مش عايز أي حصص الساعة 8:30، ينفع؟'],
         reply=('I can prepare a constraint to avoid the first period. As a mandatory rule it holds in every valid draft, but it removes one of five daily periods, '
                'which may make generation fail. As a preferred rule the solver avoids 08:30 wherever it can. Which strength do you want?',
                'أقدر أجهز قيد يمنع أول فترة. لو إجباري هيتحقق في كل مسودة صالحة، بس هيشيل فترة من خمس فترات في اليوم، '
                'وده ممكن يخلي التوليد يفشل. لو مفضل، الـ solver هيتجنب 08:30 على قد ما يقدر. عايزه إجباري ولا مفضل؟')),
    dict(name='steps-new-lab', scenario='week',
         variants=['what steps do I need to add a new lab room, regenerate and publish?', 'I want a new lab, a fresh draft, and then publish it. How?', 'عايز أضيف معمل جديد وأولد جدول وأنشره، أعمل إيه؟'],
         reply=('Three steps, in order. First add the room with its capacity, the lab type and any features. Then generate a new draft, because existing drafts do not use new rooms. '
                'Finally review and publish it; publishing re-validates the draft. Shall we start with the room? I will need its code and capacity.',
                'تلات خطوات بالترتيب. الأول ضيف القاعة بسعتها ونوع معمل وأي مميزات. بعدين ولد مسودة جديدة، لأن المسودات الموجودة مش بتستخدم القاعات الجديدة. '
                'وفي الآخر راجعها وانشرها، والنشر بيراجعها تاني. نبدأ بالقاعة؟ محتاج الكود والسعة.')),
    dict(name='days-vs-load', scenario='week',
         variants=['explain the trade-off between fewer teaching days and lighter days', 'is it better to give students fewer days on campus or shorter days?', 'الأحسن أيام حضور أقل ولا أيام أخف؟', 'أيهما أفضل للطلاب: أيام حضور أقل أم أيام أخف؟'],
         reply=('It depends on what you value. Fewer teaching days mean fewer trips to campus, but the same sessions are packed into the remaining days, so days get longer '
                'and gaps or late periods become more likely. Lighter days spread the load but bring students in more often. The convenience score counts both, '
                'so you can compare drafts on each. Which do your students care about more?',
                'بيعتمد على إيه الأهم عندك. أيام أقل يعني مشاوير أقل للجامعة، بس نفس الحصص بتتحشر في الأيام الباقية، فاليوم بيطول '
                'وفرصة الفراغات أو الفترات المتأخرة بتزيد. الأيام الأخف بتوزع الحمل بس بتخلي الطلاب ييجوا أكتر. حساب الراحة بيعد الاتنين، '
                'فتقدر تقارن المسودات على كل واحد. طلابك يهمهم إيه أكتر؟')),
    dict(name='ta-workload', scenario='week', holdout=True,
         variants=['why does one TA have so many more sessions than another?', 'workload looks uneven between TAs', 'ليه معيد واخد حصص كتير عن التاني؟'],
         reply=("A TA's load depends on which activities list them as eligible, so a TA eligible for more activities can get more sessions. Uneven weekly load is penalised above 3, 6 and 12 hours, but it is a preference, not a rule. Widening eligibility usually balances it best. Which TAs are you comparing?",
                'عبء المعيد بيعتمد على الأنشطة اللي هو مسموحله يديها، فالمعيد المسموحله أنشطة أكتر ممكن ياخد حصص أكتر. عدم التوازن الأسبوعي عليه غرامة فوق 3 و6 و12 ساعة، بس ده تفضيل مش قاعدة. توسيع الأهلية غالباً أحسن طريقة للتوازن. بتقارن بين أنهي معيدين؟')),
    dict(name='ta-one-session', scenario='week',
         variants=['why is Omar Farouk teaching only one session?', 'Omar only has one tutorial, is that right?', 'ليه عمر فاروق واخد سكشن واحد بس؟'],
         reply=('In the sessions I can see, Omar Farouk teaches this group\'s Computer Programming tutorial on Sunday at 10:15; he may teach other groups too. '
                'Every TA must get at least one session; beyond that, his load depends on which activities list him as eligible. '
                'To give him more, make him eligible for more tutorials or labs.',
                'في الحصص اللي قدامي، عمر فاروق بيدي سكشن Computer Programming للجروب ده يوم الحد 10:15، وممكن يكون بيدي جروبات تانية. '
                'كل معيد لازم ياخد حصة واحدة على الأقل، وبعد كده عبؤه بيعتمد على الأنشطة اللي هو مسموحله يديها. '
                'لو عايز تديله أكتر، خليه مؤهل لسكاشن أو معامل أكتر.')),
    dict(name='salma-unavailable', scenario='week',
         variants=["what if Dr Salma can't come on Sundays anymore?", "Dr. Salma Nabil just told me she's unavailable on Sundays. What's the impact?", 'لو دكتورة سلمى مش هتقدر تيجي الحد، إيه اللي هيتأثر؟', 'ماذا لو أصبحت الدكتورة سلمى نبيل غير متاحة يوم الأحد؟'],
         reply=('In the sessions I can see, her Computer Programming lecture for this group is on Sunday at 08:30, so it would have to move. After you record and approve her Sunday '
                'unavailability, the next generated draft will place it on another day; Draft 3 itself does not change. Shall I prepare the unavailability for your confirmation?',
                'في الحصص اللي قدامي، محاضرتها Computer Programming للجروب ده يوم الحد 08:30، فلازم تتنقل. بعد ما تسجل عدم إتاحتها يوم الحد وتعتمده، '
                'المسودة الجاية هتحطها في يوم تاني، وDraft 3 نفسها مش هتتغير. أجهزلك عدم الإتاحة عشان تأكده؟')),
    dict(name='room-closure', scenario='week', holdout=True,
         variants=['what if B5.101 is closed for maintenance on Tuesday?', 'the computer lab B5.101 will be unavailable Tuesdays, what changes?', 'لو معمل B5.101 مقفول للصيانة يوم التلات؟'],
         reply=('The Computer Programming lab uses B5.101 on Tuesday at 10:15, so it would be affected. Record the room\'s unavailability for that time; after approval, '
                'the next draft will use another room with the Computer Lab feature if one is free. If no other room has that feature, generation may fail, '
                'so check the alternatives first.',
                'معمل Computer Programming بيستخدم B5.101 يوم التلات 10:15، فهيتأثر. سجل عدم إتاحة المعمل في الوقت ده، وبعد الاعتماد '
                'المسودة الجاية هتستخدم قاعة تانية فيها ميزة Computer Lab لو فيه واحدة فاضية. لو مفيش قاعة تانية بالميزة دي، التوليد ممكن يفشل، '
                'فاتأكد من البدائل الأول.')),
    dict(name='delete-used-room', scenario='week',
         variants=['what happens if I delete room H12?', "can I remove H12 even though it's used?", 'لو مسحت قاعة H12 هيحصل إيه؟', 'ماذا يحدث إذا حذفت القاعة H12؟'],
         reply=('H12 hosts the Computer Programming and Discrete Mathematics lectures in Draft 3. JadwAI refuses to delete a record while other records or rules still refer to it. '
                'Draft 3 keeps its own copy of the data it was built from, but new drafts would need other lecture rooms with enough seats. '
                'Do you want to delete it, or just stop using it for a while?',
                'H12 فيها محاضرات Computer Programming وDiscrete Mathematics في Draft 3. JadwAI بيرفض يمسح أي حاجة لسه فيه بيانات أو rules بتشاور عليها. '
                'Draft 3 محتفظة بنسختها من البيانات اللي اتعملت منها، بس المسودات الجديدة هتحتاج قاعات محاضرات تانية بكراسي كفاية. '
                'عايز تمسحها خالص، ولا توقف استخدامها فترة؟')),
    dict(name='room-list', scenario='week', variants=['how many rooms do we have?', 'which rooms are in the system?', 'عندنا كام قاعة؟'],
         reply=('The workspace has four rooms: H12, H5, C3.201 and B5.101.',
                'عندك أربع قاعات: H12 وH5 وC3.201 وB5.101.')),
    dict(name='unknown-group-se', scenario='week', holdout=True, variants=['what about the SE group?', "what's on SE's timetable?", 'وجدول SE؟'],
         reply=('I cannot find a group called SE. The groups I know are Applied Computing II G1 and Applied Computing II G2. Which one do you mean, or is SE in another programme?',
                'مش لاقي جروب اسمه SE. الجروبات اللي عندي Applied Computing II G1 وApplied Computing II G2. تقصد أنهي واحد، ولا SE في برنامج تاني؟')),

    # ---- Multi-turn: pronouns, corrections, disagreement, memory ----
    dict(name='pronoun-follow-up', scenario='week',
         history=[U('who teaches the Discrete Mathematics lecture?'), A('Dr. Karim Adel teaches it on Sunday from 12:00 to 13:30 in H12.')],
         history_ar=[U('مين بيدي محاضرة Discrete Mathematics؟'), A('دكتور كريم عادل بيديها يوم الحد من 12:00 لـ 13:30 في H12.')],
         variants=['who else attends it?', 'is it only for this group?', 'مين كمان بيحضرها؟'],
         reply=('It is a shared lecture: Applied Computing II G1 and Applied Computing II G2 attend it together, so any move must suit both groups.',
                'دي محاضرة مشتركة: Applied Computing II G1 وApplied Computing II G2 بيحضروها مع بعض، فأي نقل لازم يناسب الجروبين.')),
    dict(name='day-correction', scenario='week', holdout=True,
         history=[U('what does this group have on Thursday?'), A('This group has no sessions on Thursday in Draft 3; it is one of their two free days.')],
         history_ar=[U('الجروب عنده إيه يوم الخميس؟'), A('الجروب ملوش حصص يوم الخميس في Draft 3، ده واحد من يومين إجازتهم.')],
         variants=['sorry, I meant Tuesday', 'no, Tuesday not Thursday', 'لا قصدي التلات مش الخميس'], reply=(TUESDAY_EN, TUESDAY_AR)),
    dict(name='language-switch', scenario='week', history=[U('what does this group have on Tuesday?'), A(TUESDAY_EN)],
         variants=['ok and Wednesday?', 'what about Wednesday?', 'طب والأربع؟'],
         reply=('On Wednesday this group has one session: the Communication Skills lecture from 08:30 to 10:00 in H5 with Dr. Rania Fathy, shared with another group.',
                'يوم الأربع الجروب عنده حصة واحدة: محاضرة Communication Skills من 08:30 لـ 10:00 في H5 مع دكتورة رانيا فتحي، ومشتركة مع جروب تاني.')),
    dict(name='user-disagrees', scenario='week', holdout=True,
         history=[U('how many sessions are on Sunday?'), A('This group has four sessions on Sunday in Draft 3.')],
         history_ar=[U('فيه كام حصة يوم الحد؟'), A('الجروب عنده أربع حصص يوم الحد في Draft 3.')],
         variants=["that's wrong, I see five on Sunday", 'no, there are 5 sessions on Sunday on my screen', 'غلط، أنا شايف خمس حصص يوم الحد'],
         reply=('The draft I can read, Draft 3, shows four Sunday sessions for this group: 08:30, 10:15, 12:00 and 15:45. You may be looking at another group or another draft. '
                'Which group and draft are on your screen?',
                'المسودة اللي قدامي، Draft 3، فيها أربع حصص يوم الحد للجروب ده: 08:30 و10:15 و12:00 و15:45. ممكن تكون فاتح جروب تاني أو مسودة تانية. '
                'إيه الجروب والمسودة اللي قدامك؟')),
    dict(name='not-saved-yet', scenario='week', holdout=True, pending={'operation': 'PUT /api/records/{kind}/{ident}'},
         history=[U('change H5 capacity to 100'), A('I prepared the change: room H5 capacity becomes 100. Please confirm to apply it.')],
         history_ar=[U('خلي سعة H5 مية'), A('جهزت التعديل: سعة قاعة H5 هتبقى 100. أكد عشان يتنفذ.')],
         variants=['did you save it?', 'is the capacity updated now?', 'اتحفظ؟'],
         reply=('Not yet. The change is only prepared; nothing is saved until you confirm it with the button or a reply such as "yes, do it". Do you want to confirm it?',
                'لسه. التعديل متجهز بس، ومفيش حاجة بتتحفظ غير لما تأكد بالزرار أو برد زي "أيوه نفذ". تحب تأكده؟')),
    dict(name='summarise-discussion', scenario='week',
         history=[U('which day is the busiest?'), A(BUSIEST_EN), U('could we make Sunday lighter?'), A(LIGHTER_EN), U("let's keep both free days"),
                  A('Then Sunday can only be lightened within the four teaching days, by moving a session that belongs only to this group to Saturday, Tuesday or Wednesday.')],
         variants=['summarise what we decided', "so what's the conclusion?", 'لخصلي اتفقنا على إيه'],
         reply=('Sunday is this group\'s busiest day, with four sessions. You chose to keep Monday and Thursday free, so any change must move a session that belongs only to this group, '
                'such as the Digital Media tutorial, to Saturday, Tuesday or Wednesday. Nothing has been changed yet. Shall we try that as a scenario edit?',
                'يوم الحد أتقل يوم للجروب، فيه أربع حصص. انت اخترت تفضل إجازة الاتنين والخميس، فأي تعديل لازم ينقل حصة بتاعة الجروب ده بس، '
                'زي سكشن Digital Media، للسبت أو التلات أو الأربع. لسه مفيش أي حاجة اتغيرت. نجرب ده كتعديل سيناريو؟')),

    # ---- Honest limits: questions facts.guide does not cover, or answers with a verified "no" ----
    dict(name='not-sure-travel-time', scenario='week',
         variants=['does JadwAI account for travel time between campuses?', 'will the timetable leave time to walk between buildings?', 'الجدول بيحسب وقت المشي بين المباني؟'],
         reply=('I am not sure. The information I have about JadwAI does not cover travel time between buildings or campuses, so I would rather not guess. '
                'I can tell you which rooms this group uses on each day, if that helps.',
                'مش متأكد. المعلومات اللي عندي عن JadwAI مش بتقول حاجة عن وقت التنقل بين المباني، فمش عايز أخمن. '
                'أقدر أقولك الجروب ده بيستخدم أنهي قاعات كل يوم لو ده يفيدك.')),
    dict(name='not-sure-user-limit', scenario='week',
         variants=['how many people can use JadwAI at the same time?', 'is there a maximum number of users?', 'كام واحد يقدر يستخدم النظام في نفس الوقت؟'],
         reply=('I am not sure. I have no verified information about a limit on users at the same time. '
                'Whoever runs this server would know. Is there something in Draft 3 I can help with meanwhile?',
                'مش متأكد. معنديش معلومة مؤكدة عن حد أقصى لعدد المستخدمين في نفس الوقت. '
                'اللي مسؤول عن السيرفر ده هيعرف. فيه حاجة في Draft 3 أقدر أساعدك فيها؟')),
    dict(name='notifications', scenario='week',
         variants=['will students get an email when I publish?', 'does JadwAI send notifications to instructors?', 'الطلاب هيوصلهم إيميل لما أنشر؟', 'هل يرسل النظام إشعاراً للطلاب عند النشر؟'],
         reply=('No. JadwAI has no email, SMS or push notifications. After you publish, each person sees their timetable in their own portal '
                'and can download it as CSV, so you may want to tell them yourself that it is published.',
                'لا. JadwAI مفيهوش إيميل أو SMS أو إشعارات. بعد ما تنشر، كل واحد بيشوف جدوله في البوابة بتاعته ويقدر ينزله CSV، '
                'فممكن تبلغهم إنت إنه اتنشر.')),
    dict(name='not-sure-sis', scenario='week', holdout=True,
         variants=['can JadwAI pull students straight from the university system?', 'does it connect to our student information system?', 'ينفع JadwAI يسحب الطلاب من سيستم الجامعة على طول؟'],
         reply=('I am not sure about a direct connection; nothing I have mentions one. What I do know is that the import page imports a CSV file '
                'atomically, every row or none, so exporting the data as CSV from that system is the safe route.',
                'مش متأكد إن فيه ربط مباشر، مفيش حاجة عندي بتقول كده. اللي أعرفه إن صفحة الاستيراد بتستورد ملف CSV مرة واحدة، يا كل الصفوف يا ولا واحد، '
                'فالأضمن إنك تصدر البيانات من السيستم ده كـ CSV.')),
]


# Guide topics (backend/app/assistant_guide.py) whose statements each reply relies on. The builder checks that
# every wording's prompt actually contains them, so the model learns to answer from facts.guide, not memory.
GUIDE_TOPICS = {
    'capabilities': ['scope'], 'identity': ['privacy'], 'privacy': ['privacy'], 'out-of-scope': ['scope'],
    'password-help': ['roles'], 'viewer-role': ['roles'], 'hard-vs-soft': ['constraints'],
    'generation-failed': ['generation-failed'], 'doctors-and-tas': ['instructors'], 'special-rooms': ['rooms'],
    'convenience-score': ['convenience'], 'room-pool': ['rooms'], 'solver-simply': ['solver'], 'search-time': ['solver-time'],
    'typed-constraint-flow': ['constraints'], 'spanning-periods': ['periods'], 'getting-started': ['setup'], 'csv-in-chat': ['import'],
    'check-inputs': ['check-inputs'], 'daily-limit': ['daily-limits'], 'unavailability-vs-preference': ['unavailability', 'instructors'],
    'confirming-changes': ['confirming'], 'advising-students': ['advising'], 'exam-halls': ['exams'], 'back-to-back-exams': ['exams'],
    'is-published': ['publishing'], 'portal-view': ['portals'], 'stale-published': ['publishing'], 'unpublish-effect': ['publishing'],
    'compare-drafts': ['convenience'], 'is-optimal': ['convenience'], 'move-shared': ['shared-lectures'], 'no-early-classes': ['constraints'],
    'days-vs-load': ['convenience'], 'ta-workload': ['instructors'], 'ta-one-session': ['instructors'], 'salma-unavailable': ['unavailability'],
    'room-closure': ['unavailability'], 'delete-used-room': ['deleting'], 'notifications': ['unknown-features'], 'not-sure-sis': ['import'],
}
