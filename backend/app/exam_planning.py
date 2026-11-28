"""Dated exam drafts from course/program metadata.

Each exam has a type: a quiz (15-60 minutes, chosen by the administrator), a midterm (2 hours)
or a final (3 hours). A course may have several exams (for example a quiz and a midterm), and
one timetable may mix every type. Each type has its own start times (finals at 09:00 and
13:00 by default); an exam occupies exactly its start plus its length, and no cohort, hall or
invigilator gets two exams that overlap in time. Older snapshots describe fixed slots instead;
an exam then starts with any slot long enough for it.

With exam halls in the snapshot, each exam also gets one or more halls whose seats cover its
students, and every hall in use gets a TA invigilator who is free at that time."""
from collections import defaultdict,Counter
from datetime import date,timedelta
import re
from math import ceil
from ortools.sat.python import cp_model

SLOTS=[('09:00','11:00'),('11:15','13:15'),('13:30','15:30')]
EXAM_TYPES={'quiz':(15,60),'midterm':(120,120),'makeup':(120,120),'final':(180,180)}  # allowed minutes; makeup = second-chance midterm
# Second-chance midterms take the first slot of each final-exam day; finals come after.
DEFAULT_STARTS={'final':['11:30','15:00'],'makeup':['09:00'],'midterm':['09:00','11:15','13:30'],'quiz':['09:00','10:15','11:30','13:00','14:15']}


def duration_of(course):
    return course.get('duration_minutes') or 120


def clock(m):
    return f'{m//60:02d}:{m%60:02d}'


def starts_of(snapshot,exam):
    """Minutes of the day this exam may start: its type's start times, or (older snapshots)
    the start of every fixed slot long enough for it."""
    if snapshot.get('starts'):
        return sorted({minutes(t) for t in snapshot['starts'].get(exam.get('exam_type','midterm'),[])})
    slots=[tuple(x) for x in snapshot.get('slots') or SLOTS]
    return sorted({minutes(a) for a,b in slots if minutes(b)-minutes(a)>=duration_of(exam)})


def pack_day(exams,halls,points,limits):
    """Halls for one day's exams. exams: [(students, start, end)]. A hall holds one exam at a
    time; at every moment the halls in use fit the free invigilators (limits[point]).
    Fewest halls, then fewest empty seats. Returns hall indexes per exam, or None."""
    if not exams:return []
    model=cp_model.CpModel()
    y={(e,h):model.new_bool_var(f'y_{e}_{h}') for e in range(len(exams)) for h in range(len(halls))}
    for e,(n,_,_) in enumerate(exams):model.add(sum(halls[h]['capacity']*y[e,h] for h in range(len(halls)))>=n)
    for p in points:
        live=[e for e,(_,a,b) in enumerate(exams) if a<=p<b]
        if not live:continue
        for h in range(len(halls)):model.add_at_most_one(y[e,h] for e in live)
        model.add(sum(y[e,h] for e in live for h in range(len(halls)))<=limits[p])
    model.minimize(sum((10000+halls[h]['capacity'])*v for (e,h),v in y.items()))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=10;solver.parameters.num_search_workers=4;solver.parameters.random_seed=42
    if solver.solve(model) not in (cp_model.OPTIMAL,cp_model.FEASIBLE):return None
    return [[h for h in range(len(halls)) if solver.value(y[e,h])] for e in range(len(exams))]
WEEKDAYS=['Monday','Tuesday','Wednesday','Thursday','Friday','Saturday','Sunday']
# Programs whose students also sit specialisation exams of the same faculty/semester,
# and spelling families that collapse to one track. Editable per workspace.
DEFAULT_COHORT_RULES={'broad_programs':['businessadministration','businessadministrationcore','informaticsandcomputerscience'],
    'tracks':{'ENGINEERING':['automotivemechatronics','roboticsandautomation','manufacturingengineering','automationandcontrolengineering','electricalpowersystemsengineering']},
    'aliases':{'mechanicalengineeringmanufacturing':'manufacturingengineering'}}
# Two exams on one day weigh more than exams on consecutive days.
# An advising student over the daily maximum is a last resort, named in the result.
EXAM_WEIGHTS={'advising_extra_exams':100,'same_day_exams':20,'back_to_back_days':10,'peak_slot':3,'halls_used':1}


def advising(cohort):
    return cohort.startswith('student:')


def minutes(text):
    h,m=text.split(':');return int(h)*60+int(m)

def course_inputs(courses,rules=None,sizes=None,groups=None):
    """groups: optional {group id: group data}; names the programmes of courses that have no programme metadata."""
    rules=rules or DEFAULT_COHORT_RULES;sizes=sizes or {};groups=groups or {}
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
        programs=(c.source_info or {}).get('program_semesters',[])
        if not programs:
            # Label only (for the PDF and CSV); clashes are already checked through the groups.
            seen=sorted({(g.get('major') or '',g.get('year')) for g in (groups.get(i) for i in c.group_ids) if g and g.get('major')},key=lambda x:(x[0],x[1] or 0))
            programs=[{'program_or_cohort':f"{m} Year {y}" if y else m,'semester':None,'faculty_section':''} for m,y in seen]
        rows.append({'id':c.id,'name':c.name,'code':c.code,'participants':sorted(set(participants)),'programs':programs,'students':students or None,
                     'quiz_count':getattr(c,'quiz_count',3),'second_chance':getattr(c,'second_chance',True)})
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


def back_to_back_floor(exams,dates,daily):
    """Fewest back-to-back exam days a cohort with this many exams must have on these dates.
    It needs at least ceil(exams/daily) days. In a run of L consecutive dates, m chosen days
    leave at least max(0, 2m-L-1) adjacent pairs; the extra cost of each further day never
    falls, so taking the cheapest days first gives the minimum."""
    runs=[]
    for d in sorted(date.fromisoformat(x) for x in dates):
        if runs and (d-runs[-1][-1]).days==1:runs[-1].append(d)
        else:runs.append([d])
    cost=lambda length,m:max(0,2*m-length-1)
    steps=sorted(cost(len(r),m)-cost(len(r),m-1) for r in runs for m in range(1,len(r)+1))
    return sum(steps[:ceil(exams/daily)])

def halls_needed(students,halls):
    """Fewest halls that can seat these students (largest halls first)."""
    total=0
    for n,capacity in enumerate(sorted((h['capacity'] for h in halls),reverse=True),1):
        total+=capacity
        if total>=students:return n
    return len(halls)

def pack_halls(students,halls,limit):
    """Give each exam in one slot its own halls, using as few halls as possible and at most
    `limit` (free invigilators). Returns hall indexes per exam, or None if impossible."""
    if not students:return []
    model=cp_model.CpModel()
    y={(e,h):model.new_bool_var(f'y_{e}_{h}') for e in range(len(students)) for h in range(len(halls))}
    for e,n in enumerate(students):model.add(sum(halls[h]['capacity']*y[e,h] for h in range(len(halls)))>=n)
    for h in range(len(halls)):model.add_at_most_one(y[e,h] for e in range(len(students)))
    model.add(sum(y.values())<=limit)
    # Fewest halls, then fewest empty seats.
    model.minimize(sum((10000+halls[h]['capacity'])*v for (e,h),v in y.items()))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=5;solver.parameters.num_search_workers=1;solver.parameters.random_seed=42
    if solver.solve(model) not in (cp_model.OPTIMAL,cp_model.FEASIBLE):return None
    return [[h for h in range(len(halls)) if solver.value(y[e,h])] for e in range(len(students))]


def second_chance_pairs(courses):
    """(second-chance index, final index) for every course that has both in this timetable."""
    at={(c.get('course_id',c['id']),c.get('exam_type')):i for i,c in enumerate(courses)}
    return [(i,at[cid,'final']) for (cid,kind),i in at.items() if kind=='makeup' and (cid,'final') in at]


def generate_exam_draft(snapshot):
    courses=snapshot['courses'];days=snapshot['dates'];per_day=snapshot['max_exams_per_cohort_day']
    with_halls='halls' in snapshot
    halls=snapshot.get('halls',[]);tas=snapshot.get('invigilators')
    if not courses:return {'status':'blocked','reason':'no_courses','assignments':[], 'recommendations':[{'action':'add_courses','message':'Add courses before generating an exam timetable.'}]}
    if snapshot['missing_cohort_codes']:return {'status':'blocked','reason':'missing_cohorts','course_codes':snapshot['missing_cohort_codes'],'assignments':[], 'recommendations':[{'action':'complete_cohorts','message':'Add the missing program/semester or student-group eligibility for the listed courses so conflicts can be checked.'}]}
    # Each exam may start at its type's start times and occupies exactly its own length.
    dur=[duration_of(c) for c in courses]
    starts=[starts_of(snapshot,c) for c in courses]
    no_time=sorted({c['code'] for c,t in zip(courses,starts) if not t})
    if no_time:return {'status':'blocked','reason':'no_start_times','course_codes':no_time,'assignments':[],'recommendations':[{'action':'add_start_times','message':'Give every exam type in this timetable at least one start time.'}]}
    points=sorted({t for ts in starts for t in ts})  # every exam starts at one of these, so overlaps show there
    covers=lambda i,t,p:t<=p<t+dur[i]
    daymax=max(1,max(len(ts) for ts in starts))
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
    daily=min(per_day,daymax)
    # Advising students never sit two exams at once; their daily maximum gives way only
    # when their courses cannot be spread otherwise (see advising_extra_exams).
    limit_of=lambda cohort:daymax if advising(cohort) else daily
    crowded=[{'cohort':cohort,'exams':len(ids),'available_days':len(days)} for cohort,ids in memberships.items() if len(ids)>len(days)*limit_of(cohort)]
    if crowded:
        required_days=max(ceil(len(ids)/limit_of(cohort)) for cohort,ids in memberships.items())
        recommendations=[{'action':'extend_period','required_days':required_days,'additional_days':required_days-len(days),'message':f'Use at least {required_days} eligible exam days ({required_days-len(days)} more than currently selected) while keeping the daily maximum at {per_day}.'}]
        required_daily=max(ceil(len(ids)/len(days)) for cohort,ids in memberships.items() if not advising(cohort)) if days else 4
        if per_day<required_daily<=daymax:recommendations.append({'action':'raise_daily_limit','daily_limit':required_daily,'message':f'Alternatively, raise the daily maximum to at least {required_daily} exams per cohort. Review student workload before changing this policy.'})
        recommendations.append({'action':'review_cohorts','message':'Review the affected courses’ program/semester eligibility for incorrect overlap. Keep genuine shared cohorts together.'})
        return {'status':'infeasible','reason':'not_enough_days','details':crowded,'assignments':[],'recommendations':recommendations,'recommendation_note':'These are capacity requirements, not a guarantee. Generate again after adjusting constraints to verify the complete timetable.'}
    sets=Counter(frozenset(ids) for ids in memberships.values())
    maximal=[ids for ids in sets if not any(ids<other for other in sets)]
    hard={frozenset(ids) for cohort,ids in memberships.items() if not advising(cohort)}
    hard_maximal=[ids for ids in hard if not any(ids<other for other in hard)]
    floors={ids:back_to_back_floor(len(ids),days,daily if ids in hard else daymax) for ids in sets}
    need=[halls_needed(c['students'],halls) for c in courses] if with_halls else []
    limits={}
    if with_halls:
        for d,day in enumerate(days):
            for p in points:
                free=sum(ta_free(t,day,(clock(p),clock(p+15))) for t in tas) if tas is not None else len(halls)
                limits[d,p]=min(len(halls),free)
    def build(joint):
        model=cp_model.CpModel();x={}
        for i in range(len(courses)):
            for d in range(len(days)):
                for t in starts[i]:x[i,d,t]=model.new_bool_var(f'exam_{i}_{d}_{t}')
            model.add_exactly_one(x[i,d,t] for d in range(len(days)) for t in starts[i])
        # A course's second-chance midterm ends before its final starts (it replaces a missed midterm).
        moment=lambda i:sum((d*1440+t)*x[i,d,t] for d in range(len(days)) for t in starts[i])
        for m,f in second_chance_pairs(courses):model.add(moment(m)+dur[m]<=moment(f))
        live=lambda i,d,p:[x[i,d,t] for t in starts[i] if covers(i,t,p)]
        for ids in maximal:
            for d in range(len(days)):
                for p in points:model.add_at_most_one(v for i in ids for v in live(i,d,p))
        for ids in hard_maximal:
            for d in range(len(days)):
                model.add(sum(x[i,d,t] for i in ids for t in starts[i])<=per_day)
        peak=model.new_int_var(0,len(courses),'peak_slot_exams')
        for d in range(len(days)):
            for p in points:model.add(sum(v for i in range(len(courses)) for v in live(i,d,p))<=peak)
        terms={'peak_slot':[(1,peak)],'back_to_back_days':[],'same_day_exams':[],'advising_extra_exams':[],'halls_used':[]}
        for n,(ids,count) in enumerate(sets.items()):
            sits=[]
            for d in range(len(days)):
                v=model.new_bool_var(f'sits_{n}_{d}');model.add_max_equality(v,[x[i,d,t] for i in ids for t in starts[i]]);sits.append(v)
            pairs=[]
            for d in range(len(days)-1):
                if (date.fromisoformat(days[d+1])-date.fromisoformat(days[d])).days==1:
                    both=model.new_bool_var(f'b2b_{n}_{d}');model.add(both>=sits[d]+sits[d+1]-1);pairs.append(both)
            if per_day>1 or ids not in hard:
                for d in range(len(days)):
                    exams=sum(x[i,d,t] for i in ids for t in starts[i])
                    extra=model.new_int_var(0,len(courses),f'extra_{n}_{d}')
                    model.add(extra>=exams-1)
                    terms['same_day_exams'].append((count,extra))
                    if ids not in hard and per_day<daymax:
                        over=model.new_int_var(0,len(courses),f'over_{n}_{d}')
                        model.add(over>=exams-per_day)
                        terms['advising_extra_exams'].append((count,over))
            if floors[ids]:model.add(sum(pairs)>=floors[ids])  # proven bound; helps the search stop early
            terms['back_to_back_days']+=[(count,v) for v in pairs]
        use={}
        if with_halls:
            for d in range(len(days)):
                for p in points:
                    # At every moment: seats, and halls in use (each needing a free TA).
                    model.add(sum(courses[i]['students']*v for i in range(len(courses)) for v in live(i,d,p))<=sum(h['capacity'] for h in halls))
                    model.add(sum(need[i]*v for i in range(len(courses)) for v in live(i,d,p))<=limits[d,p])
        if with_halls and joint:
            y={(i,h):model.new_bool_var(f'hall_{i}_{h}') for i in range(len(courses)) for h in range(len(halls))}
            for i,c in enumerate(courses):model.add(sum(halls[h]['capacity']*y[i,h] for h in range(len(halls)))>=c['students'])
            for (i,d,t),v in x.items():
                for h in range(len(halls)):
                    z=model.new_bool_var(f'use_{i}_{h}_{d}_{t}')
                    model.add_bool_and([v,y[i,h]]).only_enforce_if(z)
                    model.add_bool_or([v.Not(),y[i,h].Not()]).only_enforce_if(z.Not())
                    use[i,h,d,t]=z
            for d in range(len(days)):
                for p in points:
                    for h in range(len(halls)):
                        model.add_at_most_one(use[i,h,d,t] for i in range(len(courses)) for t in starts[i] if covers(i,t,p))
                    model.add(sum(use[i,h,d,t] for i in range(len(courses)) for t in starts[i] if covers(i,t,p) for h in range(len(halls)))<=limits[d,p])
            terms['halls_used']=[(1,v) for v in y.values()]
        model.minimize(sum(EXAM_WEIGHTS[k]*coef*v for k,pairs in terms.items() for coef,v in pairs))
        return model,x,use
    def solve(model,seconds,hint=None):
        if hint:
            for var,value in hint.items():model.add_hint(var,value)
        solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=seconds;solver.parameters.num_search_workers=4;solver.parameters.random_seed=42
        return solver,solver.solve(model)
    budget=snapshot.get('time_limit_seconds',20)
    # Dates and times first, with seat and hall-count limits at every moment; then halls day
    # by day, which are small independent problems. If a day cannot be packed, fall back to
    # the joint model, started from the first solution.
    model,x,_=build(False)
    solver,outcome=solve(model,budget)
    halls_for={}
    if with_halls and outcome in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        for d in range(len(days)):
            placed=[(i,t) for (i,dd,t),v in x.items() if dd==d and solver.value(v)]
            packed=pack_day([(courses[i]['students'],t,t+dur[i]) for i,t in placed],halls,points,{p:limits[d,p] for p in points})
            if packed is None:halls_for=None;break
            for (i,_),chosen in zip(placed,packed):halls_for[i]=chosen
        if halls_for is None:
            first={key:solver.value(v) for key,v in x.items()}
            model,x2,use=build(True)
            solver,outcome=solve(model,budget,{x2[key]:v for key,v in first.items()})
            x=x2
            if outcome in (cp_model.OPTIMAL,cp_model.FEASIBLE):
                halls_for={i:[h for h in range(len(halls)) if any(solver.value(v) for (ii,hh,_,_),v in use.items() if ii==i and hh==h)] for i in range(len(courses))}
    if outcome not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        infeasible=outcome==cp_model.INFEASIBLE
        return {'status':'infeasible' if infeasible else 'unknown','reason':'search_outcome','assignments':[], 'recommendations':[
            {'action':'extend_period' if infeasible else 'retry','message':'Add eligible exam dates, start times, exam halls or available TAs; then generate again.' if infeasible else 'The search stopped without a result; this does not prove infeasibility. Retry generation or allow a longer exam period.'},
            {'action':'review_cohorts','message':'Review shared program/semester memberships. Raising the daily maximum alone cannot resolve exams that must share a limited set of times.'}
        ],'recommendation_note':'Suggested adjustments must be verified by generating again.'}
    assignments=[]
    load=Counter()
    for (i,d,t),v in sorted(x.items()):
        if not solver.value(v):continue
        c=courses[i]
        row={'exam_id':c['id'],'course_id':c.get('course_id',c['id']),'course_name':c['name'],'course_code':c['code'],'date':days[d],'start_time':clock(t),'end_time':clock(t+dur[i]),
             'duration_minutes':dur[i],'exam_type':c.get('exam_type','midterm'),'label':c.get('label'),'programs':c['programs']}
        if with_halls:
            row['students']=c['students']
            row['halls']=[{'room_id':halls[h]['id'],'room_code':halls[h]['code'],'capacity':halls[h]['capacity'],'invigilator_id':None} for h in halls_for[i]]
        assignments.append(row)
    if with_halls and tas is not None:
        # Each day, in time order, give every hall in use the least-loaded TA who is free then
        # and not invigilating an overlapping exam.
        for day in days:
            busy=defaultdict(list)
            for row in sorted((r for r in assignments if r['date']==day),key=lambda r:r['start_time']):
                a,b=minutes(row['start_time']),minutes(row['end_time'])
                for hall in row['halls']:
                    free=[t for t in tas if ta_free(t,day,(row['start_time'],row['end_time'])) and not any(x<b and a<y for x,y in busy[t['id']])]
                    if not free:return {'status':'infeasible','reason':'invigilators','assignments':[],'recommendations':[{'action':'add_tas','message':f'Not enough free TAs to invigilate on {day} at {row["start_time"]}.'}]}
                    choice=min(free,key=lambda t:(load[t['id']],t['id']))
                    hall['invigilator_id'],hall['invigilator_name']=choice['id'],choice['name']
                    busy[choice['id']].append((a,b));load[choice['id']]+=1
    validation=validate_exam_draft(snapshot,assignments)
    if not validation['passed']:return {'status':'failed','reason':'independent_validation_failed','validation':validation,'assignments':[]}
    limitations=['Conflict checks use course program/semester labels and configured group IDs, not individual enrolments.','A draft requires institutional review before use.']
    if not with_halls:limitations.insert(0,'Dates and times only; rooms and invigilators are not assigned.')
    observed=exam_convenience(snapshot,assignments)
    observed['back_to_back_unavoidable']=sum(floors[ids]*count for ids,count in sets.items())
    recommendations=[]
    if observed['advising_exceptions']:
        names=', '.join(sorted({e['student'] for e in observed['advising_exceptions']}))
        recommendations.append({'action':'advising_exceptions','message':f"Advising students over the daily maximum: {names}. Their courses cannot be spread further within these dates; they never have two exams at the same time. Arrange this with them, or add exam dates."})
    if observed['back_to_back_unavoidable']:
        recommendations.append({'action':'reduce_back_to_back','message':f"{observed['back_to_back_unavoidable']} of the {observed['back_to_back_days']} back-to-back exam days cannot be avoided: some groups have more exams than these dates allow without consecutive days. Add exam dates to reduce them, or allow {per_day+1} exams per day, which replaces some of them with two exams on one day." if per_day<daymax else f"{observed['back_to_back_unavoidable']} of the {observed['back_to_back_days']} back-to-back exam days cannot be avoided with these dates. Add exam dates to reduce them."})
    return {'status':'completed','assignments':sorted(assignments,key=lambda a:(a['date'],a['start_time'],a['course_code'])),'validation':validation,'solver_seconds':solver.wall_time,'optimal_for_slot_balance':outcome==cp_model.OPTIMAL,'convenience':observed,'invigilation_load':dict(load),'limitations':limitations,'recommendations':recommendations}


def _group(assignments):
    groups=defaultdict(list)
    for a in assignments:groups[(a['date'],a['start_time'])].append(a)
    return groups


def exam_convenience(snapshot,assignments):
    """Independently counted: cohort back-to-back exam days, extra exams on one day, busiest slot, halls used."""
    courses={c['id']:c for c in snapshot['courses']};days_by_cohort=defaultdict(set);slots=Counter()
    for a in assignments:
        slots[(a['date'],a['start_time'])]+=1
        for cohort in courses[a.get('exam_id',a['course_id'])]['participants']:days_by_cohort[cohort].add(date.fromisoformat(a['date']))
    back=sum(1 for days in days_by_cohort.values() for d in days if d+timedelta(days=1) in days)
    per_day=Counter((cohort,a['date']) for a in assignments for cohort in courses[a.get('exam_id',a['course_id'])]['participants'])
    limit=snapshot['max_exams_per_cohort_day']
    return {'back_to_back_days':back,'same_day_exams':sum(n-1 for n in per_day.values() if n>1),
            'advising_exceptions':[{'student':cohort.split(':',1)[1],'date':day,'exams':n} for (cohort,day),n in sorted(per_day.items()) if advising(cohort) and n>limit],'peak_slot':max(slots.values(),default=0),'halls_used':sum(len(a.get('halls',[])) for a in assignments)}


def validate_exam_draft(snapshot,assignments):
    """Independent checks on real times: each exam's length matches its type, it starts at one
    of its type's start times, and no cohort, hall or invigilator has overlapping exams."""
    key=lambda a:a.get('exam_id',a.get('course_id'))
    courses={c['id']:c for c in snapshot['courses']};errors=[];counts=Counter(key(a) for a in assignments)
    if set(counts)!=set(courses) or any(n!=1 for n in counts.values()):errors.append('course_coverage')
    cohort_days=Counter();busy=defaultdict(list)  # (kind, id, date) -> [(start, end)]
    with_halls='halls' in snapshot
    halls={h['id']:h for h in snapshot.get('halls',[])};tas={t['id']:t for t in snapshot.get('invigilators') or []}
    for a in assignments:
        c=courses.get(key(a))
        if not c:continue
        if a.get('course_code') != c['code'] or a.get('course_name') != c['name']:errors.append('course_identity')
        if a.get('date') not in snapshot['dates']:errors.append('exam_dates')
        dur=duration_of(c);low,high=EXAM_TYPES.get(c.get('exam_type','midterm'),(120,120))
        try:
            start,end=minutes(a['start_time']),minutes(a['end_time'])
        except (KeyError,ValueError,AttributeError):
            errors.append('exam_times');continue
        if a.get('duration_minutes')!=dur or end-start!=dur or not low<=dur<=high or start not in starts_of(snapshot,c):errors.append('exam_times')
        for cohort in c['participants']:
            cohort_days[cohort,a.get('date')]+=1
            busy[('cohort',cohort,a.get('date'))].append((start,end))
        if with_halls:
            used=a.get('halls') or []
            if any(h.get('room_id') not in halls for h in used):errors.append('hall_type')
            if sum(halls.get(h.get('room_id'),{}).get('capacity',0) for h in used)<(c.get('students') or 1):errors.append('hall_capacity')
            for h in used:
                busy[('hall',h.get('room_id'),a.get('date'))].append((start,end))
                if snapshot.get('invigilators') is not None:
                    ta=tas.get(h.get('invigilator_id'))
                    if not ta:errors.append('invigilator_missing');continue
                    busy[('ta',ta['id'],a.get('date'))].append((start,end))
                    if a.get('date') in snapshot['dates'] and not ta_free(ta,a['date'],(a['start_time'],a['end_time'])):errors.append('invigilator_availability')
    when={(courses[key(a)].get('course_id',key(a)),courses[key(a)].get('exam_type')):(a.get('date'),a.get('start_time'),a.get('end_time')) for a in assignments if key(a) in courses}
    if any(when[cid,'makeup'][0]>when[cid,'final'][0] or (when[cid,'makeup'][0]==when[cid,'final'][0] and when[cid,'makeup'][2]>when[cid,'final'][1])
           for (cid,kind) in when if kind=='makeup' and (cid,'final') in when):errors.append('second_chance_after_final')
    overlapping=lambda spans:any(b[0]<a[1] for a,b in zip(sorted(spans),sorted(spans)[1:]))
    if any(n>snapshot['max_exams_per_cohort_day'] for (cohort,_),n in cohort_days.items() if not advising(cohort)):errors.append('cohort_daily_limit')
    if any(overlapping(v) for (kind,_,_),v in busy.items() if kind=='cohort'):errors.append('cohort_slot_conflicts')
    if any(overlapping(v) for (kind,_,_),v in busy.items() if kind=='hall'):errors.append('hall_double_booking')
    if any(overlapping(v) for (kind,_,_),v in busy.items() if kind=='ta'):errors.append('invigilator_conflict')
    checks=['course_coverage','course_identity','exam_dates','exam_times','cohort_daily_limit','cohort_slot_conflicts']
    if any(c.get('exam_type')=='makeup' for c in courses.values()):checks.append('second_chance_after_final')
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
