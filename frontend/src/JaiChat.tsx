import { useEffect, useRef, useState } from "react";
import { api, ApiError, type RecordKind, type Workspace } from "./api";
import {examOnScreen,selectExamRun} from "./examSelection";
import { showTimetableFilter, timetableOnScreen } from "./Timetable";
import { BidiLine, textDir } from "./bidi";

export type JaiAction =
  | { type: "website_request"; method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE"; path: string; body: unknown; label: string; operation: string; version?: number }
  | { type: "generate"; scope: { programme: string; year: number | null; group?: string }[] | null; label: string; filter?: { group?: string; year?: string; major?: string }; base_run_id?: string; replace?: boolean;
      then?: { programme: string; year: number | null }[][]; settings?: Record<string, unknown> }
  | { type: "publish_merged"; run_id: string; label: string; again?: string; groups?: string[] }
  | { type: "create_course"; catalog: Record<string, unknown>; activities: Record<string, unknown>[]; label: string }
  | { type: "update_course"; course_id: string; catalog: Record<string, unknown>; updates: { id: string; body: Record<string, unknown> }[]; creates: Record<string, unknown>[]; label: string }
  | { type: "apply_changes"; steps: { method: "PUT" | "POST"; path: string; body: Record<string, unknown>; save_as?: string }[]; then?: JaiAction | null; label: string }
  | { type: "update_courses"; items: { course_id: string; catalog: Record<string, unknown>; updates: { id: string; body: Record<string, unknown> }[]; creates: Record<string, unknown>[] }[]; group_code: string; label: string }
  | { type: "exam"; body: Record<string, unknown>; label: string; version?: number; scope_verified?: boolean }
  | { type: "download"; url: string; label: string }
  | { type: "open"; page: string; kind?: RecordKind; run_id?: string; label: string }
  | { type: "create_record"; kind: RecordKind; body: Record<string, unknown>; label: string }
  | { type: "publish" | "unpublish"; what: "teaching" | "exams"; run_id: string; label: string }
  | { type: "add_rules"; text: string; count: number; label: string; rules?: Record<string, unknown>[]; version?: number }
  | { type: "approve_rules"; rule_ids: string[]; label: string }
  | { type: "delete_rule"; rule_id: string; label: string }
  | { type: "update_record" | "delete_record"; kind: RecordKind; id: string; body?: Record<string, unknown>; label: string }
  | { type: "create_account"; body: Record<string, unknown>; label: string }
  | { type: "reset_account"; user_id: string; user_version: number; label: string }
  | { type: "cancel_run"; run_id: string; label: string }
  | { type: "rename_run"; what: "teaching" | "exams"; run_id: string; name: string; label: string }
  | { type: "move_session"; run_id: string; change: Record<string, unknown>; label: string }
  | { type: "lock_session"; run_id: string; activity_id: string; occurrence: number; label: string };
const CONFIRMED = ["website_request", "apply_changes", "generate", "publish_merged", "create_course", "update_course", "update_courses", "exam", "create_record", "publish", "unpublish", "add_rules", "approve_rules", "delete_rule", "update_record", "delete_record",
  "create_account", "reset_account", "cancel_run", "rename_run", "move_session", "lock_session"];
type Choice = { label: string; text: string };
export type JaiReply = {
  text: string[];
  action: JaiAction | null;
  retry_with_model: boolean;
  choices?: Choice[];
  source: "built-in" | "local-model";
  auto_open?: boolean;
  chat_id: string | null;
  message_id?: string;
  show_run?: string;  // the teaching timetable a command is about: open it on the Timetable page
};
type Message =
  | { id: string; from: "you"; text: string }
  | { id: string; from: "jai"; text: string[]; action?: JaiAction | null; choices?: Choice[]; done?: boolean; cancelled?: boolean; source?: string; pending?: boolean; error?: boolean };
type NewMessage = Message extends infer M ? (M extends Message ? Omit<M, "id"> & { id?: string } : never) : never;
type ChatSummary = { id: string; title: string; updated_at: string };
export type JaiTarget = "timetable" | "exams" | "constraints" | "data" | "overview" | "accounts" | "activity" | "evaluation" | "proposals" | "settings" | "import" | "advising";

const CURRENT = "jadwai-jai-chat";
let localId = 1;
const remembered = () => { try { return localStorage.getItem(CURRENT); } catch { return null; } };
const keep = (id: string | null) => { try { if (id) localStorage.setItem(CURRENT, id); else localStorage.removeItem(CURRENT); } catch { /* storage unavailable */ } };

/** Ask JAI: chats about the current timetable that also start website work after you confirm it.
 *  Chats are kept on the server per admin; each chat remembers its own context. */
export function JaiChat({ ws, lang, hidden, close, go, refresh, screen }: {
  ws: Workspace; lang: "en" | "ar"; hidden: boolean; close: () => void; screen?: string;
  go: (target: JaiTarget, kind?: RecordKind) => void; refresh: () => Promise<unknown>;
}) {
  const ar = lang === "ar";
  const say = (en: string, arText: string) => (ar ? arText : en);
  const [chatId, setChatId] = useState<string | null>(null);
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [showChats, setShowChats] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [localModel, setLocalModel] = useState<string | null>(null);
  const confirmationText = useRef<string | null>(null);
  const list = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLTextAreaElement>(null);

  const loadChats = () => api<ChatSummary[]>("/assistant/chats").then(setChats).catch(() => {});
  const openChat = async (id: string) => {
    try {
      const chat = await api<{ id: string; messages: Message[] }>(`/assistant/chats/${id}`);
      setChatId(chat.id); keep(chat.id); setMessages(chat.messages); setShowChats(false);
    } catch { setChatId(null); keep(null); setMessages([]); }
  };
  const newChat = () => { setChatId(null); keep(null); setMessages([]); setShowChats(false); setText(""); input.current?.focus(); };
  const removeChat = async (chat: ChatSummary) => {
    if (!window.confirm(say(`Delete the chat "${chat.title}"? This can't be undone.`, `حذف المحادثة "${chat.title}"؟ لا يمكن التراجع.`))) return;
    await api(`/assistant/chats/${chat.id}`, "DELETE").catch(() => {});
    if (chat.id === chatId) newChat();
    void loadChats();
  };

  useEffect(() => {
    api<{ model: string | null }>("/assistant/configuration").then(c => setLocalModel(c.model)).catch(() => {});
    const last = remembered();
    if (last) void openChat(last);
    void loadChats();
  }, []);
  useEffect(() => { if (!hidden) input.current?.focus(); }, [hidden]);
  useEffect(() => { const el = list.current; if (el) el.scrollTop = el.scrollHeight; }, [messages]);
  useEffect(() => {
    if (hidden) return;
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") close(); };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [hidden, close]);

  /** The page the admin is on, and on the teaching timetable the draft and filters shown. */
  const onScreen = () => screen === "teaching"
    ? { page: "timetable", ...Object.fromEntries(Object.entries(timetableOnScreen).filter(([, v]) => v)) }
    : screen === "exams" ? {page: "exams", ...examOnScreen} : screen ? { page: screen } : undefined;
  const add = (m: NewMessage) => { const id = m.id ?? `local-${localId++}`; setMessages(old => [...old, { ...m, id } as Message]); return id; };
  const update = (id: string, change: Partial<Message>) => setMessages(old => old.map(m => (m.id === id ? ({ ...m, ...change } as Message) : m)));

  /** Open the Timetable page on one draft (the one a command is about). */
  const showRun = (runId?: string) => {
    if (!runId) return;
    go("timetable");
    showTimetableFilter({ run_id: runId });
  };

  const send = async (question: string) => {
    const q = question.trim();
    if (!q || busy) return;
    setText("");
    add({ from: "you", text: q });
    const proposed = messages[messages.length - 1];
    if (proposed?.from === "jai" && proposed.action && !proposed.done && !proposed.cancelled && CONFIRMED.includes(proposed.action.type)) {
      if (/^(yes|yes please|yes,? do it|okay|ok|confirm|do it|go ahead|apply it|proceed|نعم|ايوه|أيوه|تمام|نفذ|اعمل كده)[.!؟?\s]*$/i.test(q)) {
        confirmationText.current = q;
        await run(proposed.id, proposed.action);
        return;
      }
      if (/^(no|cancel|never mind|لا|الغاء|إلغاء|خلاص)[.!؟?\s]*$/i.test(q)) {
        confirmationText.current = q;
        await settle(proposed.id, [say("Cancelled. Nothing was changed.", "تم الإلغاء دون تغيير.")], true);
        return;
      }
    }
    setBusy(true);
    let chat = chatId;
    try {
      const seen = onScreen();
      let reply = await api<JaiReply>("/assistant", "POST", { text: q, ...(chat ? { chat_id: chat } : {}), ...(seen ? { screen: seen } : {}) });
      if (reply.chat_id && reply.chat_id !== chat) { chat = reply.chat_id; setChatId(chat); keep(chat); }
      if (reply.retry_with_model) {
        const waiting = add({ from: "jai", text: reply.text, pending: true, id: reply.message_id });
        try {
          reply = await api<JaiReply>("/assistant", "POST", { text: q, use_model: true, ...(chat ? { chat_id: chat } : {}), ...(seen ? { screen: seen } : {}) });
          update(waiting, { text: reply.text, action: reply.action, choices: reply.choices, source: reply.source, pending: false });
          showRun(reply.show_run);
          if (reply.auto_open && reply.action?.type === "open") void run(reply.message_id || "", reply.action);
        } catch {
          update(waiting, { text: [say("The local model did not answer. Is Ollama running?", "لم يرد النموذج المحلي. هل Ollama يعمل؟")], pending: false, error: true });
        }
      } else {
        add({ from: "jai", text: reply.text, action: reply.action, choices: reply.choices, source: reply.source, id: reply.message_id });
        showRun(reply.show_run);
        if (reply.auto_open && reply.action?.type === "open") void run(reply.message_id || "", reply.action);  // "open X": go there now
      }
      void loadChats();
    } catch (e) {
      add({ from: "jai", text: [say("Something went wrong: ", "حدث خطأ: ") + (e instanceof ApiError ? e.code : "connection_failed")], error: true });
    } finally {
      confirmationText.current = null;
      setBusy(false);
    }
  };

  /** Record on the server that a message's action was done (or cancelled), with what to say next. */
  const settle = async (id: string, note: string[], cancelled = false, subject?: { kind: RecordKind | "schedules" | "exam_schedules"; id: string }, resultContext?: Record<string, unknown>[]) => {
    update(id, { done: true, cancelled });
    if (chatId && !id.startsWith("local-")) {
      const saved = await api<{ note: Message | null }>(`/assistant/chats/${chatId}/messages/${id}/done`, "POST",
        { note, cancelled, ...(resultContext?.length ? {result_context: resultContext} : {}), ...(confirmationText.current ? {confirmation_text: confirmationText.current} : {}), ...(subject ? { subject_kind: subject.kind, subject_id: subject.id } : {}) }).catch(() => null);
      confirmationText.current = null;
      if (saved?.note) { add(saved.note); return; }
    }
    if (note.length) add({ from: "jai", text: note });
  };

  const failure = (code: string) => ({
    schedule_active: say("A timetable is already being generated. Wait for it to finish.", "يوجد جدول قيد الإنشاء. انتظر حتى ينتهي."),
    worker_unavailable: say("The solver worker is not running, so nothing could start.", "عامل المحلل لا يعمل، لذلك لم يبدأ شيء."),
    stale_edit: say("The data changed meanwhile. Ask again so I use the latest data.", "تغيرت البيانات في الأثناء. اسأل مرة أخرى."),
    scope_empty: say("Everything in that scope is already scheduled.", "كل ما في هذا النطاق مجدول بالفعل."),
    invalid_scope: say("That programme or year has no student groups.", "هذا البرنامج أو السنة بدون مجموعات طلاب."),
    duplicate_code: say("A record with that code already exists. Ask me again with a different name or number.", "يوجد سجل بنفس الرمز. اطلب مرة أخرى باسم أو رقم مختلف."),
    invalid_input: say("Some details were not accepted. Check them on the Academic data page.", "بعض البيانات غير مقبولة. راجعها في صفحة البيانات الأكاديمية."),
    stale_schedule: say("The data changed since this timetable was made, so it can't be published. Generate a new one first.", "تغيرت البيانات بعد إنشاء هذا الجدول، لذلك لا يمكن نشره. أنشئ جدولاً جديداً أولاً."),
    schedule_incomplete: say("This is only part of the timetable; only a complete timetable can be published.", "هذا جزء من الجدول فقط؛ يُنشر الجدول الكامل فقط."),
    publication_validation_failed: say("It no longer passes the checks against the current data, so it was not published. Generate a new draft.", "لم يعد يجتاز الفحوص مقابل البيانات الحالية، لذلك لم يُنشر. أنشئ مسودة جديدة."),
    exam_without_halls: say("Exam timetables need halls and invigilators before publishing.", "جداول الامتحانات تحتاج قاعات ومراقبين قبل النشر."),
    duplicate_email: say("That email already has an account.", "هذا البريد له حساب بالفعل."),
    stale_account: say("That account changed meanwhile. Ask again.", "تغير هذا الحساب في الأثناء. اطلب مرة أخرى."),
    invalid_edit: say("That move doesn't fit: the time isn't a teaching slot, or the room or instructor isn't free or allowed there.", "هذا النقل غير ممكن: الوقت ليس فترة تدريس، أو القاعة أو المحاضر غير متاح أو غير مسموح."),
    record_in_use: say("It is still used (by a course, rule, lock or account), so it can't be deleted.", "ما زال مستخدماً (في مقرر أو قيد أو تثبيت أو حساب)، لذلك لا يمكن حذفه."),
    instructor_position: say("That position contradicts what the instructor already teaches (doctors lecture; TAs teach tutorials and labs).", "هذه الوظيفة تتعارض مع ما يدرسه المحاضر (الدكتور محاضرات؛ المعيد سكاشن ومعامل)."),
    lock_conflict: say("That lock clashes with another approved lock.", "هذا التثبيت يتعارض مع تثبيت آخر معتمد."),
    merge_validation_failed: say("It clashes with the published timetable (the same room, instructor or students at the same time), so nothing was published. Generate this part again inside the published timetable: ask me to generate it, and I'll plan it around everyone else.",
      "يتعارض مع الجدول المنشور (نفس القاعة أو المحاضر أو الطلاب في نفس الوقت)، لذلك لم يُنشر شيء. أنشئ هذا الجزء مرة أخرى داخل الجدول المنشور: اطلب مني إنشاءه وسأخططه حول الباقين."),
    nothing_published: say("Nothing is published yet, so there is nothing to publish it into.", "لا يوجد جدول منشور بعد لدمجه فيه."),
    edit_breaks_rules: say("That move breaks a rule or clashes with another session, so it was not made.", "هذا النقل يخالف قيداً أو يتعارض مع محاضرة أخرى، لذلك لم يتم."),
    course_eligibility_in_use: say("A teaching session of this course uses a group or instructor this change would remove.", "حصة في هذا المقرر تستخدم مجموعة أو محاضراً سيزيله هذا التغيير."),
    invalid_course_eligibility: say("A session names an instructor or group the course does not allow.", "حصة تذكر محاضراً أو مجموعة لا يسمح بها المقرر."),
    outside_calendar: say("That session length doesn't fit the teaching periods.", "مدة الحصة لا تناسب فترات التدريس."),
    invalid_transition: say("That can't be done in its current state (for example it is already published).", "لا يمكن ذلك في حالته الحالية (مثلاً منشور بالفعل)."),
    schedule_missing_data: say("Courses or rooms are missing, so a timetable can't be generated.", "المقررات أو القاعات ناقصة، لذلك لا يمكن إنشاء جدول."),
  } as Record<string, string>)[code] || say("It could not be done: ", "تعذر التنفيذ: ") + code;

  const run = async (id: string, action: JaiAction) => {
    if (action.type === "download") {
      const link = document.createElement("a");
      link.href = action.url; link.rel = "noopener"; document.body.appendChild(link); link.click(); link.remove();
      return;
    }
    if (action.type === "open") {
      if (action.page === "courses") go("data", "courses");
      else if (action.run_id) showRun(action.run_id);
      else go(action.page as JaiTarget, action.kind);
      return;
    }
    setBusy(true);
    try {
      const fresh = async () => (await api<{ version: number }>("/workspace")).version;  // each saved change moves the version on
      if (action.type === "website_request") {
        // Plans are contract-validated by the server; all execution uses the website's normal auth and checks.
        if (!action.path.startsWith("/") || action.path.startsWith("//") || action.path.includes(":") || /^\/(auth|assistant|health)(\/|$)/.test(action.path)) throw new ApiError("invalid_input", 400);
        const version = action.version;
        const result = await api<unknown>(action.path, action.method, action.body ?? undefined, version);
        const lines = describeWebsiteResult(result, say);
        if (action.path.startsWith("/users") && result && typeof result === "object" && "reset" in result) {
          const token = (result as {reset?: {token?: string}}).reset?.token;
          if (token) lines.push(say("One-time account setup link (expires in 30 minutes):", "رابط إعداد الحساب لمرة واحدة (ينتهي بعد 30 دقيقة):"), `${window.location.origin}/#reset=${encodeURIComponent(token)}`);
        }
        const record = action.path.match(/^\/records\/(rooms|instructors|groups|courses)(?:\/([^/?]+))?/);
        const returnedId = result && typeof result === "object" && "id" in result && typeof result.id === "string" ? result.id : undefined;
        const subject = record && action.method !== "DELETE" && (returnedId || record[2])
          ? {kind: record[1] as RecordKind, id: returnedId || record[2]}
          : action.path.startsWith("/exam-schedules") && returnedId && action.method === "POST" ? {kind: "exam_schedules" as const, id: returnedId}
          : action.path.startsWith("/schedules") && returnedId && action.method === "POST" ? {kind: "schedules" as const, id: returnedId} : undefined;
        await settle(id, [action.method === "GET" ? say("Here is the website result:", "هذه نتيجة الموقع:") : say("The website completed the request.", "أتم الموقع الطلب."), ...lines], false, subject, websiteResultContext(result));
        await refresh().catch(() => {});
        if (record) go("data", record[1] as RecordKind);
        else if (action.path.startsWith("/users")) go("accounts");
        else if (action.path.startsWith("/advising-students")) go("advising");
        else if (action.path.startsWith("/exam-schedules")) { if(returnedId) selectExamRun(returnedId); go("exams"); }
        else if (action.path.startsWith("/schedules") && returnedId) showRun(returnedId);
        else if (action.path.startsWith("/proposals")) go("proposals");
        else if (action.path.startsWith("/evaluation")) go("evaluation");
        return;
      }
      if (action.type === "apply_changes") {
        // Fixes JAI proposed (resize a group, split a lecture…): only record and course-setup requests, in order.
        // A step can create a record that later steps name as "$new" (for example a group split in two).
        const made: Record<string, string> = {};
        const fill = (value: unknown): unknown => typeof value === "string" ? value.replace(/\$(\w+)/g, (m, k) => made[k] ?? m)
          : Array.isArray(value) ? value.map(fill) : value && typeof value === "object" ? Object.fromEntries(Object.entries(value).map(([k, v]) => [k, fill(v)])) : value;
        for (const step of action.steps) {
          const path = fill(step.path) as string;
          if (!/^\/(records|course-catalog|rules)(\/|$)/.test(path) || !["PUT", "POST"].includes(step.method) || path.includes("$")) throw new ApiError("invalid_input", 400);
          const result = await api<{ id?: string }>(path, step.method, fill(step.body), await fresh());
          if (step.save_as && result?.id) made[step.save_as] = result.id;
        }
        await settle(id, [say(`Fixed: ${action.steps.length} change${action.steps.length === 1 ? "" : "s"} saved.`, `تم الإصلاح: حُفظ ${action.steps.length} تغيير.`)]);
        await refresh().catch(() => {});
        if (action.then) {
          setBusy(false);
          await run(id, action.then);  // and now the generation it was blocking
        }
        return;
      }
      if (action.type === "update_courses") {
        // A group joins several courses: each course first, then its sessions, one course at a time.
        for (const item of action.items) {
          await api(`/course-catalog/${item.course_id}`, "PUT", item.catalog, await fresh());
          for (const u of item.updates) await api(`/records/courses/${u.id}`, "PUT", u.body, await fresh());
          for (const c of item.creates) await api("/records/courses", "POST", c, await fresh());
        }
        await settle(id, [say(`Added ${action.group_code} to ${action.items.length} courses.`, `تمت إضافة ${action.group_code} إلى ${action.items.length} مقررات.`)]);
        add({ from: "jai", text: [say("Generate its timetable now?", "أنشئ جدولها الآن؟")],
          choices: [{ label: say("Generate its timetable", "إنشاء جدولها"), text: `generate a timetable for ${action.group_code}` }] });
        await refresh().catch(() => {});
        return;
      }
      if (action.type === "create_course" || action.type === "update_course") {
        // As Course setup does: the catalogue course first, then its teaching sessions.
        const course = action.type === "create_course"
          ? await api<{ id: string }>("/course-catalog", "POST", action.catalog, await fresh())
          : await api<{ id: string }>(`/course-catalog/${action.course_id}`, "PUT", action.catalog, await fresh());
        const updates = action.type === "update_course" ? action.updates : [];
        for (const u of updates) await api(`/records/courses/${u.id}`, "PUT", u.body, await fresh());
        const creates = action.type === "create_course" ? action.activities : action.creates;
        for (const a of creates) await api("/records/courses", "POST", { ...a, course_id: course.id }, await fresh());
        await settle(id, [action.type === "create_course"
          ? say(`Created ${String(action.catalog.name)} with ${creates.length} teaching session${creates.length === 1 ? "" : "s"}. It is in Course setup now; the next timetable you generate includes it.`,
            `تم إنشاء ${String(action.catalog.name)} مع ${creates.length} حصة. تجده في إعداد المقررات؛ يدخل في الجدول القادم.`)
          : say("Saved. The next timetable you generate includes the change.", "تم الحفظ. يدخل التغيير في الجدول القادم.")]);
        await refresh().catch(() => {});
        go("data", "courses");
        return;
      }
      if (action.type === "create_record") {
        const made = await api<{ id: string }>(`/records/${action.kind}`, "POST", action.body, await fresh());
        const what = { instructors: say("instructor", "المحاضر"), rooms: say("room", "القاعة"), groups: say("group", "المجموعة"), courses: say("course", "المقرر") }[action.kind];
        const teacher = action.kind === "instructors";
        const added = say(`Added the ${what} ${String(action.body.code)}. It is on the Academic data page now.`, `تمت إضافة ${what} ${String(action.body.code)}. تجده الآن في صفحة البيانات الأكاديمية.`);
        const next = teacher ? [say(`Next, add ${String(action.body.name)} to the ${action.body.position === "ta" ? "tutorials or labs" : "lectures"} of a course in Course setup; until then they get no sessions.`,
          `الخطوة التالية: أضف ${String(action.body.name)} إلى ${action.body.position === "ta" ? "سكاشن أو معامل" : "محاضرات"} مقرر من إعداد المقررات؛ حتى ذلك لا يحصل على حصص.`)] : [];
        update(id, { done: true });
        // The chat is now about the new record, so "create a schedule for them" means it.
        if (chatId && !id.startsWith("local-")) await api(`/assistant/chats/${chatId}/messages/${id}/done`, "POST", { note: [added, ...next], subject_kind: action.kind, subject_id: made.id }).catch(() => null);
        add({ from: "jai", text: [added, ...next], ...(teacher ? { action: { type: "open" as const, page: "data", kind: "courses" as const, label: say("Open Course setup", "فتح إعداد المقررات") } } : {}) });
        await refresh().catch(() => {});
        go("data", action.kind);
        return;
      }
      if (action.type === "add_rules") {
        const version = action.version ?? await fresh();
        const saved = action.rules
          ? await api<{ id: string }>("/proposals", "POST", {text: action.text, request_key: crypto.randomUUID(), output: {decision: "ready", proposals: action.rules.map(data => ({kind: "rule", data})), clarifications: [], unsupported: []}}, version)
          : await api<{ id: string }>("/proposals/interpret", "POST", { text: action.text, request_key: crypto.randomUUID() }, version);
        const review = await api<{ rule_ids: string[] }>(`/proposals/${saved.id}/review`, "POST", { action: "create_drafts", rationale: "Added from Ask JAI after confirmation", request_key: crypto.randomUUID() }, await fresh());
        for (const rule of review.rule_ids) await api(`/rules/${rule}/approve`, "POST", undefined, await fresh());
        await settle(id, [say(`Added and approved ${review.rule_ids.length} rule${review.rule_ids.length === 1 ? "" : "s"}. The next timetable you generate follows ${review.rule_ids.length === 1 ? "it" : "them"}.`, `تمت إضافة واعتماد ${review.rule_ids.length} قيد. يلتزم به الجدول القادم.`)]);
        await refresh().catch(() => {});
        return;
      }
      if (action.type === "approve_rules") {
        for (const rule of action.rule_ids) await api(`/rules/${rule}/approve`, "POST", undefined, await fresh());
        await settle(id, [say(`Approved ${action.rule_ids.length} rules.`, `تم اعتماد ${action.rule_ids.length} قيود.`)]);
        await refresh().catch(() => {});
        return;
      }
      if (action.type === "delete_rule") {
        await api(`/rules/${action.rule_id}`, "DELETE", undefined, await fresh());
        await settle(id, [say("Removed the rule.", "تم حذف القيد.")]);
        await refresh().catch(() => {});
        return;
      }
      if (action.type === "update_record" || action.type === "delete_record") {
        if (action.type === "update_record") await api(`/records/${action.kind}/${action.id}`, "PUT", action.body, await fresh());
        else await api(`/records/${action.kind}/${action.id}`, "DELETE", undefined, await fresh());
        await settle(id, [action.type === "update_record" ? say("Saved.", "تم الحفظ.") : say("Deleted.", "تم الحذف.")], false,
          action.type === "update_record" ? { kind: action.kind, id: action.id } : undefined);
        await refresh().catch(() => {});
        go("data", action.kind);
        return;
      }
      if (action.type === "create_account" || action.type === "reset_account") {
        const result = action.type === "create_account"
          ? await api<{ reset: { token: string } }>("/users", "POST", action.body)
          : await api<{ reset: { token: string } }>(`/users/${action.user_id}/reset`, "POST", undefined, action.user_version);
        const link = `${window.location.origin}/#reset=${encodeURIComponent(result.reset.token)}`;
        await settle(id, [action.type === "create_account" ? say("Account created. Send this one-time setup link to them (it expires in 30 minutes):", "تم إنشاء الحساب. أرسل له رابط الإعداد هذا (ينتهي بعد 30 دقيقة):")
          : say("New setup link (it expires in 30 minutes):", "رابط إعداد جديد (ينتهي بعد 30 دقيقة):"), link]);
        return;
      }
      if (action.type === "cancel_run") {
        await api(`/schedules/${action.run_id}/cancel`, "POST");
        await settle(id, [say("Stopping it. The Timetable page shows when it has stopped.", "جارٍ الإيقاف. تعرض صفحة الجدول متى توقف.")]);
        go("timetable");
        return;
      }
      if (action.type === "rename_run") {
        await api(`${action.what === "exams" ? "/exam-schedules" : "/schedules"}/${action.run_id}/name`, "PUT", { name: action.name });
        await settle(id, [say(`Renamed to "${action.name}".`, `تمت إعادة التسمية إلى "${action.name}".`)]);
        return;
      }
      if (action.type === "move_session") {
        await api(`/schedules/${action.run_id}/edits`, "POST", { request_key: crypto.randomUUID(), changes: [action.change] }, await fresh());
        await settle(id, [say("Moved. It is a new draft on the Timetable page, checked like any other; the original is unchanged.", "تم النقل. هي مسودة جديدة في صفحة الجدول، مفحوصة كغيرها؛ الأصلية لم تتغير.")]);
        await refresh().catch(() => {});
        go("timetable");
        return;
      }
      if (action.type === "lock_session") {
        const lock = await api<{ id: string }>("/locks", "POST", { request_key: crypto.randomUUID(), source_run_id: action.run_id, activity_id: action.activity_id,
          occurrence: action.occurrence, keep_time: true, keep_room: true, keep_instructor: true }, await fresh());
        await api(`/locks/${lock.id}/approve`, "POST", undefined, await fresh());
        await settle(id, [say("Locked. Timetables you generate from now on keep this session where it is.", "تم التثبيت. الجداول القادمة تُبقي هذه المحاضرة في مكانها.")]);
        await refresh().catch(() => {});
        return;
      }
      if (action.type === "publish_merged") {
        await api(`/schedules/${action.run_id}/publish-merged`, "POST", { request_key: crypto.randomUUID(), ...(action.groups?.length ? { groups: action.groups } : {}) }, await fresh());
        await settle(id, [action.groups?.length
          ? say("Published. Students and instructors now see the new week for this group; everyone else's published week is unchanged.", "تم النشر. يرى الطلاب والمحاضرون الآن الأسبوع الجديد لهذه المجموعة؛ وأسبوع الباقين المنشور لم يتغير.")
          : say("Published. The published timetable now has this part, and everyone else's week is unchanged.", "تم النشر. الجدول المنشور يحتوي هذا الجزء الآن، وأسبوع الباقين لم يتغير.")]);
        await refresh().catch(() => {});
        go("timetable");
        return;
      }
      if (action.type === "publish" || action.type === "unpublish") {
        const base = action.what === "exams" ? "/exam-schedules" : "/schedules";
        await api(`${base}/${action.run_id}/${action.type}`, "POST", undefined, ws.version);
        await settle(id, [action.type === "publish"
          ? say("Published. Students and instructors now see it in their portal.", "تم النشر. يراه الطلاب والمحاضرون الآن في بوابتهم.")
          : say("Unpublished. Students and instructors no longer see a teaching timetable.", "تم إلغاء النشر. لم يعد الطلاب والمحاضرون يرون جدول التدريس.")]);
        await refresh().catch(() => {});
        if(action.what === "exams") selectExamRun(action.run_id);
        go(action.what === "exams" ? "exams" : "timetable");
        return;
      }
      if (action.type === "generate") {
        const started = await api<{ id: string }>("/schedules", "POST", { request_key: crypto.randomUUID(), ...(action.scope ? { scope: action.scope } : {}),
          ...(action.base_run_id ? { base_run_id: action.base_run_id, replace: true } : {}),
          ...(action.then?.length ? { then: action.then } : {}), ...(action.settings ? { settings: action.settings } : {}) }, await fresh());
        await settle(id, [action.then?.length
          ? say(`Started part 1 of ${action.then.length + 1}. Each next part starts by itself when the one before finishes; the Timetable page shows them as they come.`,
                `بدأ الجزء 1 من ${action.then.length + 1}. يبدأ كل جزء تلقائياً بعد انتهاء ما قبله؛ تعرضها صفحة الجدول.`)
          : say("Started. The solver is working on the draft; the Timetable page shows its progress.", "بدأ العمل. المحلل يعمل على المسودة؛ تعرض صفحة الجدول التقدم.")],
          false, { kind: "schedules", id: started.id });  // "publish it" later means this one
        go("timetable");
        if (action.filter) showTimetableFilter(action.filter);
      } else if (action.type === "exam") {
        if (!action.scope_verified) {
          await settle(id, [say("This older exam proposal needs its programme scope checked again. Please repeat the exam request; no draft was created from this proposal.", "يحتاج مقترح الامتحانات القديم إلى مراجعة نطاق البرنامج. أعد طلب الامتحان؛ لم يُنشأ جدول من هذا المقترح.")], true);
          return;
        }
        const exam = await api<{ id: string; result: { status: string; reason?: string } }>("/exam-schedules", "POST", action.body, action.version ?? ws.version);
        const completed = exam.result?.status === "completed";
        await settle(id, [completed
          ? say("The exam timetable draft is ready on the Exams page. Review it there before publishing.", "مسودة جدول الامتحانات جاهزة في صفحة الامتحانات. راجعها قبل النشر.")
          : say(`The exam attempt was saved with status ${exam.result?.status || "unknown"}${exam.result?.reason ? ": " + exam.result.reason : ""}. Review the diagnostics on the Exams page; no timetable was published.`, `تم حفظ محاولة الامتحانات بالحالة ${exam.result?.status || "unknown"}. راجع التشخيص في صفحة الامتحانات؛ لم يُنشر جدول.`)], false, { kind: "exam_schedules", id: exam.id });
        selectExamRun(exam.id);
        go("exams");
      }
      await refresh().catch(() => {});
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "connection_failed";
      if (code === "stale_edit") await refresh().catch(() => {});
      // Say what the server found, and for a move offer the times that do work.
      const raw = e instanceof ApiError && Array.isArray(e.details.errors) ? (e.details.errors as string[]) : [];
      const plain: Record<string, string> = {
        complete_assignment: say("some sessions in the current data are not in it (they were added after it was made)", "بعض الحصص في البيانات الحالية غير موجودة فيه (أضيفت بعد إنشائه)"),
        resource_conflicts: say("a room, instructor or group would be in two places at once", "قاعة أو محاضر أو مجموعة في مكانين في نفس الوقت"),
        advising_student_conflicts: say("an advising student would have two classes at once", "طالب إرشاد لديه محاضرتان في نفس الوقت"),
      };
      const found = raw.map(x => plain[x] || x.replace(/_/g, " "));
      const missing = action.type === "publish_merged" && raw.includes("complete_assignment");
      add({ from: "jai", error: true,
        text: missing
          ? [say("Nothing was published: this draft was made before the latest changes, so sessions added since then (new groups, sections or courses) are not in it.",
                 "لم يُنشر شيء: هذه المسودة أُنشئت قبل آخر التغييرات، لذلك لا تحتوي الحصص المضافة بعدها."),
             say("Generate it again: drafts now include everything added since the timetable was published, so the new one can be published.",
                 "أنشئها مرة أخرى: المسودات الآن تشمل كل ما أضيف بعد النشر، لذلك يمكن نشر الجديدة.")]
          : [failure(code), ...(found.length ? [say("It found: ", "السبب: ") + found.join("; ") + "."] : [])],
        ...(action.type === "move_session" ? { choices: [{ label: say("Show other options", "اعرض بدائل"), text: say("what are the other options", "ايه البدائل") }] }
          : missing && action.again ? { choices: [{ label: say("Generate it again", "أنشئها مرة أخرى"), text: action.again }] } : {}) });
    } finally {
      confirmationText.current = null;
      setBusy(false);
    }
  };

  const examples = ar
    ? ["هل قاعة A3.128 فاضية يوم الأحد الساعة 10؟", "معامل فاضية يوم الاثنين 11:30", "اعمل جدول BA سنة 3", "حالة آخر تشغيل"]
    : ["Is room A3.128 free on Sunday at 10:00?", "Free labs on Monday 11:30 for 30 students", "Generate the timetable for BA year 3", "Status of the latest run"];
  const when = (iso: string) => new Intl.DateTimeFormat(ar ? "ar-EG" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
  const last = messages.at(-1);

  return (
    <aside className="jai-chat" hidden={hidden} aria-label={say("Chat with JAI", "محادثة مع JAI")} dir={ar ? "rtl" : "ltr"}>
      <header>
        <span className="jai-avatar" aria-hidden="true">J<span>✦</span></span>
        <div>
          <strong>JAI</strong>
          <small>{localModel ? say(`Built-in understanding · ${localModel} on this server`, `فهم مدمج · ${localModel} على هذا الخادم`) : say("Built-in understanding · runs on this server", "فهم مدمج · يعمل على هذا الخادم")}</small>
        </div>
        <button type="button" className="jai-head-btn" onClick={() => { setShowChats(v => !v); void loadChats(); }} aria-expanded={showChats}>{say("Chats", "المحادثات")}</button>
        <button type="button" className="jai-head-btn" onClick={newChat}>{say("New chat", "محادثة جديدة")}</button>
        <button type="button" className="jai-close" onClick={close} aria-label={say("Close chat", "إغلاق المحادثة")}>×</button>
      </header>
      {showChats ? (
        <nav className="jai-chats" aria-label={say("Your chats", "محادثاتك")}>
          {!chats.length && <p className="jai-source">{say("No chats yet.", "لا توجد محادثات بعد.")}</p>}
          {chats.map(c => (
            <div key={c.id} className={`jai-chat-row ${c.id === chatId ? "current" : ""}`}>
              <button type="button" onClick={() => void openChat(c.id)} dir={textDir(c.title)}>
                <span><BidiLine text={c.title} /></span><small>{when(c.updated_at)}</small>
              </button>
              <button type="button" className="jai-delete" aria-label={say(`Delete chat ${c.title}`, `حذف المحادثة ${c.title}`)} onClick={() => void removeChat(c)}>×</button>
            </div>
          ))}
        </nav>
      ) : (
        <div className="jai-messages" ref={list} aria-live="polite">
          {!messages.length && (
            <div className="jai-welcome">
              <p>{say("Ask questions, discuss options, or ask me to work with academic data, courses, accounts, constraints, semester settings, timetables, exams and reports. I remember this chat and ask for missing details. Confirm a proposed change with its button or by saying “yes, do it”. AI runs locally.",
                "اسأل عن القاعات والمحاضرين والمجموعات والمقررات في الجدول الحالي، أو اطلب إنشاء جدول أو جدول امتحانات. أنا أجهز العمل وأنت تؤكده. أتذكر ما قلناه في هذه المحادثة.")}</p>
              <div className="jai-examples">{examples.map(x => <button type="button" key={x} onClick={() => void send(x)}>{x}</button>)}</div>
            </div>
          )}
          {messages.map((m, i) => m.from === "you"
            ? <div key={m.id} className="jai-msg you" dir={textDir(m.text)}><BidiLine text={m.text} /></div>
            : <div key={m.id} className={`jai-msg jai ${m.error ? "failed" : ""} ${m.pending ? "pending" : ""}`} dir={textDir(m.text.join(" "))}>
                {m.text.map((line, j) => <p key={j} dir={textDir(line)}><BidiLine text={line} /></p>)}
                {m.pending && <p className="jai-thinking" role="status" dir={ar ? "rtl" : "ltr"}>{say("This can take a minute or two on this computer…", "قد يستغرق ذلك دقيقة أو اثنتين على هذا الجهاز…")}</p>}
                {m.source === "local-model" && <small className="jai-source" dir={ar ? "rtl" : "ltr"}>{say("Understood by the local model", "فهمه النموذج المحلي")}</small>}
                {m.action && !m.done && (
                  <div className="jai-action">
                    <button type="button" className="btn primary" disabled={busy} onClick={() => void run(m.id, m.action!)}>{m.action.label}</button>
                    {CONFIRMED.includes(m.action.type) &&
                      <button type="button" className="btn white" disabled={busy} onClick={() => void settle(m.id, [say("Cancelled.", "تم الإلغاء.")], true)}>{say("Cancel", "إلغاء")}</button>}
                  </div>
                )}
                {m.done && <small className="jai-source" dir={ar ? "rtl" : "ltr"}>{m.cancelled ? say("Cancelled", "أُلغي") : `✓ ${say("Done", "تم")}`}</small>}
                {!!m.choices?.length && i === messages.length - 1 && (
                  <div className="jai-choices" role="group" aria-label={say("Possible answers", "إجابات مقترحة")}>
                    {m.choices.map(c => <button type="button" key={c.text} disabled={busy} onClick={() => void send(c.text)}>{c.label}</button>)}
                    <small className="jai-source">{say("…or type your own answer below.", "…أو اكتب إجابتك بالأسفل.")}</small>
                  </div>
                )}
              </div>)}
        </div>
      )}
      <form className="jai-input" onSubmit={e => { e.preventDefault(); setShowChats(false); void send(text); }}>
        <textarea ref={input} rows={2} value={text} maxLength={2000} placeholder={last?.from === "jai" && last.choices?.length
          ? say("Pick an answer above, or type your own…", "اختر إجابة بالأعلى أو اكتب إجابتك…") : say("Ask JAI…", "اسأل JAI…")} aria-label={say("Message to JAI", "رسالة إلى JAI")}
          onChange={e => setText(e.target.value)} onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); setShowChats(false); void send(text); } }} />
        <button className="btn primary" disabled={busy || !text.trim()}>{busy ? "…" : say("Send", "إرسال")}</button>
      </form>
    </aside>
  );
}

export function describeWebsiteResult(value: unknown, say: (en: string, ar: string) => string): string[] {
  const visible = (v: unknown, depth = 0): string => {
    if (v == null) return "";
    if (typeof v !== "object") return String(v);
    if (depth > 2) return "…";
    if (Array.isArray(v)) return v.slice(0, 12).map(x => visible(x, depth + 1)).join("; ") + (v.length > 12 ? ` (${v.length} total)` : "");
    return Object.entries(v).filter(([k]) => !/password|token|secret|reset|^id$|_id$/.test(k)).slice(0, 16)
      .map(([k, x]) => `${k.replace(/_/g, " ")}: ${visible(x, depth + 1)}`).join(" · ");
  };
  if (value == null) return [say("Completed.", "تم التنفيذ.")];
  const items = Array.isArray(value) ? value : [value];
  return [say(`${items.length} result(s).`, `${items.length} نتيجة.`), ...items.slice(0, 12).map((x, i) => `${i + 1}. ${visible(x).slice(0, 1200)}`)];
}

export function websiteResultContext(value: unknown): Record<string, unknown>[] {
  const allowed = new Set(["id", "name", "code", "kind", "role", "email", "active", "version", "group_id", "instructor_id", "advising_student_id", "year", "major", "capacity", "size", "department", "day_off", "position"]);
  const rows = Array.isArray(value) ? value : value && typeof value === "object" ? [value] : [];
  return rows.slice(0, 12).filter(x => x && typeof x === "object").map(x => Object.fromEntries(Object.entries(x).filter(([k]) => allowed.has(k))));
}
