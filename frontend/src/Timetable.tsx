import { createPortal, flushSync } from "react-dom";
import { shortScheduleName } from "./exportNames";
import { LockSessionButton } from "./AssignmentLocks";
import { RunSettings, PreparationReport, settingsFor } from "./RunChecks";
import { PartPlan, unitLabel, type Parts } from "./PartPlan";
export const TIMETABLE_FILTER = "jadwai-timetable-filter";
/** What the Timetable page shows right now (the draft and its filters), for Ask JAI's "this timetable". */
export const timetableOnScreen: { run_id?: string; group?: string; year?: string; major?: string } = {};
/** Show the Timetable page filtered to one group (or year / programme), mounted or not. */
export function showTimetableFilter(filter: { group?: string; year?: string; major?: string; run_id?: string }) {
  try { sessionStorage.setItem(TIMETABLE_FILTER, JSON.stringify(filter)); } catch { /* storage unavailable */ }
  window.dispatchEvent(new CustomEvent(TIMETABLE_FILTER, { detail: filter }));
}
import { RepairPanel } from "./RepairPanel";
import { errors } from "./i18n";
import { SchedulePrint } from "./SchedulePrint";
import { ScenarioActions } from "./ScenarioActions";
import { useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  downloadScheduleStatistics,
  downloadTimetablePdf,
  type Workspace,
  type ScheduleRun,
  type RunMeta,
} from "./api";
import { Icon } from "./components";

const copy = {
  en: {
    eyebrow: "YOUR WEEK, ARRANGED",
    title: "A little structure. A lot of possibility.",
    intro:
      "Turn your semester’s activities and approved rules into a weekly draft.",
    generate: "Generate schedule",
    generating: "Arranging your week…",
    cancel: "Cancel generation",
    cancelling: "Cancelling…",
    history: "Recent drafts",
    empty: "Your next week starts here.",
    emptyText:
      "Add teaching activities, eligible instructors, student groups and rooms. Then let JadwAI arrange the pieces.",
    activities: "activities",
    sessions: "weekly sessions",
    rules: "approved rules",
    draft: "Draft timetable",
    version: "Input version",
    stale:
      "Your inputs have changed. Generate a new draft to use the latest data.",
    current: "Matches your current inputs",
    checks: "Supported checks passed",
    limits:
      "Every saved draft passes independent checks of all approved rules, locks and doctor/TA assignments. Publish a draft to show it to instructors and students; publishing re-checks it against the current inputs.",
    preference: "Sessions outside preferred periods",
    preferenceHelp:
      "For instructors with approved preferred periods, a session counts once when it fits entirely within none of those periods. Lower is better.",
    noSolution: "These inputs don’t fit together yet.",
    queued: "Your draft is in the queue.",
    running: "Finding room for every session…",
    waiting:
      "You can leave this page. Your run is saved and will continue in the background.",
    unknown:
      "The search limit was reached before a complete schedule was found. This does not prove the inputs are impossible. Try again or simplify the inputs.",
    cancelled: "Generation cancelled. Your semester data is unchanged.",
    failed:
      "This run could not finish. Your inputs are safe; you can try again.",
    blocked: "This draft needs a little more preparation.",
    no_suitable_room:
      "An activity has no room with enough capacity, the right type and required equipment.",
    no_available_placement:
      "An activity has no available placement with its eligible instructors and approved availability rules.",
    conflicting_requirements:
      "No complete timetable satisfies the supported mandatory checks. Review shared groups, rooms and instructor availability.",
    input_checks_failed:
      "Some inputs cannot all hold together, so no timetable was generated.",
    instance_too_large:
      "This is more than one run can place at once. Generate the whole timetable again: it is now built in parts automatically. You can also choose the parts yourself under “Build in parts”.",
    missing_data:
      "Add at least one teaching activity and a suitable room first.",
    error: "Could not load schedules. Please try again.",
    retry: "Retry",
    all: "All groups",
    group: "Student group",
    noDay: "Room to breathe",
    viewer:
      "Schedule generation and unpublished drafts are available to administrators.",
    unavailable:
      "The scheduling worker is unavailable. Start the app’s worker and try again.",
    active: "A generation is already in progress. Reloading your runs…",
    staleError: "Your inputs changed. Refresh semester data before generating.",
    requestError:
      "Could not start generation. Try again; repeating the request will not create a duplicate run.",
    cancelledTitle: "A fresh start is one click away.",
    time: "Time",
    instructor: "Instructor",
    room: "Room",
    optimal: "Best score proven for the selected objective",
    feasible: "Complete draft found; best objective score not proven",
    rulesNote:
      "Only approved rules are used. Draft rules do not affect generation.",
    timezone: "Timezone",
    refresh: "Refresh semester data",
  },
  ar: {
    eyebrow: "أسبوعك، بترتيب أوضح",
    title: "ترتيب بسيط. احتمالات أجمل.",
    intro: "حوّل أنشطة الفصل والقواعد المعتمدة إلى مسودة جدول أسبوعي.",
    generate: "إنشاء الجدول",
    generating: "جارٍ ترتيب أسبوعك…",
    cancel: "إلغاء الإنشاء",
    cancelling: "جارٍ الإلغاء…",
    history: "المسودات الأخيرة",
    empty: "أسبوعك القادم يبدأ هنا.",
    emptyText:
      "أضف الأنشطة والمدرسين المؤهلين والمجموعات والقاعات، ثم دع JadwAI يرتب التفاصيل.",
    activities: "أنشطة",
    sessions: "حصص أسبوعية",
    rules: "قواعد معتمدة",
    draft: "مسودة الجدول",
    version: "إصدار المدخلات",
    stale: "تغيّرت المدخلات. أنشئ مسودة جديدة لاستخدام أحدث البيانات.",
    current: "يطابق المدخلات الحالية",
    checks: "اجتاز الفحوص المدعومة",
    limits:
      "كل مسودة محفوظة تجتاز فحصاً مستقلاً لكل القواعد المعتمدة والتثبيتات وتوزيع الدكاترة والمعيدين. انشر المسودة ليراها المدرسون والطلاب؛ يعيد النشر فحصها مقابل المدخلات الحالية.",
    preference: "حصص خارج الفترات المفضلة",
    preferenceHelp:
      "للمدرسين الذين لديهم فترات مفضلة معتمدة، تُحسب الحصة مرة إذا لم تقع بالكامل داخل أي منها. الأقل أفضل.",
    noSolution: "هذه المدخلات لا تتوافق معاً بعد.",
    queued: "مسودتك في قائمة الانتظار.",
    running: "نبحث عن مكان لكل حصة…",
    waiting: "يمكنك مغادرة الصفحة. طلبك محفوظ وسيستمر في الخلفية.",
    unknown:
      "انتهت مهلة البحث قبل العثور على جدول كامل. هذا لا يثبت استحالة المدخلات. أعد المحاولة أو بسّط البيانات.",
    cancelled: "أُلغي الإنشاء. بيانات الفصل لم تتغير.",
    failed: "تعذّر إكمال هذا الطلب. مدخلاتك محفوظة ويمكنك المحاولة مجدداً.",
    blocked: "تحتاج هذه المسودة إلى بعض التحضير.",
    no_suitable_room:
      "يوجد نشاط بلا قاعة مناسبة من حيث السعة والنوع والتجهيزات.",
    no_available_placement:
      "يوجد نشاط بلا موعد متاح مع المدرسين المؤهلين وقواعد التوافر المعتمدة.",
    conflicting_requirements:
      "لا يوجد جدول كامل يحقق الفحوص الإلزامية المدعومة. راجع المجموعات والقاعات وتوافر المدرسين.",
    input_checks_failed:
      "بعض المدخلات لا يمكن أن تتحقق معًا، لذلك لم يُنشأ جدول.",
    instance_too_large:
      "هذا أكثر مما يستطيع تشغيل واحد جدولته. أنشئ الجدول كاملاً مرة أخرى: يُنشأ الآن على أجزاء تلقائياً. يمكنك أيضاً اختيار الأجزاء بنفسك من «الإنشاء على أجزاء».",
    missing_data: "أضف نشاطاً تدريسياً وقاعة مناسبة على الأقل أولاً.",
    error: "تعذّر تحميل الجداول. حاول مجدداً.",
    retry: "إعادة المحاولة",
    all: "كل المجموعات",
    group: "المجموعة الطلابية",
    noDay: "مساحة للراحة",
    viewer: "إنشاء الجداول والمسودات غير المنشورة متاح للمسؤولين.",
    unavailable: "عامل إنشاء الجدول غير متاح. شغّل العامل ثم حاول مجدداً.",
    active: "يوجد إنشاء قيد التنفيذ. جارٍ إعادة تحميل الطلبات…",
    staleError: "تغيّرت المدخلات. حدّث بيانات الفصل قبل الإنشاء.",
    requestError:
      "تعذّر بدء الإنشاء. حاول مجدداً؛ لن يؤدي تكرار الطلب إلى إنشاء نسخة مكررة.",
    cancelledTitle: "بداية جديدة بضغطة واحدة.",
    time: "الوقت",
    instructor: "المدرس",
    room: "القاعة",
    optimal: "ثبتت أفضل درجة للهدف المختار",
    feasible: "عُثر على مسودة كاملة دون إثبات أفضل درجة",
    rulesNote:
      "تُستخدم القواعد المعتمدة فقط. قواعد المسودة لا تؤثر على الإنشاء.",
    timezone: "المنطقة الزمنية",
    refresh: "تحديث بيانات الفصل",
  },
};
const days: Record<string, string> = {
  Sunday: "الأحد",
  Monday: "الاثنين",
  Tuesday: "الثلاثاء",
  Wednesday: "الأربعاء",
  Thursday: "الخميس",
  Friday: "الجمعة",
  Saturday: "السبت",
};
const activeRun = (r: { status: string } | undefined) =>
  r && ["queued", "running"].includes(r.status);
const clock = (m: number) =>
  `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

export function Timetable({
  ws,
  lang,
  administrator,
  refresh,
}: {
  ws: Workspace;
  lang: "en" | "ar";
  administrator: boolean;
  refresh: () => Promise<void>;
}) {
  const t = copy[lang];
  const [printing, setPrinting] = useState(false);
  const originalTitle = useRef<string | null>(null);
  useEffect(() => {
    const restoreTitle = () => {
      if (originalTitle.current !== null) document.title = originalTitle.current;
      originalTitle.current = null;
    };
    const done = () => { setPrinting(false); restoreTitle(); };
    window.addEventListener("afterprint", done);
    return () => { window.removeEventListener("afterprint", done); restoreTitle(); };
  }, []);
  // The list holds every draft's state only; the full timetable is loaded for the selected draft.
  const [runs, setRuns] = useState<RunMeta[]>([]);
  const [detail, setDetail] = useState<ScheduleRun | null>(null);
  const [tick, setTick] = useState(0);
  const [nonce, setNonce] = useState(0);
  const [selected, setSelected] = useState("");
  const [group, setGroup] = useState("");
  const [yearFilter, setYearFilter] = useState("");
  const [majorFilter, setMajorFilter] = useState("");
  // Ask JAI can open this page on one group, year or programme (for example after generating it).
  useEffect(() => {
    const apply = (f: { group?: string; year?: string; major?: string; run_id?: string } | null) => {
      if (!f) return;
      if (f.run_id) { setSelected(f.run_id); requestKey.current = null; }
      setGroup(f.group || ""); setYearFilter(f.year || ""); setMajorFilter(f.major || "");
    };
    try { const saved = sessionStorage.getItem(TIMETABLE_FILTER); sessionStorage.removeItem(TIMETABLE_FILTER); apply(saved ? JSON.parse(saved) : null); } catch { /* storage unavailable */ }
    const listen = (e: Event) => apply((e as CustomEvent).detail);
    window.addEventListener(TIMETABLE_FILTER, listen);
    return () => window.removeEventListener(TIMETABLE_FILTER, listen);
  }, []);
  const [layout, setLayout] = useState<"rows" | "columns">(() => {
    try {
      return localStorage.getItem("jadwai-schedule-layout") === "columns"
        ? "columns"
        : "rows";
    } catch {
      return "rows";
    }
  });
  const changeLayout = (value: "rows" | "columns") => {
    setLayout(value);
    try {
      localStorage.setItem("jadwai-schedule-layout", value);
    } catch {
      /* Layout still works when browser storage is unavailable. */
    }
  };
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [settings,setSettings] = useState(() => settingsFor(ws));
  const [historical,setHistorical] = useState(false);
  const [parts,setParts] = useState<Parts|null>(null);
  const [error, setError] = useState("");
  const [errorKind, setErrorKind] = useState("");
  const requestKey = useRef<string | null>(null);
  const [reportBusy, setReportBusy] = useState(false);
  const [reportNotice, setReportNotice] = useState("");
  const saveStatistics = async (
    id: string,
    format: "pdf" = "pdf",
  ) => {
    setReportBusy(true);
    setReportNotice("");
    try {
      await downloadScheduleStatistics(id, format, group ? { group } : { year: yearFilter, major: majorFilter });
    } catch {
      setReportNotice(
        lang === "ar"
          ? "تعذّر تنزيل التقرير. حاول مرة أخرى."
          : "The statistics report could not be downloaded. Try again.",
      );
    } finally {
      setReportBusy(false);
    }
  };
  // Without a choice, show the published timetable (else the newest finished one), not a draft that failed.
  const selectedMeta =
    runs.find((r) => r.id === selected) ??
    runs.find((r) => r.published_at && r.status === "completed") ??
    runs.find((r) => r.status === "completed") ??
    runs[0];
  // A timetable built in parts continues as a new draft for each part: follow it to the newest part.
  useEffect(() => {
    const next = selectedMeta && runs.find((r) => r.parent_run_id === selectedMeta.id && /· part \d+\/\d+$/.test(r.name || ""));
    if (next) setSelected(next.id);
  }, [runs, selectedMeta?.id]);
  const selectedRun: ScheduleRun | undefined =
    selectedMeta && detail?.id === selectedMeta.id ? { ...detail, ...selectedMeta } : undefined;
  // Load the selected draft once, again when its state changes, and on every poll while it is running.
  const selectedState = selectedMeta
    ? [selectedMeta.id, selectedMeta.status, selectedMeta.cancel_requested, selectedMeta.name, selectedMeta.published_at, selectedMeta.input_version].join("|")
    : "";
  useEffect(() => {
    if (!selectedMeta) return;
    let live = true;
    api<ScheduleRun>(`/schedules/${encodeURIComponent(selectedMeta.id)}`)
      .then((full) => { if (live) setDetail(full); })
      .catch(() => { if (live) setErrorKind("load"); });
    return () => { live = false; };
  }, [selectedState, nonce, activeRun(selectedMeta) ? tick : 0]);
  useEffect(() => {
    Object.assign(timetableOnScreen, { run_id: selectedRun?.id, group: group || undefined, year: yearFilter || undefined, major: majorFilter || undefined });
    return () => { for (const k of Object.keys(timetableOnScreen)) delete (timetableOnScreen as Record<string, unknown>)[k]; };
  }, [selectedRun?.id, group, yearFilter, majorFilter]);
  // A chosen group shows its own study year and major in the other two filters.
  useEffect(() => {
    const g = group ? (selectedRun?.snapshot.records ?? ws.records).find((r) => r.id === group) : undefined;
    if (!g) return;
    setYearFilter(g.year ? String(g.year) : "unassigned");
    setMajorFilter(g.major || "__unassigned");
  }, [group, selectedRun?.id]);
  const pending = runs.find((r) => activeRun(r));
  useEffect(() => {
    if (!administrator) {
      setLoading(false);
      return;
    }
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try {
        const result = await api<RunMeta[]>("/schedules?summary=true");
        if (!disposed) {
          setRuns(result);
          setTick((n) => n + 1);
          setLoading(false);
          setErrorKind("");
        }
      } catch {
        if (!disposed) {
          setErrorKind("load");
          setLoading(false);
        }
      }
      if (!disposed) timer = setTimeout(poll, 2000);
    };
    void poll();
    return () => {
      disposed = true;
      clearTimeout(timer);
    };
  }, [administrator, ws.version]);
  const reload = async () => { setRuns(await api<RunMeta[]>("/schedules?summary=true")); setNonce((n) => n + 1); };
  const generate = async () => {
    setBusy(true);
    setError("");
    requestKey.current ??= crypto.randomUUID();
    try {
      const run = await api<ScheduleRun>(
        "/schedules",
        "POST",
        { request_key: requestKey.current, settings, ...(historical && selectedRun ? {source_run_id:selectedRun.id} : {}), ...(parts ? {scope:parts.scope, ...(parts.base ? {base_run_id:parts.base} : {})} : {}) },
        ws.version,
      );
      requestKey.current = null;
      setRuns((old) =>
        [run, ...old.filter((r) => r.id !== run.id)].slice(0, 10),
      );
      setDetail(run);
      setSelected(run.id);
      setHistorical(false);
      setParts(null);
      // Keep the year, programme and group being viewed: the new draft uses the same data.
    } catch (e) {
      const code = e instanceof ApiError ? e.code : "";
      setError(
        code === "worker_unavailable"
          ? t.unavailable
          : code === "schedule_active"
            ? t.active
            : code === "stale_edit"
              ? t.staleError
              : code === "schedule_missing_data"
                ? t.missing_data
                : errors[code]
                  ? errors[code][lang === "ar" ? 1 : 0]
                  : t.requestError,
      );
      if (e instanceof ApiError && e.status !== 0 && e.status < 500)
        requestKey.current = null;
      if (code === "schedule_active") await reload().catch(() => {});
      if (code === "stale_edit") await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  };
  const cancel = async () => {
    if (!pending) return;
    setBusy(true);
    setError("");
    try {
      await api(`/schedules/${pending.id}/cancel`, "POST");
      await reload();
    } catch {
      setError(t.requestError);
    } finally {
      setBusy(false);
    }
  };
  if (!administrator)
    return (
      <section className="panel">
        <p>{t.viewer}</p>
      </section>
    );
  const activities = ws.records.filter((r) => r.kind === "courses");
  const run = selectedRun;
  // The draft's own records when one is shown; before any timetable exists, the current academic data,
  // so the year, major and group filters are always available.
  const records = run?.snapshot.records ?? ws.records;
  const record = (id: string) => records.find((r) => r.id === id);
  const groupRecords = records.filter((r) => r.kind === "groups");
  const years = [
    ...new Set(
      groupRecords.map((r) => (r.year ? String(r.year) : "unassigned")),
    ),
  ].sort((a, b) => (Number(a) || 99) - (Number(b) || 99));
  const yearGroups = groupRecords.filter(
    (r) =>
      !yearFilter || (r.year ? String(r.year) : "unassigned") === yearFilter,
  );
  const majors = [
    ...new Set(yearGroups.map((r) => r.major || "__unassigned")),
  ].sort((a, b) => a.localeCompare(b));
  const visibleGroups = yearGroups.filter(
    (r) => !majorFilter || (r.major || "__unassigned") === majorFilter,
  );
  const matchesGroup = (activityId: string) => {
    const ids = record(activityId)?.group_ids ?? [];
    return group
      ? ids.includes(group)
      : !yearFilter && !majorFilter
        ? true
        : visibleGroups.some((g) => ids.includes(g.id));
  };
  const groupLabel = (id: string) => {
    const g = record(id);
    return [
      g?.year ? `${lang === "ar" ? "السنة" : "Year"} ${g.year}` : "",
      g?.major,
      g?.name,
    ]
      .filter(Boolean)
      .join(" / ");
  };
  const result = run?.result;
  const completed = run?.status === "completed" && result?.validation?.passed;
  const stale = run && (run.stale || run.input_version !== ws.version);
  const statusText = (r: RunMeta) =>
    ({
      queued: t.queued,
      running: t.running,
      completed: t.draft,
      blocked: t.blocked,
      infeasible: t.noSolution,
      unknown: t.unknown,
      cancelled: t.cancelled,
      failed: t.failed,
    })[r.status];
  const reason = result?.reason;
  const printScope = group
    ? groupLabel(group)
    : [
        yearFilter
          ? yearFilter === "unassigned"
            ? lang === "ar"
              ? "سنة غير محددة"
              : "Unassigned year"
            : `${lang === "ar" ? "السنة" : "Year"} ${yearFilter}`
          : "",
        majorFilter
          ? majorFilter === "__unassigned"
            ? lang === "ar"
              ? "تخصص غير محدد"
              : "Unassigned major"
            : majorFilter
          : "",
      ]
        .filter(Boolean)
        .join(" / ") ||
      (lang === "ar"
        ? "كل السنوات والتخصصات والمجموعات"
        : "All years, majors and groups");
  const savePdf = () => {
    if (!run) return;
    originalTitle.current ??= document.title;
    document.title = shortScheduleName(group ? record(group) as Parameters<typeof shortScheduleName>[0] : undefined, yearFilter, majorFilter);
    flushSync(() => setPrinting(true));
    try { window.print(); }
    catch (error) {
      document.title = originalTitle.current;
      originalTitle.current = null;
      setPrinting(false);
      throw error;
    }
  };
  return (
    <div className="schedule-page">
      {printing &&
        completed &&
        run &&
        result &&
        createPortal(
          <SchedulePrint
            run={run}
            assignments={result.assignments.filter((a) =>
              matchesGroup(a.activity_id),
            )}
            lang={lang}
            scope={printScope}
            stale={!!stale}
          />,
          document.body,
        )}
      <section className="generation-hero panel">
        <div>
          <div className="eyebrow">{t.eyebrow}</div>
          <h2>{t.title}</h2>
          <p>{t.intro}</p>
          <div className="generation-stats">
            <span>
              <b>{activities.length}</b> {t.activities}
            </span>
            <span>
              <b>{activities.reduce((sum, r) => sum + (r.sessions ?? 0), 0)}</b>{" "}
              {t.sessions}
            </span>
            <span>
              <b>{ws.rules.filter((r) => r.status === "approved").length}</b>{" "}
              {lang === "en" && ws.rules.filter((r) => r.status === "approved").length === 1 ? "approved rule" : t.rules}
            </span>
          </div>
          <small>{t.rulesNote}</small>
        </div>
        <div className="generation-action">
          <span className="generation-emblem">
            <Icon name="calendar" size={38} />
          </span>
          <button
            className="btn primary"
            disabled={
              busy ||
              !!pending ||
              (!!parts && !parts.scope.length) ||
              loading ||
              !activities.length ||
              !ws.records.some((r) => r.kind === "rooms")
            }
            onClick={() => void generate()}
          >
            <Icon name="spark" size={18} />
            {pending ? t.generating : t.generate}
          </button>
          <span>{ws.term}</span>
        </div>
      </section>
      {administrator && selectedRun && !activeRun(selectedRun) && <label className="check-label"><input type="checkbox" checked={historical} disabled={busy||!!pending} onChange={e=>{setHistorical(e.target.checked);requestKey.current=null;}}/>{lang==="ar"?"إعادة الإنشاء من المدخلات المحفوظة للمسودة المختارة؛ تجاهل التغييرات الحالية":"Generate from the selected draft’s saved inputs, ignoring current input changes"}</label>}
      {administrator && !historical && <PartPlan ws={ws} ar={lang==="ar"} parts={parts} base={selectedRun} disabled={busy||!!pending} change={p=>{setParts(p);requestKey.current=null;}}/>}
      {administrator && selectedRun?.progress && !selectedRun.progress.complete && <p className="notice" role="status">{lang==="ar"?`جزء من الجدول: ${selectedRun.progress.scheduled_sessions} من ${selectedRun.progress.total_sessions} حصة. المتبقي: ${selectedRun.progress.remaining_programmes.map(u=>unitLabel(u,true)).join("، ")}`:`Part of the timetable: ${selectedRun.progress.scheduled_sessions} of ${selectedRun.progress.total_sessions} sessions. Still to schedule: ${selectedRun.progress.remaining_programmes.map(u=>unitLabel(u,false)).join(", ")}`}</p>}
      {administrator && <RunSettings ws={ws} ar={lang==="ar"} settings={settings} change={v=>{setSettings(v);requestKey.current=null;}} disabled={busy||!!pending}/>}
      {(error || errorKind) && (
        <div className="error" role="alert">
          {error || t.error}
        </div>
      )}
      {pending && (
        <section className="panel generation-progress" role="status">
          <div className="loader" />
          <div>
            <strong>
              {pending.cancel_requested ? t.cancelling : statusText(pending)}
            </strong>
            <p>{t.waiting}</p>
            {pending.id === selectedRun?.id && selectedRun.result?.progress && <p>{lang==="ar"?"أفضل درجة بحث حتى الآن":"Best search score so far"}: {selectedRun.result.progress.best_objective} · {lang==="ar"?"ليست نتيجة معتمدة بعد":"Not yet independently validated"}</p>}
          </div>
          <button
            className="btn secondary"
            disabled={busy || pending.cancel_requested}
            onClick={() => void cancel()}
          >
            {pending.cancel_requested ? t.cancelling : t.cancel}
          </button>
        </section>
      )}
      {(runs.length > 0 || groupRecords.length > 0) && (
        <div className="schedule-toolbar">
          {runs.length > 0 && <label>
            {t.history}
            <select
              value={run?.id ?? ""}
              onChange={(e) => {
                // The year, major and group being viewed stay chosen for the other draft.
                setSelected(e.target.value);
                requestKey.current=null;
              }}
              aria-label={t.history}
            >
              {runs.map((r) => (
                <option key={r.id} value={r.id}>
                  {new Date(r.created_at).toLocaleString(
                    lang === "ar" ? "ar-EG" : "en-GB",
                  )}{" "}
                  · v{r.input_version} · {statusText(r)}{r.name ? ` · ${r.name}` : ""}{r.published_at ? " ✓" : ""}
                </option>
              ))}
            </select>
          </label>}
          {groupRecords.length > 0 && (
            <>
              <label>
                {lang === "ar" ? "السنة الدراسية" : "Study year"}
                <select
                  value={yearFilter}
                  onChange={(e) => {
                    setYearFilter(e.target.value);
                    setMajorFilter("");
                    setGroup("");
                  }}
                >
                  <option value="">
                    {lang === "ar" ? "كل السنوات" : "All years"}
                  </option>
                  {years.map((year) => (
                    <option key={year} value={year}>
                      {year === "unassigned"
                        ? lang === "ar"
                          ? "سنة غير محددة"
                          : "Unassigned year"
                        : `${lang === "ar" ? "السنة" : "Year"} ${year}`}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {lang === "ar" ? "التخصص" : "Major"}
                <select
                  value={majorFilter}
                  onChange={(e) => {
                    setMajorFilter(e.target.value);
                    setGroup("");
                  }}
                >
                  <option value="">
                    {lang === "ar" ? "كل التخصصات" : "All majors"}
                  </option>
                  {majors.map((major) => (
                    <option key={major} value={major}>
                      {major === "__unassigned"
                        ? lang === "ar"
                          ? "تخصص غير محدد"
                          : "Unassigned major"
                        : major}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                {t.group}
                <select
                  value={group}
                  onChange={(e) => setGroup(e.target.value)}
                >
                  <option value="">{t.all}</option>
                  {[...visibleGroups].sort((a, b) => groupLabel(a.id).localeCompare(groupLabel(b.id), undefined, { numeric: true })).map((r) => (
                    <option key={r.id} value={r.id}>
                      {groupLabel(r.id)}
                    </option>
                  ))}
                </select>
              </label>
            </>
          )}
          {!completed && (yearFilter || majorFilter || group) && (
            <p className="room-type-help" role="status">
              {lang === "ar"
                ? "سيُعرض الجدول بهذا الاختيار بمجرد إنشائه أو اختيار مسودة مكتملة. يُنشئ زر الإنشاء الجدول كاملاً؛ لإنشاء بعض البرامج فقط استخدم «الإنشاء على أجزاء»."
                : "The timetable is shown for this choice as soon as one is generated or a finished draft is selected. Generate builds the whole timetable; to generate only some programmes, use “Build in parts”."}
            </p>
          )}
        </div>
      )}
      {stale && (
        <div className="schedule-warning" role="status">
          <Icon name="clock" size={20} />
          {t.stale}
          <button
            className="btn secondary"
            onClick={() => void refresh().catch(() => setError(t.error))}
          >
            {t.refresh}
          </button>
        </div>
      )}
      {completed && run && (
        <section className="panel schedule-result">
          <div className="schedule-result-heading">
            <div>
              <div className="eyebrow">
                {t.draft} · {t.version} {run.input_version}
              </div>
              <h2>{run.snapshot.term}</h2>
              <p>
                {t.timezone}: <bdi>{run.snapshot.calendar.timezone}</bdi>
              </p>
            </div>
            <div className="schedule-export-actions">
              <span className="validation-badge">
                <Icon name="check" size={16} />
                {t.checks}
              </span>
              <button type="button" className="btn white" onClick={() => run && downloadTimetablePdf(run.id, group ? { group } : { year: yearFilter, major: majorFilter })}>
                <Icon name="book" size={17} />
                {lang === "ar" ? "حفظ بصيغة PDF" : "Save as PDF"}
              </button>
              <button type="button" className="btn white" onClick={savePdf}>
                {lang === "ar" ? "طباعة" : "Print"}
              </button>
              <button
                type="button"
                className="btn white"
                disabled={reportBusy}
                onClick={() => void saveStatistics(run.id)}
              >
                <Icon name="book" size={17} />
                {lang === "ar" ? "تنزيل تقرير PDF" : "Download report PDF"}
              </button>
              <small>
                {lang === "ar"
                  ? "«حفظ بصيغة PDF» ينزّل ملفًا أفقيًا لما تعرضه، باسم قصير مثل BA Y3 G7 Schedule."
                  : "Save as PDF downloads a landscape file of what you are viewing, named like “BA Y3 G7 Schedule”."}
              </small>{" "}
              <small>
                {lang === "ar"
                  ? (group || yearFilter || majorFilter ? `تقرير PDF لـ ${printScope}، مع رسوم بيانية.` : "تقرير PDF للجدول الكامل مع رسوم بيانية. اختر سنة أو برنامجًا أو مجموعة لتقرير خاص بها.")
                  : (group || yearFilter || majorFilter ? `PDF summary with charts for ${printScope}.` : "PDF summary with charts for the full schedule. Choose a year, programme or group for its own report.")}
              </small>
              {reportNotice && <small role="alert">{reportNotice}</small>}
            </div>
            {administrator && <ScenarioActions key={run.id} ws={ws} run={run} runs={runs} lang={lang} reload={reload} select={setSelected} notify={setReportNotice} shows={matchesGroup} scope={group || yearFilter || majorFilter ? printScope : ""}/>}
          </div>
          <div
            className="schedule-layout-switch"
            role="group"
            aria-label={lang === "ar" ? "طريقة عرض الجدول" : "Schedule layout"}
          >
            <button
              type="button"
              aria-label={
                lang === "ar" ? "الأيام على اليسار" : "Days on the left"
              }
              title={lang === "ar" ? "الأيام على اليسار" : "Days on the left"}
              aria-pressed={layout === "rows"}
              onClick={() => changeLayout("rows")}
            >
              <Icon name="sliders" size={15} />
            </button>
            <button
              type="button"
              aria-label={
                lang === "ar" ? "الأيام في الأعلى" : "Days across the top"
              }
              title={lang === "ar" ? "الأيام في الأعلى" : "Days across the top"}
              aria-pressed={layout === "columns"}
              onClick={() => changeLayout("columns")}
            >
              <Icon name="grid" size={15} />
            </button>
          </div>
          <div className="subtle-banner" role="status">
            {result.validation?.workload?.some(w => w.standard_weekly_hours === 12) ? <div>{lang === "ar" ? "الحمل الأساسي: ١٢ ساعة أسبوعيًا؛ ما يزيد يُحسب وقتًا إضافيًا." : "Standard load: 12 hours/week; additional hours count as extra time."}<ul>{result.validation.workload.filter(w => (w.extra_hours || 0) > 0).map(w => <li key={w.instructor_id}>{run.snapshot.records.find(r => r.id === w.instructor_id)?.name || w.instructor_id}: {w.assigned_hours} {lang === "ar" ? "ساعة، إضافي" : "hours, extra time"}: {w.extra_hours}</li>)}</ul></div> : result.validation?.workload ? (lang === "ar" ? `الحدود الأسبوعية: ${result.validation.workload.filter(w => w.configured).length} من ${result.validation.workload.length} مدرسين لديهم حد محدد. الحدود غير المحددة لم تُفحص.` : `Weekly maxima: ${result.validation.workload.filter(w => w.configured).length} of ${result.validation.workload.length} instructors configured. Missing maxima are not checked.`) : (lang === "ar" ? "لم تُسجل حدود أسبوعية في تقرير هذه المسودة. أعد الإنشاء لفحص الحدود الحالية." : "Weekly maxima were not recorded for this saved draft. Regenerate to check current limits.")}
          </div>
          <div className="subtle-banner" role="status">
            {result.validation?.realism ? (lang === "ar" ? `سياسة يومية مفعّلة: الطالب ${result.validation.realism.policy?.student_daily_hours ?? "—"} ساعة؛ المدرس ${result.validation.realism.policy?.instructor_daily_hours ?? "—"} ساعة. فترات الفراغ: ${result.validation.realism.idle_periods}.` : `Daily policy checked: students ${result.validation.realism.policy?.student_daily_hours != null ? `${result.validation.realism.policy.student_daily_hours} hours` : "no limit set"}; instructors ${result.validation.realism.policy?.instructor_daily_hours != null ? `${result.validation.realism.policy.instructor_daily_hours} hours` : "no limit set"}. Total idle teaching periods: ${result.validation.realism.idle_periods}.`) : (lang === "ar" ? "لم تُفحص سياسة توزيع يومية في هذه المسودة المحفوظة." : "A practical-day policy was not checked for this saved draft.")}
          </div>
          {layout === "columns" && (
            <p className="schedule-scroll-hint">
              {lang === "ar"
                ? "مرّر أفقياً لعرض جميع الأيام."
                : "Scroll sideways to see every day."}
            </p>
          )}
          <div
            className={`weekly-board weekly-board--${layout}`}
            role="region"
            aria-label={lang === "ar" ? "الجدول الأسبوعي" : "Weekly timetable"}
            tabIndex={0}
          >
            {run.snapshot.calendar.days.map((day) => (
              <section className="schedule-day" key={day}>
                <h3>{lang === "ar" ? (days[day] ?? day) : day}</h3>
                <div
                  className="day-sessions"
                  dir={lang === "ar" ? "rtl" : "ltr"}
                >
                  {result.assignments
                    .filter((a) => a.day === day && matchesGroup(a.activity_id))
                    .sort(
                      (a, b) =>
                        a.start_minute - b.start_minute ||
                        a.activity_id.localeCompare(b.activity_id),
                    )
                    .map((a) => {
                      const activity = record(a.activity_id);
                      return (
                        <article
                          className={`session-card ${activity?.activity_type === "lab" ? "session-lab" : ""}`}
                          key={`${a.activity_id}-${a.occurrence}`}
                        >
                          <time dir="ltr">
                            {clock(a.start_minute)} – {clock(a.end_minute)}
                          </time>
                          <strong>{activity?.name}</strong>
                          <span className="session-code" dir="auto">
                            {activity?.code} · {a.occurrence + 1}/
                            {activity?.sessions}
                          </span>
                          <span>
                            <Icon name="people" size={14} />
                            {record(a.instructor_id)?.name}
                          </span>
                          <span>
                            <Icon name="room" size={14} />
                            {record(a.room_id)?.name} ·{" "}
                            <bdi>{record(a.room_id)?.code}</bdi>
                          </span>
                          {administrator && <LockSessionButton ws={ws} run={run} assignment={a} lang={lang} refresh={refresh}/>}
                          <small>
                            {activity?.group_ids
                              ?.map((g) => groupLabel(g))
                              .join(" · ")}
                          </small>
                        </article>
                      );
                    })}
                  {!result.assignments.some(
                    (a) => a.day === day && matchesGroup(a.activity_id),
                  ) && <p className="free-day">{t.noDay}</p>}
                </div>
              </section>
            ))}
          </div>
          <div className="schedule-score">
            <strong>{result.preference_penalty ?? 0}</strong>
            <div>
              <b>{t.preference}</b>
              <p>{t.preferenceHelp}</p>
              <small>{result.optimal ? t.optimal : t.feasible}</small>
            </div>
          </div>
        </section>
      )}
      {result?.preflight && !result.preflight.ready && <PreparationReport report={result.preflight} ws={ws} ar={lang==="ar"}/>}
      {!completed && run && !activeRun(run) && (
        <section className="panel generation-outcome" role="status">
          <Icon name="calendar" size={36} />
          <h2>
            {run.status === "cancelled"
              ? t.cancelledTitle
              : run.status === "infeasible"
                ? t.noSolution
                : run.status === "blocked"
                  ? t.blocked
                  : run.status === "unknown"
                    ? lang === "ar"
                      ? "انتهت مهلة البحث."
                      : "The search needs more time."
                    : t.failed}
          </h2>
          <p>
            {reason && reason in t
              ? t[reason as keyof typeof t]
              : statusText(run)}
          </p>
          {result?.activity_id && <b>{record(result.activity_id)?.name}</b>}
          {result?.repair && <RepairPanel repair={result.repair} ar={lang === "ar"} />}
        </section>
      )}
      {!run && !loading && selectedMeta && (
        <p className="room-type-help" role="status">{lang === "ar" ? "جارٍ تحميل المسودة المختارة…" : "Loading the selected draft…"}</p>
      )}
      {!run && !loading && !selectedMeta && (
        <section className="panel generation-outcome">
          <Icon name="calendar" size={36} />
          <h2>{t.empty}</h2>
          <p>{t.emptyText}</p>
        </section>
      )}
      {result?.validation?.coverage && <details className="panel run-evidence"><summary>{lang==="ar"?"تغطية الفحوصات":"Validation coverage"}</summary><p>{result.validation.conflict_basis}</p><ul className="coverage-grid">{result.validation.coverage.map(c=><li key={c.check}><strong>{c.check.replaceAll("_"," ")}</strong><span className={`pill ${c.status==="passed"?"green":c.status==="failed"?"amber":""}`}>{c.status.replaceAll("_"," ")}</span><small>{c.applicable??"—"} {c.basis}</small></li>)}</ul>{!!result.validation.violations?.length && <ul>{result.validation.violations.map((v,i)=><li key={i}>{v.message} · {v.sessions.map(a=>`${record(a.activity_id)?.name||a.activity_id} #${a.occurrence+1} ${a.day||""}`).join("; ")} · {v.rule_ids.join(", ")}</li>)}</ul>}</details>}
      {run && !activeRun(run) && <details className="panel run-evidence">
        <summary>{lang === "ar" ? "تفاصيل إنشاء المسودة" : "How this draft was generated"}</summary>
        {result?.provenance ? <>
          <p>{lang === "ar" ? "مدة المعالجة بالثواني" : "Worker elapsed seconds"}: {result.provenance.worker_elapsed_seconds}</p>
          <p>{lang === "ar" ? "إصدار الفاحص" : "Validator version"}: {result.provenance.validator_version || "—"}</p>
          {result.provenance.snapshot ? <><p>SHA-256 · {lang === "ar" ? "المدخلات" : "Saved inputs"}</p><code>{result.provenance.snapshot.snapshot_sha256}</code><p>SHA-256 · {lang === "ar" ? "الإعدادات" : "Configuration"}</p><code>{result.provenance.snapshot.config_sha256}</code></> : <p>{lang === "ar" ? "لم تُسجل بصمات لهذه المدخلات القديمة." : "Fingerprints were not recorded for these legacy inputs."}</p>}
          {result.solver_diagnostics && <><p>OR-Tools {result.solver_diagnostics.ortools_version} · {result.solver_diagnostics.raw_status}</p><p>{result.solver_diagnostics.objective_definition}</p><pre>{result.solver_diagnostics.parameters_text}</pre></>}
          <p>{lang === "ar" ? "قد ينتج البحث المتوازي جداول مختلفة رغم تطابق المدخلات والبذرة." : result.provenance.reproducibility_note}</p>
        </> : <p>{lang === "ar" ? "لم تُسجل تفاصيل الإنشاء لهذه المسودة القديمة. أنشئ مسودة جديدة لتسجيلها." : "Generation evidence was not recorded for this older draft. Generate a new draft to record it."}</p>}
      </details>}
      <div className="publication-note">
        <Icon name="lock" size={18} />
        {t.limits}
      </div>
    </div>
  );
}
