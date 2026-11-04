"""Dated two-hour exam drafts from course/program metadata; no room allocation."""
from collections import defaultdict,Counter
from datetime import date,timedelta
import re
from math import ceil
from ortools.sat.python import cp_model

SLOTS=[('09:00','11:00'),('11:15','13:15'),('13:30','15:30')]

def course_inputs(courses):
    rows=[];missing=[];labels={}
    for c in courses:
        participants=[]
        for group in c.group_ids:participants.append('group:'+group)
        for p in (c.source_info or {}).get('program_semesters',[]):
            faculty=p.get('faculty_section','');program=p.get('program_or_cohort') or faculty
            clean=re.sub(r'[^a-z0-9]','',program.lower())
            if faculty=='ENGINEERING':
                for track in ('automotivemechatronics','roboticsandautomation','manufacturingengineering','automationandcontrolengineering','electricalpowersystemsengineering'):
                    if track in clean:clean=track;break
                if clean=='mechanicalengineeringmanufacturing':clean='manufacturingengineering'
            semester=p.get('semester')
            key=f'{faculty}:{clean}:{semester or "all"}'
            participants.append(key);labels[key]={'faculty':faculty,'program':clean,'semester':semester}
        if not participants:missing.append(c.code)
        rows.append({'id':c.id,'name':c.name,'code':c.code,'participants':sorted(set(participants)),'programs':(c.source_info or {}).get('program_semesters',[])})
    # General/core cohorts conservatively share students with specialization cohorts.
    for row in rows:
        expanded=set(row['participants'])
        for key in row['participants']:
            if key not in labels:continue
            label=labels[key]
            broad=label['program'] in ('businessadministration','businessadministrationcore','informaticsandcomputerscience')
            for other,target in labels.items():
                if target['faculty']!=label['faculty']:continue
                same_semester=target['semester']==label['semester'] or label['semester'] is None
                if same_semester and (broad or label['program']==target['program']):expanded.add(other)
        row['participants']=sorted(expanded)
    return rows,missing

def generate_exam_draft(snapshot):
    courses=snapshot['courses'];days=snapshot['dates'];per_day=snapshot['max_exams_per_cohort_day']
    if not courses:return {'status':'blocked','reason':'no_courses','assignments':[], 'recommendations':[{'action':'add_courses','message':'Add courses before generating an exam timetable.'}]}
    if snapshot['missing_cohort_codes']:return {'status':'blocked','reason':'missing_cohorts','course_codes':snapshot['missing_cohort_codes'],'assignments':[], 'recommendations':[{'action':'complete_cohorts','message':'Add the missing program/semester or student-group eligibility for the listed courses so conflicts can be checked.'}]}
    memberships=defaultdict(list)
    for i,c in enumerate(courses):
        for cohort in c['participants']:memberships[cohort].append(i)
    crowded=[{'cohort':cohort,'exams':len(ids),'available_days':len(days)} for cohort,ids in memberships.items() if len(ids)>len(days)*per_day]
    if crowded:
        required_days=max(ceil(len(ids)/per_day) for ids in memberships.values())
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
    model.minimize(peak)
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=10;solver.parameters.num_search_workers=2;solver.parameters.random_seed=42
    outcome=solver.solve(model)
    if outcome not in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        infeasible=outcome==cp_model.INFEASIBLE
        return {'status':'infeasible' if infeasible else 'unknown','reason':'search_outcome','assignments':[], 'recommendations':[
            {'action':'extend_period' if infeasible else 'retry','message':'Add eligible exam dates to separate courses with shared cohorts; then generate again.' if infeasible else 'The search stopped without a result; this does not prove infeasibility. Retry generation or allow a longer exam period.'},
            {'action':'review_cohorts','message':'Review shared program/semester memberships. Raising the daily maximum alone cannot resolve courses that must occupy the same limited set of slots.'}
        ],'recommendation_note':'Suggested adjustments must be verified by generating again.'}
    assignments=[]
    for i,c in enumerate(courses):
        for d,day in enumerate(days):
            for s,(start,end) in enumerate(SLOTS):
                if solver.value(x[i,d,s]):assignments.append({'course_id':c['id'],'course_name':c['name'],'course_code':c['code'],'date':day,'start_time':start,'end_time':end,'duration_minutes':120,'programs':c['programs']})
    validation=validate_exam_draft(snapshot,assignments)
    if not validation['passed']:return {'status':'failed','reason':'independent_validation_failed','validation':validation,'assignments':[]}
    return {'status':'completed','assignments':sorted(assignments,key=lambda a:(a['date'],a['start_time'],a['course_code'])),'validation':validation,'solver_seconds':solver.wall_time,'optimal_for_slot_balance':outcome==cp_model.OPTIMAL,'limitations':['Dates and times only; rooms and invigilators are not assigned.','Conflict checks use course program/semester labels and configured group IDs, not individual enrolments.','A draft requires institutional review before use.']}


def validate_exam_draft(snapshot,assignments):
    courses={c['id']:c for c in snapshot['courses']};errors=[];counts=Counter(a.get('course_id') for a in assignments)
    if set(counts)!=set(courses) or any(n!=1 for n in counts.values()):errors.append('course_coverage')
    cohort_days=Counter();cohort_slots=Counter()
    for a in assignments:
        c=courses.get(a.get('course_id'))
        if not c:continue
        if a.get('course_code') != c['code'] or a.get('course_name') != c['name']:errors.append('course_identity')
        if a.get('date') not in snapshot['dates']:errors.append('exam_dates')
        if (a.get('start_time'),a.get('end_time')) not in SLOTS or a.get('duration_minutes')!=120:errors.append('two_hour_slots')
        for cohort in c['participants']:
            cohort_days[cohort,a.get('date')]+=1
            cohort_slots[cohort,a.get('date'),a.get('start_time')]+=1
    if any(n>snapshot['max_exams_per_cohort_day'] for n in cohort_days.values()):errors.append('cohort_daily_limit')
    if any(n>1 for n in cohort_slots.values()):errors.append('cohort_slot_conflicts')
    return {'passed':not errors,'errors':sorted(set(errors)),'checks':['course_coverage','course_identity','exam_dates','two_hour_slots','cohort_daily_limit','cohort_slot_conflicts'],'basis':'Program/semester metadata and configured group IDs; individual enrolments are not available.'}


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
