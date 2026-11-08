import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Rule, type Workspace } from "./api";
import { describeRule } from "./RuleText";
import { errors, type Word } from "./i18n";

type Envelope = { decision: string; proposals: { kind: string; data: Rule }[]; clarifications: string[]; unsupported: string[] };
/** Parser question codes (annotation guide v2) as plain questions. */
const QUESTIONS: Record<string, [string, string]> = {
  ambiguous_instructor: ["Several instructors match this name. Use the full name.", "أكثر من مدرس بهذا الاسم. اكتب الاسم كاملًا."],
  ambiguous_group: ["Several student groups match. Use the group code, for example BA5-G7.", "أكثر من مجموعة مطابقة. اكتب رمز المجموعة، مثل BA5-G7."],
  ambiguous_room: ["Several rooms match. Use the room code.", "أكثر من قاعة مطابقة. اكتب رمز القاعة."],
  ambiguous_activity: ["Several courses match. Use the course code.", "أكثر من مقرر مطابق. اكتب رمز المقرر."],
  unknown_instructor: ["No instructor with this name was found. Check the spelling or add the instructor first.", "لم يُعثر على مدرس بهذا الاسم. راجع الكتابة أو أضف المدرس أولًا."],
  missing_target: ["Say who or what this rule is for: an instructor, group, room or course.", "حدّد لمن هذا القيد: مدرس أو مجموعة أو قاعة أو مقرر."],
  day_required: ["Which day? Add a day, or say “every day”.", "أي يوم؟ أضف يومًا، أو اكتب «كل يوم»."],
  rule_type_and_strength_required: ["Is this a time they can't teach, a preferred time, or the only allowed time?", "هل هذا وقت لا يمكن التدريس فيه، أم وقت مفضل، أم الوقت الوحيد المسموح؟"],
  undefined_early: ["“Early” is not a time. Give one, for example “before 10:00”.", "«بدري» ليس وقتًا محددًا. اكتب وقتًا، مثل «قبل 10:00»."],
  undefined_late: ["“Late” is not a time. Give one, for example “after 14:00”.", "«متأخر» ليس وقتًا محددًا. اكتب وقتًا، مثل «بعد 14:00»."],
  time_outside_teaching_hours: ["That time is outside the teaching day.", "هذا الوقت خارج يوم التدريس."],
  nothing_left_in_the_week: ["That would leave no teaching time at all.", "هذا لا يترك أي وقت للتدريس."],
  need_two_activities: ["Name at least two courses that should be on different days.", "اذكر مقررين على الأقل يجب أن يكونا في أيام مختلفة."],
  preferences_need_an_instructor: ["Preferences can only be set for instructors.", "التفضيلات تُحدد للمدرسين فقط."],
  unrecognised_request: ["This request is not one JadwAI can turn into a rule. Try a time someone can't teach, a preferred time, or a daily limit.", "لا يستطيع JadwAI تحويل هذا الطلب إلى قيد. جرّب وقتًا لا يمكن التدريس فيه أو وقتًا مفضلًا أو حدًا يوميًا."],
};
export const question = (code: string, ar: boolean) => QUESTIONS[code]?.[ar ? 1 : 0]
  ?? (code.startsWith("no_groups_in_year_") ? (ar ? `لا توجد مجموعات في السنة ${code.slice(18)}.` : `There are no groups in year ${code.slice(18)}.`) : code.replace(/_/g, " "));

type Saved = { id: string; record: { text: string; output: Envelope; origin: string }; review: unknown };

/** Admin box: plain-text constraint -> interpreted rules -> draft rules (approval stays separate). */
export function TypedConstraint({ ws, lang, t, refresh }: { ws: Workspace; lang: "en" | "ar"; t: (key: Word) => string; refresh: () => Promise<void> }) {
  const [text, setText] = useState(""), [saved, setSaved] = useState<Saved | null>(null), [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(""), [gpt, setGpt] = useState(false);
  const key = useRef({ text: "", value: "" });
  const ar = lang === "ar";
  useEffect(() => { api<{ enabled: boolean }>("/model-calls/configuration").then(c => setGpt(c.enabled === true)).catch(() => setGpt(false)); }, []);
  // One request key per distinct text, so a retried click never stores twice.
  const requestKey = (value: string) => { if (key.current.text !== value) key.current = { text: value, value: crypto.randomUUID() }; return key.current.value; };
  async function run(action: () => Promise<void>) {
    setBusy(true); setMessage("");
    try { await action(); } catch (e) { const code = e instanceof ApiError ? e.code : "invalid_input"; setMessage(errors[code]?.[ar ? 1 : 0] || code); } finally { setBusy(false); }
  }
  const interpret = () => run(async () => setSaved(await api<Saved>("/proposals/interpret", "POST", { text, request_key: requestKey("parser:" + text) }, ws.version)));
  const askGpt = () => run(async () => {
    const job = await api<{ status: string; proposal_id: string | null }>("/model-calls", "POST", { text, request_key: requestKey("gpt:" + text) }, ws.version);
    if (!job.proposal_id) { setMessage(t("notUnderstood")); return; }
    const all = await api<{ proposals: Saved[] }>("/proposals");
    setSaved(all.proposals.find(p => p.id === job.proposal_id) || null);
  });
  const create = () => run(async () => {
    if (!saved) return;
    await api(`/proposals/${saved.id}/review`, "POST", { action: "create_drafts", rationale: "Confirmed typed constraint", request_key: requestKey("review:" + saved.id) }, ws.version);
    setSaved(null); setText(""); setMessage(ar ? "تم إنشاء القواعد كمسودة. اعتمدها من القائمة أدناه." : "Draft rules created. Approve them in the list below.");
    await refresh();
  });
  const output = saved?.record.output;
  return <section className="panel typed-constraint">
    <h3>{t("typeConstraint")}</h3>
    <p className="modal-description">{t("typeConstraintHelp")}</p>
    <form onSubmit={(e) => { e.preventDefault(); void interpret(); }}>
      <textarea dir="auto" rows={2} maxLength={2000} value={text} onChange={(e) => { setText(e.target.value); setSaved(null); }} />
      <div className="form-actions">
        {gpt && output && output.decision !== "ready" && <button type="button" className="btn white" disabled={busy} onClick={() => void askGpt()}>{t("askGpt")}</button>}
        <button className="btn primary" disabled={busy || !text.trim()}>{t(busy ? "working" : "interpret")}</button>
      </div>
    </form>
    {message && <p role="status">{message}</p>}
    {output && <div className="meaning-preview" aria-live="polite">
      <span className="eyebrow">{output.decision === "ready" ? t("interpretation") : output.proposals.length ? t("needsClarification") : t("notUnderstood")}</span>
      {output.proposals.map((p, i) => { const m = describeRule(p.data, ws.records, t); return <p key={i}>{m.subject} · {m.type}<br /><bdi>{m.detail}</bdi> · {t(p.data.strength)}</p>; })}
      {[...output.clarifications, ...output.unsupported].map(c => <p key={c} className="error">{question(c, ar)}</p>)}
      {output.decision === "ready" && !saved?.review && <button className="btn primary" disabled={busy} onClick={() => void create()}>{t("createDrafts")}</button>}
    </div>}
  </section>;
}
