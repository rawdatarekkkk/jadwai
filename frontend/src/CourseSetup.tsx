import { useState } from "react";
import { api, ApiError, type Workspace, type CatalogCourse } from "./api";
import { Icon, Modal } from "./components";
import { errors, type Word } from "./i18n";

export function CourseSetup({ws, t, close, saved}: {ws: Workspace; t: (key:Word)=>string; close:()=>void; saved:()=>Promise<unknown>}) {
  const [editing, setEditing] = useState<CatalogCourse | null | undefined>(undefined);
  const [name, setName] = useState(""); const [code, setCode] = useState("");
  const [eligibility, setEligibility] = useState<Record<string,string[]>>({lecture:[], tutorial:[], lab:[]});
  const [groups, setGroups] = useState<string[]>([]);
  const [students, setStudents] = useState("");
  const [type, setType] = useState("lecture"); const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false); const [error, setError] = useState("");
  const start = (course: CatalogCourse | null) => {setEditing(course);setName(course?.name || "");setCode(course?.code || "");setEligibility(course?.eligibility || {lecture:[],tutorial:[],lab:[]});setGroups(course?.group_ids || []);setStudents(course?.expected_students ? String(course.expected_students) : "");setType("lecture");setError("");};
  const toggle = (ids: string[], id: string) => ids.includes(id) ? ids.filter(x=>x!==id) : [...ids,id];
  return <Modal title={t("courseSetup")} t={t} dismissible={!busy} close={busy ? ()=>{} : close}>
    {error && <div className="error" role="alert">{error}</div>}
    {editing === undefined ? <>
      <p className="modal-description">{t("courseSetupHelp")}</p>
      <div className="course-catalog-toolbar"><input aria-label={t("searchRecords")} placeholder={t("searchRecords")} value={query} onChange={e=>setQuery(e.target.value)}/><button className="btn primary" onClick={()=>start(null)}><Icon name="plus" size={16}/>{t("newCourse")}</button></div>
      <div className="course-catalog-list">{(ws.course_catalog || []).filter(c=>`${c.name} ${c.code}`.toLowerCase().includes(query.toLowerCase())).map(c=><button key={c.id} className="course-catalog-row" onClick={()=>start(c)}><span><strong>{c.name}</strong><small>{c.code} · {c.group_ids.length} {t("studentGroups")}</small></span><Icon name="edit" size={16}/></button>)}
      {!ws.course_catalog?.length && <p className="modal-description">{t("noCoursesYet")}</p>}</div>
    </> : <form onSubmit={async e=>{e.preventDefault();setBusy(true);setError("");try{await api(`/course-catalog${editing ? `/${editing.id}` : ""}`,editing?"PUT":"POST",{name,code,eligibility,group_ids:groups,expected_students:students ? Number(students) : null},ws.version);await saved();setEditing(undefined);}catch(e){const key=e instanceof ApiError ? e.code : "network"; const language=t("language")==="العربية"?0:1;setError(errors[key]?.[language] || t("courseSaveError"));if(e instanceof ApiError && e.status===409)await saved();}finally{setBusy(false);}}}>
      {!!editing?.source_info?.program_semesters?.length && <div className="meaning-preview"><strong>{t("sourcePrograms")}</strong><p>{t("sourceProgramsHelp")}</p><ul className="course-source-programs">{editing.source_info.program_semesters.map((p,i)=><li key={i}>{p.program_or_cohort || p.faculty_section} · {t("sourceSemester")}: {p.semester ?? t("sourceUnspecified")}</li>)}</ul></div>}
      <div className="form-grid"><label>{t("courseName")}<input required maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></label><label>{t("code")}<input required maxLength={20} value={code} onChange={e=>setCode(e.target.value)}/></label><label>{t("expectedStudents")}<input type="number" min={1} max={5000} value={students} onChange={e=>setStudents(e.target.value)}/></label></div>
      <fieldset><legend>{t("instructorEligibility")}</legend><p className="room-type-help">{t("courseInstructorHelp")}</p>
        <div className="course-type-tabs">{["lecture","tutorial","lab"].map(k=><button type="button" className={type===k?"selected":""} key={k} onClick={()=>setType(k)}>{t(k as Word)} <span>{eligibility[k].length}</span></button>)}</div>
        <div className="check-options course-eligibility-options">{ws.records.filter(r=>r.kind==="instructors" && (!r.position || r.position === (type === "lecture" ? "doctor" : "ta"))).map(r=><label key={r.id}><input type="checkbox" checked={eligibility[type].includes(r.id)} onChange={()=>setEligibility({...eligibility,[type]:toggle(eligibility[type],r.id)})}/>{r.name}</label>)}</div>
      </fieldset>
      <fieldset><legend>{t("studentGroups")}</legend><p className="room-type-help">{t("courseGroupHelp")}</p><div className="check-options course-eligibility-options">{ws.records.filter(r=>r.kind==="groups").map(r=><label key={r.id}><input type="checkbox" checked={groups.includes(r.id)} onChange={()=>setGroups(toggle(groups,r.id))}/>{[r.year ? `${t("studyYear")} ${r.year}` : "",r.major,r.name].filter(Boolean).join(" / ")}</label>)}</div></fieldset>
      <div className="form-actions"><button type="button" className="btn white" disabled={busy} onClick={()=>setEditing(undefined)}>{t("cancel")}</button><button className="btn primary" disabled={busy || !(groups.length || students) || !Object.values(eligibility).some(ids=>ids.length)}>{t(busy?"working":"save")}<Icon name="check" size={16}/></button></div>
    </form>}
  </Modal>;
}
