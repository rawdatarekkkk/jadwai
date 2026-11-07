import { useEffect, useState } from "react";
import { api, ApiError, type Workspace } from "./api";
import { Icon, Modal } from "./components";
import { errors, type Word } from "./i18n";

type Change = { action: "drop" | "add"; course_id: string; group_id: string | null };
export type AdvisingStudent = { id: string; code: string; name: string; group_id: string | null; changes: Change[]; activity_ids: string[]; course_ids: string[] };

/** Students whose courses differ from their group's: their own sessions never overlap and they get their own exam cohort. */
export function AdvisingStudents({ ws, lang, t, close, saved }: { ws: Workspace; lang: "en" | "ar"; t: (key: Word) => string; close: () => void; saved: () => Promise<unknown> }) {
  const ar = lang === "ar";
  const [students, setStudents] = useState<AdvisingStudent[] | null>(null);
  const [editing, setEditing] = useState<AdvisingStudent | null | undefined>(undefined);
  const [code, setCode] = useState(""), [name, setName] = useState(""), [group, setGroup] = useState(""), [changes, setChanges] = useState<Change[]>([]);
  const [query, setQuery] = useState(""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  const groups = ws.records.filter(r => r.kind === "groups");
  const courses = [...(ws.course_catalog || [])].sort((a, b) => a.code.localeCompare(b.code));
  const label = (id: string | null) => { const g = groups.find(r => r.id === id); return g ? [g.code, g.major, g.name].filter(Boolean).join(" · ") : "—"; };
  const courseLabel = (id: string) => { const c = courses.find(x => x.id === id); return c ? `${c.code} · ${c.name}` : id; };
  const load = () => api<{ students: AdvisingStudent[] }>("/advising-students").then(r => setStudents(r.students)).catch(() => setStudents([]));
  useEffect(() => { void load(); }, []);
  const start = (s: AdvisingStudent | null) => { setEditing(s); setCode(s?.code || ""); setName(s?.name || ""); setGroup(s?.group_id || ""); setChanges(s?.changes || [{ action: "add", course_id: "", group_id: "" }]); setError(""); };
  const update = (i: number, change: Partial<Change>) => setChanges(changes.map((c, j) => j === i ? { ...c, ...change, ...(change.action === "drop" ? { group_id: null } : change.action === "add" ? { group_id: "" } : {}) } : c));
  const run = async (action: () => Promise<unknown>) => {
    setBusy(true); setError("");
    try { await action(); await saved(); await load(); setEditing(undefined); }
    catch (e) { const key = e instanceof ApiError ? e.code : "network"; setError(errors[key]?.[ar ? 1 : 0] || key.replace(/_/g, " ")); if (e instanceof ApiError && e.status === 409) await saved(); }
    finally { setBusy(false); }
  };
  const title = ar ? "طلاب الإرشاد الأكاديمي" : "Advising students";
  return <Modal title={title} t={t} dismissible={!busy} close={busy ? () => {} : close}>
    {error && <div className="error" role="alert">{error}</div>}
    {editing === undefined ? <>
      <p className="modal-description">{ar ? "طلاب تختلف مقرراتهم عن مجموعتهم (إعادة مقرر، إسقاط، أو حضور مع مجموعة أخرى). لن تتداخل حصصهم، ولن يكون لهم امتحانان في الوقت نفسه، ويُطبق عليهم الحد اليومي للامتحانات." : "Students whose courses differ from their group's: retakes, drops, or sessions with another group. Their sessions never overlap, they never have two exams at once, and the daily exam maximum applies to them."}</p>
      <div className="course-catalog-toolbar"><input aria-label={ar ? "بحث" : "Search"} placeholder={ar ? "ابحث بالرقم أو الاسم…" : "Search by ID or name…"} value={query} onChange={e => setQuery(e.target.value)} /><button className="btn primary" onClick={() => start(null)}><Icon name="plus" size={16} />{ar ? "طالب جديد" : "New student"}</button></div>
      <div className="course-catalog-list">
        {students === null && <p className="modal-description">{t("working")}</p>}
        {students?.filter(s => `${s.code} ${s.name}`.toLowerCase().includes(query.toLowerCase())).map(s => <button key={s.id} className="course-catalog-row" onClick={() => start(s)}><span><strong>{s.code} · {s.name}</strong><small>{label(s.group_id)} · {s.changes.filter(c => c.action === "drop").length} {ar ? "مُسقط" : "dropped"} · {s.changes.filter(c => c.action === "add").length} {ar ? "مضاف" : "added"} · {s.activity_ids.length} {ar ? "نشاط" : "activities"}</small></span><Icon name="edit" size={16} /></button>)}
        {students?.length === 0 && <p className="modal-description">{ar ? "لا يوجد طلاب إرشاد بعد." : "No advising students yet."}</p>}
      </div>
    </> : <form onSubmit={e => { e.preventDefault(); void run(() => api(`/advising-students${editing ? `/${editing.id}` : ""}`, editing ? "PUT" : "POST", { code, name, group_id: group || null, changes }, ws.version)); }}>
      <div className="form-grid">
        <label>{ar ? "الرقم الجامعي" : "Student ID"}<input required maxLength={20} value={code} onChange={e => setCode(e.target.value)} /></label>
        <label>{ar ? "الاسم" : "Name"}<input required maxLength={100} value={name} onChange={e => setName(e.target.value)} /></label>
        <label>{ar ? "المجموعة الأساسية" : "Home group"}<select value={group} onChange={e => setGroup(e.target.value)}><option value="">{ar ? "بدون مجموعة" : "No home group"}</option>{groups.map(g => <option key={g.id} value={g.id}>{label(g.id)}</option>)}</select></label>
      </div>
      <fieldset><legend>{ar ? "التغييرات عن المجموعة" : "Changes from the group"}</legend>
        <p className="room-type-help">{ar ? "إسقاط: لا يحضر هذا المقرر مع مجموعته. إضافة: يحضر محاضرات وسكاشن/معامل هذا المقرر مع المجموعة المختارة." : "Drop: does not take this course with their group. Add: attends this course's lectures and tutorials/labs with the chosen group."}</p>
        {changes.map((c, i) => <div className="form-grid advising-change" key={i}>
          <label>{ar ? "الإجراء" : "Change"}<select value={c.action} onChange={e => update(i, { action: e.target.value as Change["action"] })}><option value="add">{ar ? "إضافة مقرر" : "Add course"}</option><option value="drop">{ar ? "إسقاط مقرر" : "Drop course"}</option></select></label>
          <label>{ar ? "المقرر" : "Course"}<select required value={c.course_id} onChange={e => update(i, { course_id: e.target.value })}><option value="">{ar ? "اختر المقرر" : "Choose a course"}</option>{courses.map(x => <option key={x.id} value={x.id}>{courseLabel(x.id)}</option>)}</select></label>
          {c.action === "add" && <label>{ar ? "يحضر مع مجموعة" : "Attends with group"}<select required value={c.group_id || ""} onChange={e => update(i, { group_id: e.target.value })}><option value="">{ar ? "اختر المجموعة" : "Choose a group"}</option>{groups.map(g => <option key={g.id} value={g.id}>{label(g.id)}</option>)}</select></label>}
          <button type="button" className="btn white" aria-label={ar ? "إزالة التغيير" : "Remove change"} onClick={() => setChanges(changes.filter((_, j) => j !== i))}><Icon name="trash" size={16} /></button>
        </div>)}
        <button type="button" className="btn white" onClick={() => setChanges([...changes, { action: "add", course_id: "", group_id: "" }])}><Icon name="plus" size={16} />{ar ? "تغيير آخر" : "Another change"}</button>
      </fieldset>
      <div className="form-actions">
        {editing && <button type="button" className="btn white" disabled={busy} onClick={() => { if (confirm(t("confirmDelete"))) void run(() => api(`/advising-students/${editing.id}`, "DELETE", undefined, ws.version)); }}>{ar ? "حذف" : "Delete"}</button>}
        <button type="button" className="btn white" disabled={busy} onClick={() => setEditing(undefined)}>{t("cancel")}</button>
        <button className="btn primary" disabled={busy || !changes.length}>{t(busy ? "working" : "save")}<Icon name="check" size={16} /></button>
      </div>
    </form>}
  </Modal>;
}
