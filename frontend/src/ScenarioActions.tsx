import { useState } from "react";
import { api, ApiError, type ScheduleRun, type Workspace } from "./api";
import { errors, words } from "./i18n";

type Comparison = { a: { name: string | null; metrics: Record<string, number> }; b: { name: string | null; metrics: Record<string, number> };
  moved_sessions: { activity_id: string; occurrence: number; changed: string[] }[]; note: string };

const clock = (m: number) => `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

/** Admin controls for one completed draft: name, publish, validated move, compare, CSV. */
/** "INF1-G10, INF1-G11, INF1-G12" -> "INF1-G10–G12". */
export function compactGroups(codes: string[]) {
  const numbered = new Map<string, number[]>(), other: string[] = [];
  for (const c of codes) {
    const m = /^(.*?)G(\d+)$/i.exec(c);
    if (m) numbered.set(m[1], [...(numbered.get(m[1]) || []), Number(m[2])]);
    else if (c) other.push(c);
  }
  const parts: string[] = [];
  for (const [prefix, list] of numbered) {
    const ns = [...new Set(list)].sort((a, b) => a - b);
    let start = ns[0], prev = ns[0];
    for (const n of [...ns.slice(1), NaN]) {
      if (n === prev + 1) { prev = n; continue; }
      parts.push(prev > start + 1 ? `${prefix}G${start}–G${prev}` : prev === start + 1 ? `${prefix}G${start}, ${prefix}G${prev}` : `${prefix}G${start}`);
      start = prev = n;
    }
  }
  return [...parts, ...other].join(", ");
}

export function ScenarioActions({ ws, run, runs, lang, reload, select, notify, shows = () => true, scope = "" }: { ws: Workspace; run: ScheduleRun; runs: ScheduleRun[]; lang: "en" | "ar"; reload: () => Promise<void>; select: (id: string) => void; notify: (message: string) => void;
  /** Whether an activity is in the year, programme or group being viewed. */ shows?: (activityId: string) => boolean; scope?: string }) {
  const t = (k: keyof typeof words.en) => words[lang][k];
  const ar = lang === "ar";
  const [name, setName] = useState(run.name || ""), [busy, setBusy] = useState(false), [message, setMessage] = useState("");
  const [other, setOther] = useState(""), [comparison, setComparison] = useState<Comparison | null>(null);
  const [move, setMove] = useState({ session: "", day: "", start: "", room: "" });
  const records = run.snapshot.records;
  const label = (id: string) => records.find(r => r.id === id)?.name || id;
  const dayName = (d: string) => t(d as keyof typeof words.en) || d;
  const code = (id: string) => records.find(r => r.id === id)?.code || id;
  // Same-named activities differ by group, so show the groups in the session list.
  const groupsOf = (activityId: string) => compactGroups((records.find(r => r.id === activityId)?.group_ids || []).map(code));
  const draftName = (r: ScheduleRun) => `${r.name || (ar ? "مسودة" : "Draft")} · ${new Date(r.created_at).toLocaleString(ar ? "ar-EG" : "en-GB")}`;
  const others = runs.filter(r => r.id !== run.id && r.status === "completed");
  async function act(action: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await action(); } catch (e) {
      const code = e instanceof ApiError ? e.code : "invalid_input";
      const detail = e instanceof ApiError && e.details.errors ? ` (${e.details.errors.join(", ").replace(/_/g, " ")})` : "";
      setMessage((errors[code]?.[ar ? 1 : 0] || code) + detail);
    } finally { setBusy(false); }
  }
  // Only the sessions being viewed, in timetable order.
  const sessions = (run.result?.assignments || []).filter(a => shows(a.activity_id))
    .sort((a, b) => run.snapshot.calendar.days.indexOf(a.day) - run.snapshot.calendar.days.indexOf(b.day) || a.start_minute - b.start_minute || label(a.activity_id).localeCompare(label(b.activity_id)));
  const chosen = sessions.find(a => `${a.activity_id}:${a.occurrence}` === move.session);
  const activity = chosen && records.find(r => r.id === chosen.activity_id);
  // Start options come from the saved calendar: named periods, or the grid.
  const cal = run.snapshot.calendar;
  const starts = cal.teaching_periods?.length ? cal.teaching_periods.map(p => p.start) : Array.from({ length: (cal.end_hour - cal.start_hour) * 60 / cal.period_minutes }, (_, i) => cal.start_hour * 60 + i * cal.period_minutes);
  return <div className="scenario-actions">
    <div className="form-grid">
      <label>{t("scenarioName")}<input value={name} maxLength={100} onChange={e => setName(e.target.value)} /></label>
      <div className="form-actions">
        <button className="btn white" disabled={busy || !name.trim()} onClick={() => void act(async () => { await api(`/schedules/${run.id}/name`, "PUT", { name }); await reload(); })}>{t("rename")}</button>
        {run.published_at
          ? <button className="btn white" disabled={busy} onClick={() => void act(async () => { await api(`/schedules/${run.id}/unpublish`, "POST", undefined, ws.version); await reload(); })}>{t("unpublish")}</button>
          : <button className="btn primary" disabled={busy || run.stale} onClick={() => void act(async () => { await api(`/schedules/${run.id}/publish`, "POST", undefined, ws.version); await reload(); setMessage(ar ? "تم النشر. يرى المدرسون والطلاب هذا الجدول الآن." : "Published. Instructors and students now see this timetable."); })}>{t("publish")}</button>}
        <a className="btn white" href={`/api/schedules/${run.id}/export.csv`} download>{t("exportCsv")}</a>
      </div>
    </div>
    {run.published_at && <p className="validation-badge">{t("published")} · <bdi>{new Date(run.published_at).toLocaleString(ar ? "ar-EG" : "en-GB")}</bdi></p>}
    <details><summary>{t("editSession")}</summary>
      <div className="form-grid">
        <label>{ar ? "الحصة" : "Session"}<select value={move.session} onChange={e => setMove({ ...move, session: e.target.value })}>
          <option value="">{scope ? `— ${sessions.length} ${ar ? "حصة في" : sessions.length === 1 ? "session in" : "sessions in"} ${scope}` : "—"}</option>
          {sessions.map(a => <option key={`${a.activity_id}:${a.occurrence}`} value={`${a.activity_id}:${a.occurrence}`}>{label(a.activity_id)} · {groupsOf(a.activity_id)} · {dayName(a.day)} {clock(a.start_minute)} · {label(a.room_id)}</option>)}
        </select></label>
        <label>{ar ? "اليوم" : "Day"}<select value={move.day} onChange={e => setMove({ ...move, day: e.target.value })}><option value="">{ar ? "بدون تغيير" : "Keep"}</option>{cal.days.map(d => <option key={d} value={d}>{dayName(d)}</option>)}</select></label>
        <label>{ar ? "البداية" : "Start"}<select value={move.start} onChange={e => setMove({ ...move, start: e.target.value })}><option value="">{ar ? "بدون تغيير" : "Keep"}</option>{starts.map(s => <option key={s} value={s}>{clock(s)}</option>)}</select></label>
        <label>{ar ? "القاعة" : "Room"}<select value={move.room} onChange={e => setMove({ ...move, room: e.target.value })}><option value="">{ar ? "بدون تغيير" : "Keep"}</option>{records.filter(r => r.kind === "rooms").map(r => <option key={r.id} value={r.id}>{r.name}</option>)}</select></label>
      </div>
      <button className="btn primary" disabled={busy || !chosen || !(move.day || move.start || move.room)} onClick={() => void act(async () => {
        if (!chosen || !activity) return;
        const change: Record<string, unknown> = { activity_id: chosen.activity_id, occurrence: chosen.occurrence };
        if (move.day || move.start) { change.day = move.day || chosen.day; change.start_minute = move.start ? Number(move.start) : chosen.start_minute; }
        if (move.room) change.room_id = move.room;
        const made = await api<{ id: string }>(`/schedules/${run.id}/edits`, "POST", { request_key: crypto.randomUUID(), changes: [change] });
        await reload(); select(made.id);
        // This panel remounts for the new draft, so the page shows the confirmation.
        notify(ar ? "تم حفظ التعديل كمسودة جديدة بعد التحقق. المسودة الأصلية لم تتغير." : "Saved as a new validated draft. The original is unchanged.");
      })}>{t("editSession")}</button>
    </details>
    {others.length > 0 && <details><summary>{t("compare")}</summary>
      <label>{ar ? "قارن مع" : "Compare with"}<select value={other} onChange={e => setOther(e.target.value)}><option value="">—</option>{others.map(r => <option key={r.id} value={r.id}>{draftName(r)}</option>)}</select></label>
      <button className="btn white" disabled={busy || !other} onClick={() => void act(async () => setComparison(await api<Comparison>(`/schedule-comparisons?a=${run.id}&b=${other}`)))}>{t("compare")}</button>
      {comparison && <div>
        <table className="source-timetable-table"><thead><tr><th></th><th>{comparison.a.name || (ar ? "هذه المسودة" : "This draft")}</th><th>{comparison.b.name || (ar ? "الأخرى" : "Other")}</th></tr></thead>
          <tbody>{Object.keys(comparison.a.metrics).filter(k => k !== "same_inputs").map(k => <tr key={k}><td>{k.replace(/_/g, " ")}</td><td>{comparison.a.metrics[k]}</td><td>{comparison.b.metrics[k]}</td></tr>)}</tbody></table>
        <p>{comparison.moved_sessions.length === 1 ? (ar ? "حصة واحدة تغيرت" : "1 session differs") : `${comparison.moved_sessions.length} ${ar ? "حصص تغيرت" : "sessions differ"}`} · <small>{comparison.note}</small></p>
        <ul>{comparison.moved_sessions.slice(0, 12).map(m => <li key={`${m.activity_id}:${m.occurrence}`}>{label(m.activity_id)} · {groupsOf(m.activity_id)}: {m.changed.map(f => ({ day: ar ? "اليوم" : "day", start_minute: ar ? "الوقت" : "time", end_minute: "", room_id: ar ? "القاعة" : "room", instructor_id: ar ? "المدرس" : "instructor" } as Record<string, string>)[f]).filter(Boolean).join(", ")}</li>)}</ul>
      </div>}
    </details>}
    {message && <p role="status">{message}</p>}
  </div>;
}
