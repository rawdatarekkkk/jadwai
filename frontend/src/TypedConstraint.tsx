import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Rule, type Workspace } from "./api";
import { describeRule } from "./RuleText";
import { errors, type Word } from "./i18n";

type Envelope = { decision: string; proposals: { kind: string; data: Rule }[]; clarifications: string[]; unsupported: string[] };
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
      {[...output.clarifications, ...output.unsupported].map(c => <p key={c} className="error">{c.replace(/_/g, " ")}</p>)}
      {output.decision === "ready" && !saved?.review && <button className="btn primary" disabled={busy} onClick={() => void create()}>{t("createDrafts")}</button>}
    </div>}
  </section>;
}
