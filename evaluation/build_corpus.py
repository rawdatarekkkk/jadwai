"""Author-owned synthetic examples; deterministic packaging, never model predictions."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
VERSION='0.1.0-draft'
LANGUAGES=('en','ar','arz','mixed')
RESERVED={6,10,18,21,23,24,27,32}


def rule(typ,target,day='Sunday',start=8,end=10):
    return {'kind':'rule','data':dict(title='Requirement',type=typ,day=day,start_hour=start,end_hour=end,strength='preferred' if typ=='preferred_period' else 'mandatory',**target)}


def gold(proposals=(),decision='ready',clarifications=(),unsupported=()):
    return dict(decision=decision,proposals=list(proposals),clarifications=list(clarifications),unsupported=list(unsupported))


def families():
    t={'instructor_id':'i-nour-hassan'};a={'activity_id':'a-ds'};g={'group_id':'g-cs2a'};r={'room_id':'r-lab1'}
    return [
    ('teacher-window',('Nour Hassan cannot teach on Sunday from 08:00 to 10:00.','لا يستطيع نور حسن التدريس يوم الأحد من 08:00 إلى 10:00.','نور حسن مش هيقدر يدرّس يوم الحد من 8 الصبح لـ10 الصبح.','Nour Hassan مش متاح Sunday من 08:00 لـ10:00.'),gold([rule('unavailable',t)])),
    ('teacher-preference',('Nour Hassan prefers teaching Monday from 10:00 to 12:00.','يفضّل نور حسن التدريس يوم الاثنين من 10:00 إلى 12:00.','نور حسن يفضّل يدرّس يوم الاتنين من 10 لـ12، بس ده تفضيل.','Nour Hassan prefers الاتنين 10:00–12:00.'),gold([rule('preferred_period',t,'Monday',10,12)])),
    ('room-closure',('Lab 1 is unavailable Tuesday from 12:00 to 14:00.','معمل 1 غير متاح يوم الثلاثاء من 12:00 إلى 14:00.','معمل 1 مقفول يوم التلات من 12 لـ2 الضهر.','Lab 1 unavailable التلات 12:00–14:00.'),gold([rule('room_unavailable',r,'Tuesday',12,14)])),
    ('group-closure',('Year 2 Computer Science Group A must have no classes Wednesday from 14:00 to 16:00.','يجب ألا تكون للمجموعة أ بالسنة الثانية علوم حاسب حصص الأربعاء من 14:00 إلى 16:00.','مجموعة أ سنة تانية حاسبات مينفعش يبقى عندها حصص الأربع من 2 لـ4 العصر.','Year 2 CS Group A مش متاحة Wednesday 14:00–16:00.'),gold([rule('group_unavailable',g,'Wednesday',14,16)])),
    ('activity-permitted',('Data Structures may be scheduled only Thursday from 08:00 to 12:00, with no other weekly window.','لا يجوز جدولة هياكل البيانات إلا الخميس من 08:00 إلى 12:00، ولا توجد نافذة أسبوعية أخرى.','هياكل البيانات تتحط بس يوم الخميس من 8 لـ12 ومفيش وقت تاني في الأسبوع.','Data Structures only الخميس 08:00–12:00، no other weekly window.'),gold([rule('activity_allowed',a,'Thursday',8,12)])),
    ('group-permitted',('Year 2 Computer Science Group A may attend only Sunday from 08:00 to 12:00 this week.','تقتصر دراسة المجموعة أ بالسنة الثانية علوم حاسب على الأحد من 08:00 إلى 12:00 أسبوعيًا.','مجموعة أ سنة تانية حاسبات تحضر بس الحد من 8 لـ12 في الأسبوع.','Year 2 CS Group A allowed only الأحد 08:00–12:00 weekly.'),gold([rule('group_allowed',g,'Sunday',8,12)])),
    ('multi-day-closure',('Nour Hassan is unavailable Monday and Tuesday from 08:00 to 10:00 on each day.','نور حسن غير متاح الاثنين والثلاثاء من 08:00 إلى 10:00 في كل يوم.','نور حسن مش متاح الاتنين والتلات من 8 لـ10 في كل يوم.','Nour Hassan unavailable الاتنين والتلات 08:00–10:00 each day.'),gold([rule('unavailable',t,'Monday'),rule('unavailable',t,'Tuesday')])),
    ('alternative-activity-windows',('Data Structures must fit either Sunday 08:00–10:00 or Monday 08:00–10:00; no other times.','يجب أن تقع هياكل البيانات إما الأحد 08:00–10:00 أو الاثنين 08:00–10:00 فقط.','هياكل البيانات يا الحد من 8 لـ10 يا الاتنين من 8 لـ10، وبس.','Data Structures either الأحد 08:00–10:00 or Monday 08:00–10:00 فقط.'),gold([rule('activity_allowed',a),rule('activity_allowed',a,'Monday')])),
    ('weekly-hours',('Set Nour Hassan’s maximum weekly teaching load to 6 hours.','اجعل الحد الأقصى لعبء نور حسن التدريسي الأسبوعي 6 ساعات.','خلي أقصى تدريس لنور حسن في الأسبوع 6 ساعات.','Nour Hassan max weekly teaching load = 6 ساعات.'),gold([{'kind':'instructor_weekly_limit','data':{'instructor_id':'i-nour-hassan','max_weekly_hours':6}}])),
    ('global-daily-hours',('Set the global daily teaching maximum to 6 hours for students and 6 hours for instructors.','اجعل الحد اليومي العام للتدريس 6 ساعات للطلاب و6 ساعات للمدرسين.','خلي الحد اليومي العام 6 ساعات للطلبة و6 ساعات للدكاترة.','Global daily caps: students 6 ساعات، instructors 6 ساعات.'),gold([{'kind':'realism_policy','data':{'student_daily_hours':6,'instructor_daily_hours':6}}])),
    ('full-assignment-lock',('Keep the instructor, day/time and room of Data Structures occurrence 1 from the context draft fixed.','ثبّت المدرس واليوم والوقت والقاعة للحصة الأولى لهياكل البيانات من المسودة المرفقة بالسياق.','ثبّت الدكتور واليوم والوقت والقاعة بتوع أول حصة هياكل بيانات في مسودة السياق.','Lock instructor, day/time and room للحصة الأولى Data Structures من context draft.'),gold([{'kind':'assignment_lock','data':{'source_run_id':'11111111-1111-4111-8111-111111111111','activity_id':'a-ds','occurrence':0,'keep_instructor':True,'keep_time':True,'keep_room':True}}])),
    ('whole-teaching-day',('Nour Hassan is unavailable for the entire Tuesday teaching day.','نور حسن غير متاح طوال يوم الثلاثاء الدراسي.','نور حسن مش متاح يوم التلات الدراسي كله.','Nour Hassan unavailable طول teaching day يوم Tuesday.'),gold([rule('unavailable',t,'Tuesday',8,18)])),
    ('negated-closure-operation',('Nour Hassan is not unavailable Sunday 08:00–10:00.','نور حسن ليس غير متاح الأحد 08:00–10:00.','نور حسن مش غير متاح الحد من 8 لـ10.','Nour Hassan is not unavailable الأحد 08:00–10:00.'),gold(decision='clarify',clarifications=['operation_required_for_negated_closure'])),
    ('missing-day',('Nour Hassan cannot teach from 08:00 to 10:00.','لا يستطيع نور حسن التدريس من 08:00 إلى 10:00.','نور حسن مش هيقدر يدرّس من 8 لـ10.','Nour Hassan unavailable من 08:00 لـ10:00.'),gold(decision='clarify',clarifications=['day_required'])),
    ('missing-time',('Nour Hassan is unavailable Sunday, but I have not specified which hours.','نور حسن غير متاح الأحد، لكنني لم أحدد الساعات.','نور حسن مش متاح الحد بس لسه محددتش الساعات.','Nour Hassan unavailable Sunday بس hours مش محددة.'),gold(decision='clarify',clarifications=['time_window_required'])),
    ('unknown-instructor',('Mona Adel cannot teach Sunday 08:00–10:00.','منى عادل لا تستطيع التدريس الأحد 08:00–10:00.','منى عادل مش هتقدر تدرّس الحد من 8 لـ10.','Mona Adel unavailable الحد 08:00–10:00.'),gold(decision='clarify',clarifications=['unknown_instructor'])),
    ('ambiguous-instructor',('Nour cannot teach Sunday 08:00–10:00.','نور لا يستطيع التدريس الأحد 08:00–10:00.','نور مش هيقدر يدرّس الحد من 8 لـ10.','Nour unavailable الأحد 08:00–10:00.'),gold(decision='clarify',clarifications=['ambiguous_instructor'])),
    ('vague-early',('Nour Hassan prefers early classes on Sunday.','يفضّل نور حسن الحصص المبكرة يوم الأحد.','نور حسن عايز حصصه بدري يوم الحد.','Nour Hassan prefers early يوم Sunday.'),gold(decision='clarify',clarifications=['early_threshold_required'])),
    ('before-boundary',('Nour Hassan cannot teach before 10:00 on Sunday.','لا يستطيع نور حسن التدريس قبل 10:00 يوم الأحد.','نور حسن مينفعش يدرّس قبل 10 الصبح يوم الحد.','Nour Hassan unavailable before 10:00 يوم Sunday.'),gold([rule('unavailable',t)])),
    ('minute-precision',('Nour Hassan is unavailable Sunday from 10:15 to 11:45 exactly; do not round the times.','نور حسن غير متاح الأحد من 10:15 إلى 11:45 بالضبط؛ لا تقرّب الوقت.','نور حسن مش متاح الحد من 10 وربع لـ12 إلا ربع بالظبط، متقربش الوقت.','Nour Hassan unavailable الأحد 10:15–11:45 exactly، no rounding.'),gold(decision='unsupported',unsupported=['manual_rule_minute_precision_not_supported'])),
    ('outside-teaching-days',('Nour Hassan cannot teach Friday 08:00–10:00.','لا يستطيع نور حسن التدريس الجمعة 08:00–10:00.','نور حسن مينفعش يدرّس الجمعة من 8 لـ10.','Nour Hassan unavailable Friday من 08:00 لـ10:00.'),gold(decision='clarify',clarifications=['outside_current_calendar'])),
    ('hard-window-contradiction',('Data Structures must be only Sunday 08:00–10:00, and Year 2 Computer Science Group A must be unavailable for that entire interval.','يجب أن تقع هياكل البيانات فقط الأحد 08:00–10:00، ويجب منع حصص المجموعة أ سنة ثانية علوم حاسب طوال نفس الفترة.','هياكل البيانات لازم بس الحد من 8 لـ10، ومجموعة أ سنة تانية حاسبات ممنوعة من الحضور نفس الفترة كلها.','Data Structures only Sunday 08:00–10:00، وYear 2 CS Group A unavailable نفس الفترة كلها.'),gold([rule('activity_allowed',a),rule('group_unavailable',g)],decision='conflict',clarifications=['hard_window_has_no_placement'])),
    ('campus-travel',('Require 45 minutes of campus travel time between Nour Hassan’s classes.','اشترط 45 دقيقة للانتقال بين الحرم الجامعي بين حصص نور حسن.','لازم نور حسن يبقى عنده 45 دقيقة عشان ينقل بين الحرمين بين الحصص.','Nour Hassan needs 45 minutes campus travel بين الحصص.'),gold(decision='unsupported',unsupported=['campus_travel_not_supported'])),
    ('mixed-exam-and-room',('Lab 1 is unavailable Tuesday 12:00–14:00; also schedule the final exams.','معمل 1 غير متاح الثلاثاء 12:00–14:00؛ وجدول الامتحانات النهائية أيضًا.','معمل 1 مقفول التلات من 12 لـ2، وجدول امتحانات الفاينل كمان.','Lab 1 unavailable Tuesday 12:00–14:00، وكمان schedule final exams.'),gold([rule('room_unavailable',r,'Tuesday',12,14)],decision='mixed',unsupported=['exam_timetabling_not_supported'])),
    ('missing-historical-reference',('Give Nour Hassan the same restrictions as last week.','طبّق على نور حسن قيود الأسبوع الماضي نفسها.','حط لنور حسن نفس قيود الأسبوع اللي فات.','Nour Hassan نفس restrictions بتاعة last week.'),gold(decision='clarify',clarifications=['historical_context_required'])),
    ('unspecified-group',('Group A is unavailable Wednesday 14:00–16:00.','المجموعة أ غير متاحة الأربعاء 14:00–16:00.','مجموعة أ مش متاحة الأربع من 2 لـ4.','Group A unavailable الأربعاء 14:00–16:00.'),gold(decision='clarify',clarifications=['ambiguous_group'])),
    ('conflicting-scalar-update',('Set Nour Hassan’s single maximum weekly teaching-hours field to exactly 6 and exactly 3 at the same time.','اضبط حقل الحد الأسبوعي الوحيد لساعات تدريس نور حسن على 6 بالضبط و3 بالضبط في الوقت نفسه.','خلي نفس خانة الحد الأسبوعي لنور حسن 6 بالظبط و3 بالظبط في نفس الوقت.','Set Nour Hassan same max_weekly_hours field to exactly 6 وexactly 3 simultaneously.'),gold([{'kind':'instructor_weekly_limit','data':{'instructor_id':'i-nour-hassan','max_weekly_hours':6}},{'kind':'instructor_weekly_limit','data':{'instructor_id':'i-nour-hassan','max_weekly_hours':3}}],decision='conflict',clarifications=['conflicting_scalar_values'])),
    ('silent-hard-relaxation',('Ignore room capacity limits whenever they prevent a schedule.','تجاهل حدود سعة القاعات كلما منعت إنشاء الجدول.','طنش سعة القاعات لو هتعطل الجدول.','Ignore room capacity لو بتمنع generation.'),gold(decision='unsupported',unsupported=['hard_capacity_relaxation_not_supported'])),
    ('missing-polarity',('Nour Hassan, Sunday, 08:00–10:00.','نور حسن، الأحد، 08:00–10:00.','نور حسن، الحد، من 8 لـ10.','Nour Hassan، Sunday، 08:00–10:00.'),gold(decision='clarify',clarifications=['rule_type_and_strength_required'])),
    ('alternative-preferences',('Nour Hassan prefers either Monday 10:00–12:00 or Wednesday 14:00–16:00.','يفضّل نور حسن إما الاثنين 10:00–12:00 أو الأربعاء 14:00–16:00.','نور حسن يفضّل يا الاتنين من 10 لـ12 يا الأربع من 2 لـ4.','Nour Hassan prefers Monday 10:00–12:00 أو Wednesday 14:00–16:00.'),gold([rule('preferred_period',t,'Monday',10,12),rule('preferred_period',t,'Wednesday',14,16)])),
    ('session-to-hours-unit',('Limit Nour Hassan to at most four 90-minute teaching sessions per week, measured as teaching hours.','اجعل الحد الأسبوعي لنور حسن أربع حصص تدريس مدتها 90 دقيقة للحصة، محسوبًا بساعات التدريس.','نور حسن أقصى حاجة أربع حصص 90 دقيقة في الأسبوع، واحسب الحد بالساعات.','Nour Hassan max four 90-minute sessions/week، convert to teaching hours.'),gold([{'kind':'instructor_weekly_limit','data':{'instructor_id':'i-nour-hassan','max_weekly_hours':6}}])),
    ('zero-weekly-cap',('Nour Hassan must have zero weekly teaching hours.','يجب أن تكون ساعات تدريس نور حسن الأسبوعية صفرًا.','نور حسن ميدرسش أي ساعات في الأسبوع.','Nour Hassan weekly teaching cap = صفر hours.'),gold([{'kind':'instructor_weekly_limit','data':{'instructor_id':'i-nour-hassan','max_weekly_hours':0}}])),
    ]


def write_json(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def read_release_is_reviewed():
    return json.loads((ROOT/'manifest.json').read_text())['independently_adjudicated']


def build():
    if (ROOT/'manifest.json').exists() and read_release_is_reviewed():
        raise ValueError('Refusing to overwrite a release marked independently adjudicated')
    context={'id':'synthetic-dept-v1','provenance':'Original synthetic fixtures; no real institutional or personal data.',
      'calendar':{'days':['Sunday','Monday','Tuesday','Wednesday','Thursday'],'start_hour':8,'end_hour':18,'timezone':'Africa/Cairo','teaching_periods':[{'start':510,'end':600},{'start':615,'end':705},{'start':720,'end':810},{'start':825,'end':915},{'start':945,'end':1035}]},
      'instructors':[{'id':'i-nour-hassan','name':'Nour Hassan','aliases':['نور حسن']},{'id':'i-nour-ali','name':'Nour Ali','aliases':['نور علي']}],
      'rooms':[{'id':'r-lab1','name':'Lab 1','aliases':['معمل 1'],'capacity':30,'room_type':'flexible'}],
      'groups':[{'id':'g-cs2a','name':'Year 2 Computer Science Group A','aliases':['Year 2 CS Group A','المجموعة أ سنة ثانية علوم حاسب'],'size':20},{'id':'g-is2a','name':'Year 2 Information Systems Group A','aliases':['Year 2 IS Group A','المجموعة أ سنة ثانية نظم معلومات'],'size':20}],
      'activities':[{'id':'a-ds','name':'Data Structures','aliases':['هياكل البيانات','هياكل بيانات'],'group_ids':['g-cs2a'],'eligible_instructors':['i-nour-hassan'],'sessions':1,'duration':90}],
      'source_draft':{'id':'11111111-1111-4111-8111-111111111111','validated':True,'assignments':[{'activity_id':'a-ds','occurrence':0,'instructor_id':'i-nour-hassan','room_id':'r-lab1','day':'Sunday','start_minute':510,'end_minute':600}]},
      'definitions':{'early':None,'groups_are_disjoint':True,'rule_hours_are_integers':True,'occurrence_display_is_one_based':True,'occurrence_payload_is_zero_based':True}}
    write_json(ROOT/'data/contexts.json',[context])
    partitions={'development':[],'reserved':[]}
    for n,(topic,texts,expected) in enumerate(families(),1):
        split='reserved' if n in RESERVED else 'development'
        for lang,text in zip(LANGUAGES,texts,strict=True):
            partitions[split].append({'id':f'jdw-{n:03}-{lang}','family_id':f'family-{n:03}','topic':topic,'language':lang,'split':split,'context_id':context['id'],'text':text,'gold':expected,'review_status':'draft_unreviewed'})
    for split,rows in partitions.items():
        path=ROOT/f'data/{split}/cases.jsonl'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(''.join(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n' for row in rows),encoding='utf-8')
    paths=['data/contexts.json','data/development/cases.jsonl','data/reserved/cases.jsonl','annotation-guide.md','proposal-contract.schema.json','build_corpus.py','runner.py']
    write_json(ROOT/'manifest.json',{'dataset_version':VERSION,'schema_version':'proposal-contract-v1','annotation_version':'annotation-guide-v1','synthetic':True,'independently_adjudicated':False,'reserved_is_blind':False,'split_unit':'intent-template family; all translations stay together','files':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths},'counts':{k:len(v) for k,v in partitions.items()}})

if __name__=='__main__':build()
