"""Dated two-hour exam drafts from course/program metadata.

With exam halls in the snapshot, each exam also gets one or more halls whose seats cover
its students, and every hall in use gets a TA invigilator who is free at that time.
Snapshots without halls (older drafts) keep the date-and-time-only behaviour."""
from collections import defaultdict,Counter
from datetime import date,timedelta
import re
from math import ceil
from ortools.sat.python import cp_model

SLOTS=[('09:00','11:00'),('11:15','13:15'),('13:30','15:30')]
WEEKDAYS=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
# Programs whose students also sit specialisation exams of the same faculty/semester,
# and spelling families that collapse to one track. Editable per workspace.
DEFAULT_COHORT_RULES={'broad_programs':['businessadministration','businessadministrationcore','informaticsandcomputerscience'],
    'tracks':{'ENGINEERING':['automotivemechatronics','roboticsandautomation','manufacturingengineering','automationandcontrolengineering','electricalpowersystemsengineering']},
    'aliases':{'mechanicalengineeringmanufacturing':'manufacturingengineering'}}
EXAM_WEIGHTS={'back_to_back_days':10,'peak_slot':3,'halls_used':1}


def minutes(text):
    h,m=text.split(':');return int(h)*60+int(m)

def course_inputs(courses,rules=None,sizes=None):
    rules=rules or DEFAULT_COHORT_RULES;sizes=sizes or {}
    rows=[];missing=[];labels={}
    for c in courses:
        participants=[]
        for group in c.group_ids:participants.append('group:'+group)
        for p in (c.source_info or {}).get('program_semesters',[]):
            faculty=p.get('faculty_section','');program=p.get('program_or_cohort') or faculty
            clean=re.sub(r'[^a-z0-9]','',program.lower())
            for track in rules.get('tracks',{}).get(faculty,[]):
                if track in clean:clean=track;break
            clean=rules.get('aliases',{}).get(clean,clean)
            semester=p.get('semester')
            key=f'{faculty}:{clean}:{semester or "all"}'
            participants.append(key);labels[key]={'faculty':faculty,'program':clean,'semester':semester}
        if not participants:missing.append(c.code)
        students=sum(sizes.get(g,0) for g in c.group_ids) if c.group_ids else getattr(c,'expected_students',None)
        rows.append({'id':c.id,'name':c.name,'code':c.code,'participants':sorted(set(participants)),'programs':(c.source_info or {}).get('program_semesters',[]),'students':students or None})
    # General/core cohorts conservatively share students with specialization cohorts.
    for row in rows:
        expanded=set(row['participants'])
        for key in row['participants']:
            if key not in labels:continue
            label=labels[key]
            broad=label['program'] in rules.get('broad_programs',[])
            for other,target in labels.items():
                if target['faculty']!=label['faculty']:continue
                same_semester=target['semester']==label['semester'] or label['semester'] is None
                if same_semester and (broad or label['program']==target['program']):expanded.add(other)
        row['participants']=sorted(expanded)
    return rows,missing

def ta_free(ta,day,slot):
    """A TA may invigilate unless it is their day off or an approved unavailability overlaps."""
    weekday=WEEKDAYS[date.fromisoformat(day).weekday()]
    if ta.get('day_off')==weekday:return False
    low,high=minutes(slot[0]),minutes(slot[1])
    return not any((r.get('day') in (None,weekday)) and low<round(r['end_hour']*60) and round(r['start_hour']*60)<high for r in ta.get('unavailable',[]))


def generate_exam_draft(snapshot):
    courses=snapshot['courses'];days=snapshot['dates'];per_day=snapshot['max_exams_per_cohort_day']
    with_halls='halls' in snapshot
    halls=snapshot.get('halls',[]);tas=snapshot.get('invigilators')
    if not courses:return {'status':'blocked','reason':'no_courses','assignments':[], 'recommendations':[{'action':'add_courses','message':'Add courses before generating an exam timetable.'}]}
    if snapshot['missing_cohort_codes']:return {'status':'blocked','reason':'missing_cohorts','course_codes':snapshot['missing_cohort_codes'],'assignments':[], 'recommendations':[{'action':'complete_cohorts','message':'Add the missing program/semester or student-group eligibility for the listed courses so conflicts can be checked.'}]}
    if with_halls:
        if not halls:return {'status':'blocked','reason':'no_exam_halls','assignments':[],'recommendations':[{'action':'add_exam_halls','message':'Mark rooms as Exam hall and set their capacity.'}]}
        unknown=[c['code'] for c in courses if not c.get('students')]
        if unknown:return {'status':'blocked','reason':'missing_student_counts','course_codes':unknown,'assignments':[],'recommendations':[{'action':'set_student_counts','message':'Link student groups to these courses or enter the expected number of students.'}]}
        seats=sum(h['capacity'] for h in halls)
        too_big=[c['code'] for c in courses if c['students']>seats]
        if too_big:return {'status':'blocked','reason':'hall_capacity','course_codes':too_big,'assignments':[],'recommendations':[{'action':'add_exam_halls','message':'These exams have more students than all exam halls together can seat.'}]}
        if tas is not None and not tas:return {'status':'blocked','reason':'no_invigilators','assignments':[],'recommendations':[{'action':'add_tas','message':'Mark instructors as TAs so they can invigilate.'}]}
    memberships=defaultdict(list)
    for i,c in enumerate(courses):
        for cohort in c['participants']:memberships[cohort].append(i)
    daily=min(per_day,len(SLOTS))
    crowded=[{'cohort':cohort,'exams':len(ids),'available_days':len(days)} for cohort,ids in memberships.items() if len(ids)>len(days)*daily]
    if crowded:
        required_days=max(ceil(len(ids)/daily) for ids in memberships.values())
        recommendations=[{'action':'extend_period','required_days':required_days,'additional_days':required_days-len(days),'message':f'Use at least {required_days} eligible exam days ({required_days-len(days)} more than currently selected) while keeping the daily maximum at {per_day}.'}]
        required_daily=max(ceil(len(ids)/len(days)) for ids in memberships.values()) if days else 4
        if per_day<required_daily<=len(SLOTS):recommendations.append({'action':'raise_daily_limit','daily_limit':required_daily,'message':f'Alternatively, raise the daily maximum to at least {required_daily} exams per cohort. Review student workload before changing this policy.'})
        recommendations.append({'action':'review_cohorts','message':'Review the affected courses’ program/semester eligibility for incorrect overlap. Keep genuine shared cohorts together.'})
        return {'status':'infeasible','reason':'not_enough_days','details':crowded,'assignments':[],'recommendations':recommendations,'recommendation_note':'These are capacity requirements, not a guarantee. Generate again after adjusting constraints to verify the complete timetable.'}
    model=cp_model.CpModel();x={}
    for i in range(len(courses)):
        for d in range(len(days)):
            for s in range(3):x[i,d,s]=model.new_bool_var(f'exam_{i}_{d}_{s}')
        model.add_exactly_one(x[i,d,s] for d in range(len(days)) for s in range(3))
    for ids in memberships.values():
        for d in range(len(days)):
            model.add(sum(x[i,d,s] for i in ids for s in range(3))<=per_day)
            for s in range(3):model.add_at_most_one(x[i,d,s] for i in ids)
    peak=model.new_int_var(0,len(courses),'peak_slot_exams')
    for d in range(len(days)):
        for s in range(3):model.add(sum(x[i,d,s] for i in range(len(courses)))<=peak)
    terms={'peak_slot':[peak]}
    # A cohort sitting exams on two consecutive calendar days is inconvenient.
    sits={}
    for cohort,ids in memberships.items():
        for d in range(len(days)):
            sits[cohort,d]=model.new_bool_var(f'sits_{cohort}_{d}')
            model.add_max_equality(sits[cohort,d],[x[i,d,s] for i in ids for s in range(3)])
    back_to_back=[]
    for cohort in memberships:
        for d in range(len(days)-1):
            if (date.fromisoformat(days[d+1])-date.fromisoformat(days[d])).days==1:
                both=model.new_bool_var(f'b2b_{cohort}_{d}')
                model.add(both>=sits[cohort,d]+sits[cohort,d+1]-1)
                back_to_back.append(both)
    terms['back_to_back_days']=back_to_back
    use={}
    if with_halls:
        y={(i,h):model.new_bool_var(f'hall_{i}_{h}') for i in range(len(courses)) for h in range(len(halls))}
        for i,c in enumerate(courses):
            model.add(sum(halls[h]['capacity']*y[i,h] for h in range(len(halls)))>=c['students'])
        for h in range(len(halls)):
            for d in range(len(days)):
                for s in range(3):
                    in_use=[]
                    for i in range(len(courses)):
                        z=model.new_bool_var(f'use_{i}_{h}_{d}_{s}')
                        model.add_bool_and([x[i,d,s],y[i,h]]).only_enforce_if(z)
                        model.add_bool_or([x[i,d,s].Not(),y[i,h].Not()]).only_enforce_if(z.Not())
                        use[i,h,d,s]=z;in_use.append(z)
                    model.add_at_most_one(in_use)
        if tas is not None:
            for d,day in enumerate(days):
                for s,slot in enumerate(SLOTS):
                    free=sum(ta_free(t,day,slot) for t in tas)
                    model.add(sum(use[i,h,d,s] for i in range(len(courses)) for h in range(len(halls)))<=free)
        terms['halls_used']=list(y.values())
    model.minimize(sum(EXAM_WEIGHTS[k]*sum(v) for k,v in terms.items()))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=snapshot.get('time_limit_seconds',20);solver.parameters.num_search_workers=4;solver.parameters.random_seed=42
    outcome=solver.solve(model)
    if outcome not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        infeasible=outcome==cp_model.INFEASIBLE
        return {'status':'infeasible' if infeasible else 'unknown','reason':'search_outcome','assignments':[], 'recommendations':[
            {'action':'extend_period' if infeasible else 'retry','message':'Add eligible exam dates, exam halls or available TAs; then generate again.' if infeasible else 'The search stopped without a result; this does not prove infeasibility. Retry generation or allow a longer exam period.'},
            {'action':'review_cohorts','message':'Review shared program/semester memberships. Raising the daily maximum alone cannot resolve courses that must occupy the same limited set of slots.'}
        ],'recommendation_note':'Suggested adjustments must be verified by generating again.'}
    assignments=[]
    load=Counter()
    for i,c in enumerate(courses):
        for d,day in enumerate(days):
            for s,(start,end) in enumerate(SLOTS):
                if not solver.value(x[i,d,s]):continue
                row={'course_id':c['id'],'course_name':c['name'],'course_code':c['code'],'date':day,'start_time':start,'end_time':end,'duration_minutes':120,'programs':c['programs']}
                if with_halls:
                    row['students']=c['students']
                    row['halls']=[{'room_id':halls[h]['id'],'room_code':halls[h]['code'],'capacity':halls[h]['capacity'],'invigilator_id':None} for h in range(len(halls)) if solver.value(use[i,h,d,s])]
                assignments.append(row)
    if with_halls and tas is not None:
        # Per slot any free TA can take any hall, so a least-loaded-first assignment
        # always succeeds when the solver kept halls in use <= free TAs.
        for (day,start),rows in sorted(_group(assignments).items()):
            slot=next(sl for sl in SLOTS if sl[0]==start)
            taken=set()
            for row in rows:
                for hall in row['halls']:
                    choice=min((t for t in tas if t['id'] not in taken and ta_free(t,day,slot)),key=lambda t:(load[t['id']],t['id']))
                    hall['invigilator_id'],hall['invigilator_name']=choice['id'],choice['name']
                    taken.add(choice['id']);load[choice['id']]+=1
    validation=validate_exam_draft(snapshot,assignments)
    if not validation['passed']:return {'status':'failed','reason':'independent_validation_failed','validation':validation,'assignments':[]}
    limitations=['Conflict checks use course program/semester labels and configured group IDs, not individual enrolments.','A draft requires institutional review before use.']
    if not with_halls:limitations.insert(0,'Dates and times only; rooms and invigilators are not assigned.')
    observed=exam_convenience(snapshot,assignments)
    return {'status':'completed','assignments':sorted(assignments,key=lambda a:(a['date'],a['start_time'],a['course_code'])),'validation':validation,'solver_seconds':solver.wall_time,'optimal_for_slot_balance':outcome==cp_model.OPTIMAL,'convenience':observed,'invigilation_load':dict(load),'limitations':limitations}


def _group(assignments):
    groups=defaultdict(list)
    for a in assignments:groups[(a['date'],a['start_time'])].append(a)
    return groups


def exam_convenience(snapshot,assignments):
    """Independently counted: cohort back-to-back exam days, busiest slot, halls used."""
    courses={c['id']:c for c in snapshot['courses']};days_by_cohort=defaultdict(set);slots=Counter()
    for a in assignments:
        slots[(a['date'],a['start_time'])]+=1
        for cohort in courses[a['course_id']]['participants']:days_by_cohort[cohort].add(date.fromisoformat(a['date']))
    back=sum(1 for days in days_by_cohort.values() for d in days if d+timedelta(days=1) in days)
    return {'back_to_back_days':back,'peak_slot':max(slots.values(),default=0),'halls_used':sum(len(a.get('halls',[])) for a in assignments)}


def validate_exam_draft(snapshot,assignments):
    courses={c['id']:c for c in snapshot['courses']};errors=[];counts=Counter(a.get('course_id') for a in assignments)
    if set(counts)!=set(courses) or any(n!=1 for n in counts.values()):errors.append('course_coverage')
    cohort_days=Counter();cohort_slots=Counter()
    with_halls='halls' in snapshot
    halls={h['id']:h for h in snapshot.get('halls',[])};tas={t['id']:t for t in snapshot.get('invigilators') or []}
    hall_slots=Counter();ta_slots=Counter()
    for a in assignments:
        c=courses.get(a.get('course_id'))
        if not c:continue
        if a.get('course_code') != c['code'] or a.get('course_name') != c['name']:errors.append('course_identity')
        if a.get('date') not in snapshot['dates']:errors.append('exam_dates')
        if (a.get('start_time'),a.get('end_time')) not in SLOTS or a.get('duration_minutes')!=120:errors.append('two_hour_slots')
        for cohort in c['participants']:
            cohort_days[cohort,a.get('date')]+=1
            cohort_slots[cohort,a.get('date'),a.get('start_time')]+=1
        if with_halls:
            used=a.get('halls') or []
            if any(h.get('room_id') not in halls for h in used):errors.append('hall_type')
            if sum(halls.get(h.get('room_id'),{}).get('capacity',0) for h in used)<(c.get('students') or 1):errors.append('hall_capacity')
            for h in used:
                hall_slots[(h.get('room_id'),a.get('date'),a.get('start_time'))]+=1
                if snapshot.get('invigilators') is not None:
                    ta=tas.get(h.get('invigilator_id'))
                    if not ta:errors.append('invigilator_missing');continue
                    ta_slots[(ta['id'],a.get('date'),a.get('start_time'))]+=1
                    slot=next((sl for sl in SLOTS if sl[0]==a.get('start_time')),None)
                    if slot and a.get('date') in snapshot['dates'] and not ta_free(ta,a['date'],slot):errors.append('invigilator_availability')
    if any(n>snapshot['max_exams_per_cohort_day'] for n in cohort_days.values()):errors.append('cohort_daily_limit')
    if any(n>1 for n in cohort_slots.values()):errors.append('cohort_slot_conflicts')
    if any(n>1 for n in hall_slots.values()):errors.append('hall_double_booking')
    if any(n>1 for n in ta_slots.values()):errors.append('invigilator_conflict')
    checks=['course_coverage','course_identity','exam_dates','two_hour_slots','cohort_daily_limit','cohort_slot_conflicts']
    if with_halls:checks+=['hall_type','hall_capacity','hall_double_booking']+(['invigilator_missing','invigilator_conflict','invigilator_availability'] if snapshot.get('invigilators') is not None else [])
    return {'passed':not errors,'errors':sorted(set(errors)),'checks':checks,'basis':'Program/semester metadata and configured group IDs; individual enrolments are not available.'}


def feasibility_test_cases():
    """Isolated examples run through the real solver; never write workspace data."""
    from copy import deepcopy
    def course(code, participants):
        return {'id':code,'code':code,'name':code,'participants':participants,'programs':[]}
    base={'dates':['2026-10-20'],'max_exams_per_cohort_day':1,'missing_cohort_codes':[], 'courses':[course('TEST-A',['Demo cohort']),course('TEST-B',['Demo cohort'])]}
    overlap=deepcopy(base);overlap['max_exams_per_cohort_day']=2
    overlap['courses']=[course(f'TEST-{i}',[f'Pair {min(i,j)}-{max(i,j)}' for j in range(4) if j!=i]) for i in range(4)]
    missing=deepcopy(base);missing['missing_cohort_codes']=['TEST-A']
    definitions=[
        ('daily_capacity','Daily capacity exceeded','Two exams share a cohort, but only one exam per day is allowed on one date.',base,{'dates':['2026-10-20','2026-10-21']},'Add a second eligible date.'),
        ('slot_conflicts','Shared-cohort slot conflicts','Four exams overlap pairwise through shared cohorts. One day has only three slots, even with a daily maximum of two.',overlap,{'dates':['2026-10-20','2026-10-21']},'Add a second eligible date; raising the daily maximum alone is insufficient.'),
        ('missing_metadata','Missing eligibility data','A course lacks the cohort information needed to check conflicts.',missing,{'missing_cohort_codes':[],'dates':['2026-10-20','2026-10-21']},'Complete cohort eligibility and provide two eligible dates.')]
    results=[]
    for ident,title,description,snapshot,changes,adjustment in definitions:
        before=generate_exam_draft(snapshot)
        revised=deepcopy(snapshot);revised.update(changes)
        after=generate_exam_draft(revised)
        results.append({'id':ident,'title':title,'description':description,'before':before,'adjustment':adjustment,'after':after,'verified':after['status']=='completed' and after['validation']['passed']})
    return results
