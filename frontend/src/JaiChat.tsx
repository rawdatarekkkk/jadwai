import { useEffect, useRef, useState } from "react";
import { api, ApiError, type Workspace } from "./api";

export type JaiAction =
  | { type: "generate"; scope: { programme: string; year: number | null }[] | null; label: string }
  | { type: "exam"; body: Record<string, unknown>; label: string }
  | { type: "download"; url: string; label: string }
  | { type: "open"; page: string; label: string };
export type JaiReply = {
  text: string[];
  action: JaiAction | null;
  retry_with_model: boolean;
  meaning: { intent: string; slots: Record<string, unknown> } | null;
  source: "built-in" | "local-model";
};
type Message =
  | { id: number; from: "you"; text: string }
  | { id: number; from: "jai"; text: string[]; action?: JaiAction | null; done?: boolean; source?: string; pending?: boolean; error?: boolean };
type NewMessage = Message extends infer M ? (M extends Message ? Omit<M, "id"> : never) : never;
export type JaiTarget = "timetable" | "exams" | "constraints" | "data";

const ARABIC = /[؀-ۿ]/;
let nextId = 1;

/** Ask JAI: a chat about the current timetable that also starts website work after you confirm it. */
export function JaiChat({ ws, lang, hidden, close, go, refresh }: {
  ws: Workspace; lang: "en" | "ar"; hidden: boolean; close: () => void;
  go: (target: JaiTarget) => void; refresh: () => Promise<unknown>;
}) {
  const ar = lang === "ar";
  const say = (en: string, arText: string) => (ar ? arText : en);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [localModel, setLocalModel] = useState<string | null>(null);
  const previous = useRef<JaiReply["meaning"]>(null);
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  useEffect(() => { api<{ model: string | null }>("/assistant/configuration").then(c => setLocalModel(c.model)).catch(() => {}); }, []);
  useEffect(() => { if (!hidden) input.current?.focus(); }, [hidden]);
  useEffect(() => { const el = list.current; if (el) el.scrollTop = el.scrollHeight; }, [messages]);
  useEffect(() => {
    if (hidden) return;
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [hidden, close]);

  const add = (m: NewMessage) => { const id = nextId++; setMessages(old => [...old, { ...m, id } as Message]); return id; };
  const update = (id: number, change: Partial<Message>) => setMessages(old => old.map(m => (m.id === id ? ({ ...m, ...change } as Message) : m)));

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    setText("");
    add({ from: "you", text: q });
    setBusy(true);
    try {
      let reply = await api<JaiReply>("/assistant", "POST", { text: q, previous: previous.current });
      if (reply.retry_with_model) {
        const waiting = add({ from: "jai", text: reply.text, pending: true });
        try {
          reply = await api<JaiReply>("/assistant", "POST", { text: q, previous: previous.current, use_model: true });
          update(waiting, { text: reply.text, action: reply.action, source: reply.source, pending: false });
        } catch {
          update(waiting, { text: [say("The local model did not answer. Is Ollama running?", "لم يرد النموذج المحلي. هل Ollama يعمل؟")], pending: false, error: true });
        }
      } else {
        add({ from: "jai", text: reply.text, action: reply.action, source: reply.source });
      }
      previous.current = reply.meaning;
    } catch (e) {
      add({ from: "jai", text: [say("Something went wrong: ", "حدث خطأ: ") + (e instanceof ApiError ? e.code : "connection_failed")], error: true });
    } finally {
      setBusy(false);
    }
  };

  const failure = (code: string) => ({
    schedule_active: say("A timetable is already being generated. Wait for it to finish.", "يوجد جدول قيد الإنشاء. انتظر حتى ينتهي."),
    worker_unavailable: say("The solver worker is not running, so nothing could start.", "عامل المحلل لا يعمل، لذلك لم يبدأ شيء."),
    stale_edit: say("The data changed meanwhile. Ask again so I use the latest data.", "تغيرت البيانات في الأثناء. اسأل مرة أخرى."),
    scope_empty: say("Everything in that scope is already scheduled.", "كل ما في هذا النطاق مجدول بالفعل."),
    invalid_scope: say("That programme or year has no student groups.", "هذا البرنامج أو السنة بدون مجموعات طلاب."),
    schedule_missing_data: say("Courses or rooms are missing, so a timetable can't be generated.", "المقررات أو القاعات ناقصة، لذلك لا يمكن إنشاء جدول."),
  } as Record<string, string>)[code] || say("It could not be done: ", "تعذر التنفيذ: ") + code;

  const run = async (id: number, action: JaiAction) => {
    if (action.type === "download") {
      const link = document.createElement("a");
      link.href = action.url; link.rel = "noopener"; document.body.appendChild(link); link.click(); link.remove();
      return;
    }
    if (action.type === "open") { go(action.page === "exams" ? "exams" : "timetable"); return; }
    setBusy(true);
    try {
      if (action.type === "generate") {
        await api("/schedules", "POST", { request_key: crypto.randomUUID(), ...(action.scope ? { scope: action.scope } : {}) }, ws.version);
        update(id, { done: true });
        add({ from: "jai", text: [say("Started. The solver is working on the draft; the Timetable page shows its progress.", "بدأ العمل. المحلل يعمل على المسودة؛ تعرض صفحة الجدول التقدم.")] });
        go("timetable");
      } else {
        await api("/exams", "POST", action.body, ws.version);
        update(id, { done: true });
        add({ from: "jai", text: [say("The exam timetable draft is ready on the Exams page. Review it there before publishing.", "مسودة جدول الامتحانات جاهزة في صفحة الامتحانات. راجعها قبل النشر.")] });
        go("exams");
      }
      await refresh().catch(() => {});
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "connection_failed";
      if (code === "stale_edit") await refresh().catch(() => {});
      add({ from: "jai", text: [failure(code)], error: true });
    } finally {
      setBusy(false);
    }
  };

  const examples = ar
    ? ["هل قاعة A3.128 فاضية يوم الأحد الساعة 10؟", "معامل فاضية يوم الاثنين 11:30", "اعمل جدول BA سنة 3", "حالة آخر تشغيل"]
    : ["Is room A3.128 free on Sunday at 10:00?", "Free labs on Monday 11:30 for 30 students", "Generate the timetable for BA year 3", "Status of the latest run"];

  return (
    <aside className="jai-chat" hidden={hidden} aria-label={say("Chat with JAI", "محادثة مع JAI")} dir={ar ? "rtl" : "ltr"}>
      <header>
        <span className="jai-avatar" aria-hidden="true">J<span>✦</span></span>
        <div>
          <strong>JAI</strong>
          <small>{localModel ? say(`Built-in understanding · ${localModel} on this server`, `فهم مدمج · ${localModel} على هذا الخادم`) : say("Built-in understanding · runs on this server", "فهم مدمج · يعمل على هذا الخادم")}</small>
        </div>
        <button type="button" className="jai-close" onClick={close} aria-label={say("Close chat", "إغلاق المحادثة")}>×</button>
      </header>
      <div className="jai-messages" ref={list} aria-live="polite">
        {!messages.length && (
          <div className="jai-welcome">
            <p>{say("Ask about rooms, instructors, groups and courses in the current timetable, or ask me to generate a timetable or an exam timetable. I prepare the work; you confirm it.",
              "اسأل عن القاعات والمحاضرين والمجموعات والمقررات في الجدول الحالي، أو اطلب إنشاء جدول أو جدول امتحانات. أنا أجهز العمل وأنت تؤكده.")}</p>
            <div className="jai-examples">{examples.map(x => <button type="button" key={x} onClick={() => void send(x)}>{x}</button>)}</div>
          </div>
        )}
        {messages.map(m => m.from === "you"
          ? <div key={m.id} className="jai-msg you" dir={ARABIC.test(m.text) ? "rtl" : "ltr"}>{m.text}</div>
          : <div key={m.id} className={`jai-msg jai ${m.error ? "error" : ""} ${m.pending ? "pending" : ""}`} dir={m.text.some(l => ARABIC.test(l)) ? "rtl" : "ltr"}>
              {m.text.map((line, i) => <p key={i}>{line}</p>)}
              {m.pending && <p className="jai-thinking" role="status">{say("This can take a minute or two on this computer…", "قد يستغرق ذلك دقيقة أو اثنتين على هذا الجهاز…")}</p>}
              {m.source === "local-model" && <small className="jai-source">{say("Understood by the local model", "فهمه النموذج المحلي")}</small>}
              {m.action && !m.done && (
                <div className="jai-action">
                  <button type="button" className="btn primary" disabled={busy} onClick={() => void run(m.id, m.action!)}>{m.action.label}</button>
                  {(m.action.type === "generate" || m.action.type === "exam") && <button type="button" className="btn white" disabled={busy} onClick={() => update(m.id, { action: null })}>{say("Cancel", "إلغاء")}</button>}
                </div>
              )}
              {m.done && <small className="jai-source">✓ {say("Done", "تم")}</small>}
            </div>)}
      </div>
      <form className="jai-input" onSubmit={e => { e.preventDefault(); void send(text); }}>
        <textarea ref={input} rows={2} value={text} maxLength={2000} placeholder={say("Ask JAI…", "اسأل JAI…")} aria-label={say("Message to JAI", "رسالة إلى JAI")}
          onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(text); } }} />
        <button className="btn primary" disabled={busy || !text.trim()}>{busy ? "…" : say("Send", "إرسال")}</button>
      </form>
    </aside>
  );
}
