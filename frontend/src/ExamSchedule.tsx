import {useEffect,useRef,useState} from "react";
import {createPortal,flushSync} from "react-dom";
import {ExamSchedulePrint} from "./ExamSchedulePrint";
import {api,ApiError} from "./api";
import {errors} from "./i18n";
import type {Workspace} from "./api";
import {Icon} from "./components";

export type Exam={course_id:string;course_name:string;course_code:string;date:string;start_time:string;end_time:string;duration_minutes:number;students?:number|null;halls?:{room_id:string;room_code:string;capacity:number;invigilator_id:string|null;invigilator_name?:string}[];programs:{faculty_section:string;program_or_cohort:string|null;semester:number|null}[]};
export type Run={id:string;name?:string|null;published_at?:string|null;input_version:number;created_at:string;snapshot:{dates:string[];settings:{start_date:string;end_date:string};courses:{id:string;name:string;code:string}[]};result:{status:string;reason?:string;course_codes?:string[];assignments:Exam[];validation?:{passed:boolean;checks:string[]};limitations?:string[];recommendations?:{action:string;message:string}[];recommendation_note?:string;convenience?:{back_to_back_days:number;same_day_exams?:number;back_to_back_unavoidable?:number;peak_slot:number};details?:{cohort:string;exams:number;available_days:number}[]}};
function calendarDates(start:string,end:string) {
 const first=Date.parse(start+"T00:00:00Z"), last=Date.parse(end+"T00:00:00Z");
 if(!Number.isFinite(first)||!Number.isFinite(last)||last<first||last-first>60*86400000)return [];
 return Array.from({length:Math.round((last-first)/86400000)+1},(_,i)=>new Date(first+i*86400000).toISOString().slice(0,10));
}
function ExamDateBreakdown({start,end,eligible,ar,saved=false}:{start:string;end:string;eligible:string[];ar:boolean;saved?:boolean}) {
 const dates=calendarDates(start,end);
 if(!dates.length)return null;
 const allowed=new Set(eligible), excluded=dates.filter(d=>!allowed.has(d));
 return <div className="meaning-preview exam-date-breakdown" aria-live="polite">
 <strong>{saved?(ar?"الفترة المستخدمة لهذه المسودة":"Period used for this saved draft"):(ar?"أيام الامتحانات الفعلية":"Effective exam days")}</strong>
 <p>{start} – {end}: {dates.length} {ar?"أيام تقويمية":"calendar days"} − {excluded.length} {ar?"أيام مستبعدة":"excluded days"} = <b>{eligible.length} {ar?"أيام امتحانات متاحة":"eligible exam days"}</b>.</p>
 {!!excluded.length&&<p>{ar?"التواريخ المستبعدة":"Excluded dates"}: {excluded.map(d=>`${d} (${new Intl.DateTimeFormat(ar?"ar-EG":"en-GB",{weekday:"long",timeZone:"UTC"}).format(new Date(d+"T12:00:00Z"))})`).join(", ")}</p>}
 {saved&&<p>{ar?"التوصيات مبنية على هذه الأيام المتاحة، لا على عدد الأيام التقويمية أو التعديلات غير المحفوظة في النموذج.":"Recommendations use these eligible days, rather than calendar days or unsaved changes to the form."}</p>}
 </div>;
}
export function ExamSchedule({ws,lang}:{ws:Workspace;lang:"en"|"ar"}){
 const [testCases,setTestCases]=useState<{id:string;title:string;description:string;before:Run["result"];adjustment:string;after:Run["result"];verified:boolean}[]>([]);
 const [testing,setTesting]=useState(false);
 const [testError,setTestError]=useState("");
 const [printing,setPrinting]=useState(false);
 const originalTitle=useRef<string|null>(null);
 useEffect(()=>{
  const restore=()=>{if(originalTitle.current!==null)document.title=originalTitle.current;originalTitle.current=null;};
  const done=()=>{setPrinting(false);restore();};
  window.addEventListener("afterprint",done);
  return()=>{window.removeEventListener("afterprint",done);restore();};
 },[]);
 const ar=lang==="ar";const [runs,setRuns]=useState<Run[]>([]);const [selected,setSelected]=useState("");const [start,setStart]=useState("2026-10-20");const [end,setEnd]=useState("2026-10-31");const [fridays,setFridays]=useState(true);const [daily,setDaily]=useState(1);const [halls,setHalls]=useState(true);const [invigilate,setInvigilate]=useState(true);const [notice,setNotice]=useState("");const [busy,setBusy]=useState(false);const [error,setError]=useState("");const [query,setQuery]=useState("");
 useEffect(()=>{let active=true;api<Run[]>("/exam-schedules").then(r=>{if(active)setRuns(r);}).catch(()=>{if(active)setError(ar?"تعذر تحميل مسودات الامتحانات.":"Could not load exam drafts.");});return()=>{active=false;};},[ar]);
 async function act(action:()=>Promise<void>){setError("");setNotice("");try{await action();setRuns(await api<Run[]>("/exam-schedules"));}catch(e){const code=e instanceof ApiError?e.code:"invalid_input";setError(errors[code]?.[ar?1:0]||code);}}
 const run=runs.find(r=>r.id===selected)||runs[0];const assignments=run?.result.assignments||[];
 const visible=assignments.filter(a=>`${a.course_code} ${a.course_name} ${a.programs.map(p=>p.program_or_cohort).join(" ")}`.toLowerCase().includes(query.toLowerCase()));
 const eligibleDates=calendarDates(start,end).filter(d=>!fridays||new Date(d+"T12:00:00Z").getUTCDay()!==5);
 const savePdf=()=>{
  if(!run||run.result.status!=="completed")return;
  originalTitle.current??=document.title;
  document.title=`JadwAI-Midterms-${run.snapshot.settings.start_date}-${run.id.slice(0,8)}`;
  flushSync(()=>setPrinting(true));
  try{window.print();}catch{document.title=originalTitle.current!;originalTitle.current=null;setPrinting(false);setError(ar?"تعذر فتح الطباعة. حاول مرة أخرى.":"Could not open printing. Please try again.");}
 };
 return <section className="exam-planner">
 {printing&&run&&createPortal(<ExamSchedulePrint run={run} assignments={visible} lang={lang} query={query} stale={run.input_version!==ws.version}/>,document.body)}
 <section className="panel feasibility-tests"><h3>{ar?"اختبار قابلية الجدولة":"Test schedule feasibility"}</h3>
 <p>{ar?"أمثلة منفصلة تختبر القيود وتتحقق من التعديلات دون تغيير بياناتك. تفاصيل الأمثلة بالإنجليزية.":"Run isolated examples through the exam solver: see the blocking constraint, an adjustment, and whether the revised schedule passes validation. Your data is unchanged."}</p>
 <button type="button" className="btn white" disabled={testing} onClick={async()=>{setTesting(true);setTestError("");try{setTestCases(await api("/exam-schedules/feasibility-tests","POST"));}catch{setTestError(ar?"تعذر تشغيل الاختبارات.":"Could not run feasibility tests. Please try again.");}finally{setTesting(false);}}}>{testing?(ar?"جارٍ الاختبار…":"Testing…"):(ar?"تشغيل حالات الاختبار":"Run feasibility test cases")}</button>
 {testError&&<p role="alert" className="error">{testError}</p>}
 <div className="feasibility-case-list">{testCases.map(c=><article className="meaning-preview" key={c.id}><h4>{c.title}</h4><p>{c.description}</p><p><strong>{ar?"قبل التعديل":"Before adjustment"}: {c.before.status}</strong></p><p>{c.adjustment}</p><p><strong>{c.verified?(ar?"تم التحقق: جدول كامل اجتاز الفحص":"Verified: complete schedule; independent checks passed"):(ar?"لم يتم التحقق من الحل":"Adjustment did not produce a verified schedule")}</strong></p></article>)}</div>
 </section>
 <section className="panel"><h3>{ar?"فترة الامتحانات":"Exam period"}</h3><p className="room-type-help">{ar?"الإعدادات الافتراضية تتبع جدولك: ٢٠–٣١ أكتوبر ٢٠٢٦، بدون الجمعة.":"Defaults match your schedule: 20–31 October 2026, excluding Fridays."}</p>
 <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");try{const r=await api<Run>("/exam-schedules","POST",{start_date:start,end_date:end,exclude_fridays:fridays,max_exams_per_cohort_day:daily,use_halls:halls,assign_invigilators:halls&&invigilate},ws.version);setRuns([r,...runs]);setSelected(r.id);}catch{setError(ar?"تعذر إنشاء الجدول. حدّث مساحة العمل وحاول مجددًا.":"Could not generate. Refresh the workspace and try again.");}finally{setBusy(false);}}}>
 <div className="exam-settings"><label>{ar?"من":"Start date"}<input type="date" required value={start} onChange={e=>setStart(e.target.value)}/></label><label>{ar?"إلى":"End date"}<input type="date" required min={start} value={end} onChange={e=>setEnd(e.target.value)}/></label><label>{ar?"الحد اليومي لكل برنامج وفصل":"Daily maximum per program/semester"}<select value={daily} onChange={e=>setDaily(Number(e.target.value))}><option value={1}>1</option><option value={2}>2</option><option value={3}>3</option></select></label></div>
 <label className="check-label"><input type="checkbox" checked={fridays} onChange={e=>setFridays(e.target.checked)}/>{ar?"استبعاد الجمعة":"Exclude Fridays"}</label>
 <label className="check-label"><input type="checkbox" checked={halls} onChange={e=>setHalls(e.target.checked)}/>{ar?"خصص قاعات الامتحان (تُقسم الامتحانات الكبيرة على أكثر من قاعة)":"Assign exam halls (large exams are split across halls)"}</label>
 <label className="check-label"><input type="checkbox" checked={halls&&invigilate} disabled={!halls} onChange={e=>setInvigilate(e.target.checked)}/>{ar?"خصص معيداً مراقباً لكل قاعة":"Assign a TA invigilator to every hall"}</label>
 <ExamDateBreakdown start={start} end={end} eligible={eligibleDates} ar={ar}/>
 <div className="exam-slot-list">{["09:00–11:00","11:15–13:15","13:30–15:30"].map(t=><span key={t}><Icon name="clock" size={14}/><bdi>{t}</bdi></span>)}</div>
 <p className="room-type-help">{halls?(ar?"تُستخدم القاعات المحددة كقاعة امتحان وسعتها، وعدد الطلاب من مجموعات المقرر أو العدد المتوقع، والمعيدون كمراقبين حسب أيام إجازتهم وعدم إتاحتهم. التعارضات مبنية على البرامج والفصول والمجموعات، لا على تسجيل كل طالب.":"Uses rooms marked Exam hall with their capacity, student counts from each course’s groups or expected students, and TAs as invigilators, respecting their days off and unavailability. Conflicts use program/semester labels and groups, not individual enrolments."):(ar?"مسودة تواريخ وأوقات فقط. التعارضات مبنية على البرامج والفصول الدراسية والمجموعات المحددة؛ بيانات تسجيل الطلاب والقاعات والمراقبين غير متاحة.":"Dates and times only. Conflict checks use program/semester labels and configured groups. Individual enrolments, rooms and invigilators are not covered.")}</p>
 <button className="btn primary" disabled={busy||!ws.course_catalog?.length}><Icon name="spark" size={16}/>{busy?(ar?"جارٍ الإنشاء…":"Generating…"):(ar?"إنشاء جدول الامتحانات":"Generate exam schedule")}</button>
 </form></section>
 {error&&<div className="error" role="alert">{error}</div>}{notice&&<p role="status" className="panel">{notice}</p>}
 {!!runs.length&&<section className="panel"><div className="exam-result-toolbar"><label>{ar?"المسودة المحفوظة":"Saved draft"}<select value={run?.id} onChange={e=>setSelected(e.target.value)}>{runs.map(r=><option key={r.id} value={r.id}>{r.name?`${r.name} · `:""}{r.snapshot.settings.start_date} – {r.snapshot.settings.end_date} · {r.result.status}{r.published_at?" ✓":""} · {r.id.slice(0,8)}</option>)}</select></label>{run?.result.status==="completed"&&<><button type="button" className="btn primary" onClick={savePdf}>{ar?"حفظ PDF":"Save as PDF"}</button><a className="btn white" href={`/api/exam-schedules/${run.id}/export`} download>{ar?"تحميل CSV":"Download CSV"}</a>
 <button type="button" className="btn white" onClick={()=>{const name=window.prompt(ar?"اسم المسودة":"Draft name",run.name||"");if(name?.trim())void act(async()=>{await api(`/exam-schedules/${run.id}/name`,"PUT",{name:name.trim()});});}}>{ar?"إعادة تسمية":"Rename"}</button>
 {run.published_at?<button type="button" className="btn white" onClick={()=>void act(async()=>{await api(`/exam-schedules/${run.id}/unpublish`,"POST",undefined,ws.version);})}>{ar?"إلغاء النشر":"Unpublish"}</button>
 :<button type="button" className="btn primary" disabled={run.input_version!==ws.version} onClick={()=>void act(async()=>{await api(`/exam-schedules/${run.id}/publish`,"POST",undefined,ws.version);setNotice(ar?"تم النشر. يرى الطلاب امتحاناتهم والمعيدون مهام المراقبة.":"Published. Students see their exams and TAs their invigilation duties.");})}>{ar?"انشر":"Publish"}</button>}</>}</div>
 {run&&<ExamDateBreakdown start={run.snapshot.settings.start_date} end={run.snapshot.settings.end_date} eligible={run.snapshot.dates} ar={ar} saved/>}
 {run?.result.status==="completed"&&<p className="room-type-help">{ar?"اختر حفظ بتنسيق PDF في نافذة الطباعة. يتضمن التصدير الامتحانات المطابقة للبحث الحالي.":"Choose Save as PDF in the print dialog. The export includes exams matching your current search."}</p>}
 {run?.input_version!==ws.version&&<p className="error">{ar?"تغيرت المدخلات منذ إنشاء هذه المسودة.":"Inputs have changed since this draft was generated."}</p>}
 {run?.result.status!=="completed"?<div className="meaning-preview"><strong>{ar?"لم يُنتج جدول كامل":"No complete timetable produced"}</strong><p>{run?.result.reason==="missing_cohorts"?(ar?"أضف بيانات المجموعات أو البرامج لهذه المقررات:":"Add group or program details for these courses:"):run?.result.reason==="not_enough_days"?(ar?"بعض البرامج تحتاج أيامًا أكثر ضمن الحد اليومي المحدد.":"Some cohorts need more dates under the selected daily maximum."):run?.result.status==="unknown"?(ar?"انتهى البحث دون نتيجة؛ هذا لا يثبت استحالة الجدولة.":"The search ended without a result. Infeasibility has not been proven."):(ar?"راجع المدخلات أو وسّع فترة الامتحانات.":"Review inputs or extend the exam period.")}</p>{run?.result.recommendations?.length ? <div className="feasibility-recommendations"><h4>{ar?"تعديلات مقترحة":"Recommended adjustments"}</h4><ul>{run.result.recommendations.map((r,i)=><li key={i}>{r.message}</li>)}</ul>{run.result.recommendation_note&&<p>{run.result.recommendation_note}</p>}</div>:null}{run?.result.course_codes?.join(", ")}{run?.result.details?.map(d=><p key={d.cohort}>{d.cohort}: {d.exams} {ar?"امتحانات في":"exams over"} {d.available_days} {ar?"أيام":"days"}</p>)}</div>:<>
 <div className="exam-draft-summary"><strong>{assignments.length} {ar?"امتحانًا":"exams"}</strong><span>{run.snapshot.dates.length} {ar?"أيام متاحة":"available days"}</span><span>{ar?"ساعتان لكل امتحان":"2 hours each"}</span><span>{ar?"اجتاز الفحص المستقل":"Independent checks passed"}</span></div>
 {run.result.convenience&&<p className="exam-convenience">{ar?"أيام امتحانات متتالية للمجموعات":"Back-to-back exam days across groups"}: <strong>{run.result.convenience.back_to_back_days}</strong>{run.result.convenience.back_to_back_unavoidable!==undefined&&<> ({ar?"لا يمكن تجنب":"unavoidable"}: {run.result.convenience.back_to_back_unavoidable})</>} · {ar?"امتحانان في يوم واحد":"Two exams on one day"}: <strong>{run.result.convenience.same_day_exams??0}</strong></p>}
 {!!run.result.recommendations?.length&&<ul className="feasibility-recommendations">{run.result.recommendations.map((r,i)=><li key={i}>{ar&&r.action==="advising_exceptions"?`طلاب إرشاد تجاوزوا الحد اليومي: ${[...new Set((run.result.convenience as {advising_exceptions?:{student:string}[]}|undefined)?.advising_exceptions?.map(e=>e.student)||[])].join("، ")}. لا يمكن توزيع مقرراتهم أكثر ضمن هذه التواريخ، ولن يكون لهم امتحانان في الوقت نفسه. نسّق معهم أو أضف تواريخ امتحانات.`:ar&&r.action==="reduce_back_to_back"?`${run.result.convenience?.back_to_back_unavoidable} من ${run.result.convenience?.back_to_back_days} يوم امتحانات متتالية لا يمكن تجنبها: لدى بعض المجموعات امتحانات أكثر مما تسمح به هذه التواريخ دون أيام متتالية. أضف تواريخ امتحانات لتقليلها، أو اسمح بامتحان إضافي في اليوم، فيستبدل بعضها بامتحانين في يوم واحد.`:r.message}</li>)}</ul>}
 <input aria-label={ar?"تصفية الامتحانات":"Filter exams"} placeholder={ar?"ابحث عن مقرر أو برنامج…":"Search course, code or program…"} value={query} onChange={e=>setQuery(e.target.value)}/>
 {[...new Set(visible.map(a=>a.date))].sort().map(day=><section className="exam-day" key={day}><h3>{day} · {new Intl.DateTimeFormat(ar?"ar-EG":"en-GB",{weekday:"long",timeZone:"UTC"}).format(new Date(day+"T12:00:00Z"))}</h3><div className="exam-day-grid">{["09:00","11:15","13:30"].map(time=>{const exams=visible.filter(a=>a.date===day&&a.start_time===time);return <div className="exam-period" key={time}><h4>{time}–{time==="09:00"?"11:00":time==="11:15"?"13:15":"15:30"}</h4>{exams.map(a=><article className="exam-course" key={a.course_id}><small>{a.course_code}</small><strong>{a.course_name}</strong><p>{a.programs.map(p=>`${p.program_or_cohort} (${p.semester??"?"})`).filter((p,i,all)=>all.indexOf(p)===i).join(" · ")}</p>{a.halls&&<p className="exam-halls">{a.students} {ar?"طالباً":"students"} · {a.halls.map(h=>`${h.room_code} (${h.capacity})${h.invigilator_name?` – ${h.invigilator_name}`:""}`).join(", ")}</p>}</article>)}</div>;})}</div></section>)}
 </>}
 </section>}
 </section>;
}
