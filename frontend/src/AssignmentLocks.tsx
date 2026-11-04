import { useRef, useState } from "react";
import { createPortal } from "react-dom";
import { api, ApiError, type Workspace, type ScheduleRun, type ScheduleAssignment } from "./api";
import { Icon, Modal } from "./components";
import { words, type Word } from "./i18n";

const clock = (m:number) => `${String(Math.floor(m/60)).padStart(2,"0")}:${String(m%60).padStart(2,"0")}`;
function explanation(e:unknown, ar:boolean) {
  const code=e instanceof ApiError ? e.code : "";
  if (code==="lock_conflict") return ar ? "يتعارض مع تثبيت معتمد آخر. راجع التثبيتات أولاً." : "This conflicts with another approved lock. Review the existing locks first.";
  if (code==="stale_edit") return ar ? "تغيرت المدخلات. تم تحديث البيانات؛ راجعها وحاول مجدداً." : "Inputs changed. Data has been refreshed; review and try again.";
  if (code==="invalid_lock" || code==="invalid_lock_source") return ar ? "تغير النشاط أو الموارد أو التقويم. أنشئ التثبيت من مسودة صالحة." : "The activity, resources or calendar changed. Create a lock from a valid draft.";
  return ar ? "تعذر حفظ التثبيت. حاول مجدداً." : "Could not save the lock. Try again.";
}

export function LockSessionButton({ws,run,assignment:a,lang,refresh}:{ws:Workspace;run:ScheduleRun;assignment:ScheduleAssignment;lang:"en"|"ar";refresh:()=>Promise<void>}) {
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(""),[notice,setNotice]=useState("");
  const [instructor,setInstructor]=useState(true),[time,setTime]=useState(true),[room,setRoom]=useState(true);
  const requestKey=useRef("");
  const ar=lang==="ar",t=(k:Word)=>words[lang][k];
  const record=(id:string)=>run.snapshot.records.find(r=>r.id===id);
  return <>
    <button type="button" className="session-lock-button" onClick={()=>{requestKey.current=crypto.randomUUID();setError("");setOpen(true);}} aria-label={`${ar ? "تثبيت الحصة" : "Keep session fixed"}: ${record(a.activity_id)?.name} ${a.occurrence+1}`}><Icon name="lock" size={13}/>{ar ? "تثبيت" : "Keep fixed"}</button>
    {notice && <small role="status">{notice}</small>}
    {open && createPortal(<Modal title={ar ? "تثبيت تعيين الحصة" : "Keep this assignment fixed"} close={()=>{if(!busy)setOpen(false);}} t={t}>
      <p><strong>{record(a.activity_id)?.name}</strong> · {a.occurrence+1}<br/>{a.day} · {clock(a.start_minute)}–{clock(a.end_minute)}</p>
      <p className="modal-description">{ar ? "اختر ما تريد الإبقاء عليه. يُحفظ كتثبيت مسودة؛ اعتمده في صفحة القيود ثم أعد إنشاء الجدول." : "Choose what to keep. Save a draft lock, approve it under Constraints, then generate a new timetable."}</p>
      {error && <div className="error" role="alert">{error}</div>}
      <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");try{await api('/locks','POST',{request_key:requestKey.current,source_run_id:run.id,activity_id:a.activity_id,occurrence:a.occurrence,keep_instructor:instructor,keep_time:time,keep_room:room},ws.version);await refresh();setOpen(false);setNotice(ar ? "حُفظت المسودة. اعتمدها في القيود." : "Draft saved. Approve it under Constraints.");}catch(e){setError(explanation(e,ar));if(e instanceof ApiError && e.code==='stale_edit')await refresh();}finally{setBusy(false);}}}>
        <label className="check-label"><input type="checkbox" checked={instructor} onChange={e=>setInstructor(e.target.checked)}/>{ar ? "الإبقاء على المدرس" : "Keep instructor"} · {record(a.instructor_id)?.name}</label>
        <label className="check-label"><input type="checkbox" checked={time} onChange={e=>setTime(e.target.checked)}/>{ar ? "الإبقاء على اليوم والوقت" : "Keep day and time"} · {a.day} {clock(a.start_minute)}</label>
        <label className="check-label"><input type="checkbox" checked={room} onChange={e=>setRoom(e.target.checked)}/>{ar ? "الإبقاء على القاعة" : "Keep room"} · {record(a.room_id)?.name}</label>
        <p className="modal-description">{ar ? "تثبيت المدرس يسري على جميع حصص النشاط الأسبوعية للحفاظ على الاستمرارية. تُراجع المراجع وفق المدخلات الحالية؛ قد تجعل قيود أخرى إعادة الإنشاء غير ممكنة." : "Keeping the instructor applies to all weekly sessions of this activity for continuity. References are checked against current inputs; other constraints may still make regeneration infeasible."}</p>
        <div className="form-actions"><button type="button" className="btn white" disabled={busy} onClick={()=>setOpen(false)}>{t("cancel")}</button><button className="btn primary" disabled={busy || !(instructor || time || room)}>{busy ? t("working") : ar ? "حفظ تثبيت مسودة" : "Save draft lock"}</button></div>
      </form>
    </Modal>,document.body)}
  </>;
}

export function AssignmentLocks({ws,lang,administrator,refresh}:{ws:Workspace;lang:"en"|"ar";administrator:boolean;refresh:()=>Promise<void>}) {
  const ar=lang==='ar',locks=ws.assignment_locks || [],[busy,setBusy]=useState(false),[error,setError]=useState("");
  const record=(id:string|null)=>ws.records.find(r=>r.id===id);
  async function act(id:string,action:string) {
    setBusy(true);setError("");
    try {await api(`/locks/${id}${action==='delete'?'':'/'+action}`,action==='delete'?'DELETE':'POST',undefined,ws.version);await refresh();}
    catch(e){setError(explanation(e,ar));if(e instanceof ApiError && e.code==='stale_edit')await refresh();}
    finally{setBusy(false);}
  }
  return <section className="panel assignment-lock-panel"><h3><Icon name="lock" size={17}/> {ar ? "تثبيت التعيينات" : "Assignment locks"} · {locks.length}</h3><p className="modal-description">{ar ? "من الجدول المولد اختر تثبيت، ثم اعتمد المسودة هنا. المسودات لا تؤثر على الحل؛ التثبيت المعتمد شرط إلزامي عند إعادة الإنشاء." : "Choose Keep fixed on a generated session, then approve its draft here. Draft locks do not affect solving; approved locks are mandatory during regeneration."}</p>
    {error && <div className="error" role="alert">{error}</div>}
    {locks.map(lock=><article className="assignment-lock-row" key={lock.id}><div><strong>{record(lock.activity_id)?.name} · {lock.occurrence+1}</strong><p>{[lock.instructor_id && `${ar?'المدرس':'Instructor'}: ${record(lock.instructor_id)?.name}`, lock.day && `${lock.day} ${clock(lock.start_minute!)}`, lock.room_id && `${ar?'القاعة':'Room'}: ${record(lock.room_id)?.name}`].filter(Boolean).join(' · ')}</p><small>{ar ? "المصدر" : "Source draft"}: {lock.source_run_id.slice(0,8)}</small></div><div><span className={`pill ${lock.status==='approved'?'green':'amber'}`}>{ar ? lock.status==='approved'?'معتمد':'يحتاج مراجعة' : lock.status==='approved'?'Approved':'Needs review'}</span>{administrator && <><button className="btn white" disabled={busy} onClick={()=>void act(lock.id,lock.status==='approved'?'revoke':'approve')}>{ar ? lock.status==='approved'?'إلغاء الاعتماد':'اعتماد' : lock.status==='approved'?'Revoke':'Approve'}</button>{lock.status==='draft' && <button className="btn white" disabled={busy} onClick={()=>void act(lock.id,'delete')}>{ar ? 'حذف' : 'Remove'}</button>}</>}</div></article>)}
  </section>;
}
