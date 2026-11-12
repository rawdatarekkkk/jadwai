import type { IconName } from "./components";
import React, { useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  type Workspace,
  type User,
  type DataRecord,
  type RecordKind,
  type Rule,
} from "./api";
import { words, errors, type Word } from "./i18n";
import { BRAND } from "./brand";
import { StudentPortal } from "./StudentPortal";
import { describeRule } from "./RuleText";
import { TypedConstraint } from "./TypedConstraint";
import { AssignmentLocks } from "./AssignmentLocks";
import { GroupHierarchy } from "./GroupHierarchy";
import { Timetable } from "./Timetable";
import { ImportData } from "./ImportData";
import { CalendarSettings } from "./CalendarSettings";
import { Accounts, MyAccount, ResetAccess } from "./Accounts";

import {
  Icon,
  ScheduleArt,
  Empty,
  EventList,
  Modal,
  RecordForm,
  RuleForm,
} from "./components";
type Page =
  "overview" | "data" | "constraints" | "timetable" | "activity" | "accounts" | "evaluation" | "proposals";
const kindIcons: Record<RecordKind, IconName> = {
  courses: "book",
  instructors: "people",
  rooms: "room",
  groups: "people",
};
import type {BrowserReviewSnapshot} from "./BrowserAnnotationReview";
import {Proposals} from "./Proposals";
import { Evaluation } from "./Evaluation";
import { ExamSchedule } from "./ExamSchedule";
import { SourceTimetables } from "./SourceTimetables";
import { CourseSetup } from "./CourseSetup";
import { AdvisingStudents } from "./AdvisingStudents";
export default function App() {
  const annotationStore=useRef<BrowserReviewSnapshot|null>(null);
  const [lang, setLang] = useState<"en" | "ar">(() =>
    localStorage.getItem("jadwai-language") === "ar" ? "ar" : "en",
  );
  const t = (key: Word) => words[lang][key];
  const [user, setUser] = useState<User | null>(null),
    [ws, setWs] = useState<Workspace | null>(null),
    [boot, setBoot] = useState(true);
  const [page, setPage] = useState<Page>("overview"),
    [kind, setKind] = useState<RecordKind>("courses"),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all");
  const [error, setError] = useState(""),
    [toast, setToast] = useState(""),
    [busy, setBusy] = useState(false);
  const [jaiOpen, setJaiOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [courseSetupOpen, setCourseSetupOpen] = useState(false);
  const [advisingOpen, setAdvisingOpen] = useState(false);
  const [scheduleMode,setScheduleMode] = useState<"teaching"|"exams">("exams");
  const [sessionExpired, setSessionExpired] = useState(false);
  const [resetToken, setResetToken] = useState(() =>
    new URLSearchParams(window.location.hash.slice(1)).get("reset"),
  );
  const clearSession = () => {
    annotationStore.current=null;
    setUser(null);
    setWs(null);
    setPage("overview");
    setAccountOpen(false);
    setCalendarOpen(false);
    setImportOpen(false);
    setSessionExpired(false);
    setModal(null);
    setJaiOpen(false);
  };
  useEffect(() => {
    const expired = () => {
      if (user) setSessionExpired(true);
    };
    const focus = () => {
      if (user && !sessionExpired)
        void api<User>("/auth/me")
          .then(setUser)
          .catch(() => {});
    };
    window.addEventListener("jadwai-session-expired", expired);
    window.addEventListener("focus", focus);
    const timer = setInterval(focus, 60000);
    return () => {
      window.removeEventListener("jadwai-session-expired", expired);
      window.removeEventListener("focus", focus);
      clearInterval(timer);
    };
  }, [user?.id, sessionExpired]);
  const [modal, setModal] = useState<{
    type: "record" | "rule" | "delete";
    record?: DataRecord;
    rule?: Rule;
  } | null>(null);
  const [email, setEmail] = useState<string>(BRAND.adminEmail),
    [password, setPassword] = useState("");
  const message = (e: unknown) =>
    errors[e instanceof ApiError ? e.code : "connection_failed"]?.[
      lang === "en" ? 0 : 1
    ] ||
    (lang === "en"
      ? "Something went wrong. Please try again."
      : "حدث خطأ. حاول مجدداً.");
  useEffect(() => {
    document.documentElement.lang = lang;
    document.documentElement.dir = lang === "ar" ? "rtl" : "ltr";
    localStorage.setItem("jadwai-language", lang);
  }, [lang]);
  const refresh = async () => {
    const identity = await api<User>("/auth/me");
    if (identity.role !== "student") setWs(await api<Workspace>("/workspace"));
  };
  const load = async () => {
    setBoot(true);
    setError("");
    try {
      const identity = await api<User>("/auth/me");
      setUser(identity);
      if (identity.role !== "student") await refresh();
    } catch (e) {
      if (!(e instanceof ApiError && e.status === 401)) setError(message(e));
    } finally {
      setBoot(false);
    }
  };
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    if (toast) {
      const id = setTimeout(() => setToast(""), 4500);
      return () => clearTimeout(id);
    }
  }, [toast]);
  useEffect(() => {
    setQuery("");
    setError("");
  }, [page, kind]);
  const mutate = async (
    path: string,
    method: string,
    body?: unknown,
    success: Word = "changesSaved",
  ) => {
    setBusy(true);
    setError("");
    try {
      await api(path, method, body, ws?.version);
      await refresh();
      setModal(null);
      setToast(t(success));
    } catch (e) {
      setError(message(e));
      if (e instanceof ApiError && e.status === 409)
        await refresh().catch(() => {});
      if (e instanceof ApiError && e.status === 401) {
        setSessionExpired(true);
      }
    } finally {
      setBusy(false);
    }
  };
  const navigate = (p: Page, k?: RecordKind) => {
    setPage(p);
    if (k) setKind(k);
  };
  const switchLanguage = () => setLang(lang === "en" ? "ar" : "en");
  const brand = (
    <div className="brand">
      <span className="brand-mark">
        <i />
        <i />
        <i />
        <i />
      </span>
      <span className="brand-name">
        <span className="wordmark" dir="ltr">
          Jadw<span>AI</span>
        </span>
        <small>{t("tagline")}</small>
      </span>
    </div>
  );
  const language = (
    <button className="language" onClick={switchLanguage}>
      <Icon name="globe" size={16} />
      {t("language")}
    </button>
  );
  if (resetToken)
    return (
      <ResetAccess
        token={resetToken}
        t={t}
        lang={lang}
        onDone={() => {
          window.history.replaceState(
            null,
            "",
            window.location.pathname + window.location.search,
          );
          setResetToken(null);
          clearSession();
          setBoot(false);
        }}
      />
    );
  if (boot)
    return (
      <div className="boot">
        {brand}
        <div className="loader" />
        <p>{t("loading")}</p>
      </div>
    );
  if (!user)
    return (
      <div className="login-layout">
        <section className="login-art">
          {brand}
          <div className="login-copy">
            <div className="eyebrow">UNIVERSITY TIMETABLING, RECONSIDERED</div>
            <h1>{t("loginTitle")}</h1>
            <p>{t("loginText")}</p>
            <ScheduleArt t={t} />
          </div>
          <span className="login-foot">
            A little clarity goes a long way. <Icon name="leaf" />
          </span>
        </section>
        <section className="login-panel">
          {language}
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              try {
                setUser(
                  await api<User>("/auth/login", "POST", { email, password }),
                );
                setPassword("");
                await refresh();
              } catch (e) {
                setError(message(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <span className="login-symbol">
              <Icon name="leaf" size={28} />
            </span>
            <h2>{t("signin")}</h2>
            <p>{t("signinText")}</p>
            {error && (
              <div className="error" role="alert">
                {error}
              </div>
            )}
            <label>
              {t("email")}
              <input
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              {t("password")}
              <input
                type="password"
                autoComplete="current-password"
                required
                maxLength={200}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            <button className="btn primary wide" disabled={busy}>
              {busy ? t("loading") : t("signinButton")}
              <Icon name="arrow" />
            </button>
            <p className="recovery-note">{t("recoveryNote")}</p>
            <p className="login-local">
              <Icon name="lock" size={14} />
              {t("local")}
            </p>
          </form>
        </section>
      </div>
    );
  if (user.role === "student" || user.role === "instructor") return <StudentPortal user={user} lang={lang} setLang={setLang} onSignedOut={clearSession} />;
  const counts = (k: RecordKind) =>
    ws?.records.filter((r) => r.kind === k).length || 0;
  const pending = ws?.rules.filter((r) => r.status === "draft").length || 0;
  const dataReady = ["courses", "instructors", "rooms", "groups"].every(
    (k) => counts(k as RecordKind) > 0,
  );
  const approved = ws?.rules.filter((r) => r.status === "approved").length || 0;
  const heading: Record<Page, [Word, Word]> = {
    overview: ["goodday", "welcome"],
    data: ["academicTitle", "academicText"],
    constraints: ["constraintsTitle", "constraintsText"],
    timetable: ["timetableTitle", "timetableText"],
    activity: ["activityTitle", "activityText"],
    accounts: ["accountsTitle", "accountsText"],
    evaluation: ["evaluationTitle", "evaluationText"],
    proposals: ["proposalsTitle", "proposalsText"],
  };
  return (
    <div
      className={`app-shell ${user.role !== "administrator" ? "read-only" : ""}`}
    >
      <aside className="sidebar">
        {brand}
        <div className="workspace-switch">
          <span className="workspace-icon">CS</span>
          <span>
            <strong>{ws?.name || t("department")}</strong>
            <small>{ws?.term || t("term")}</small>
          </span>
          <Icon name="chevron" size={14} />
        </div>
        <div className="nav-label">{t("workspace")}</div>
        <nav>
          {(
            [
              "overview",
              "data",
              "constraints",
              "timetable",
              "activity",
              ...(user.role === "administrator" ? ["accounts", "evaluation", "proposals"] : []),
            ] as Page[]
          ).map((p, i) => (
            <button
              key={p}
              aria-label={t(p)}
              className={`nav-item ${page === p ? "active" : ""}`}
              onClick={() => navigate(p)}
            >
              <Icon
                name={
                  (
                    [
                      "grid",
                      "book",
                      "sliders",
                      "calendar",
                      "clock",
                      "people",
                      "spark",
                      "check",
                    ] as IconName[]
                  )[i]
                }
              />
              <span>{t(p)}</span>
              {p === "constraints" && pending > 0 && <b>{pending}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="side-note">
            <Icon name="leaf" size={25} />
            <p>{t("sidebarNote")}</p>
            <span>✳</span>
          </div>
          <div className="user">
            <span className="avatar">
              {user.name
                .split(" ")
                .map((n) => n[0])
                .slice(0, 2)
                .join("")}
            </span>
            <span>
              <strong>{user.name}</strong>
              <small>
                {t(user.role === "administrator" ? "admin" : "viewer")}
              </small>
            </span>
            <button
              className="icon-btn"
              title={t("signout")}
              aria-label={t("signout")}
              onClick={async () => {
                try {
                  await api("/auth/logout", "POST");
                  clearSession();
                } catch (e) {
                  setError(message(e));
                }
              }}
            >
              <Icon name="logout" size={17} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            {t("workspace")} <span>/</span>
            <strong>{t(page)}</strong>
          </div>
          <div className="top-actions">
            {user.role === "administrator" && (
              <button
                className="language calendar-settings-btn"
                aria-label={t("semesterSettings")}
                title={t("semesterSettings")}
                onClick={() => setCalendarOpen(true)}
              >
                <Icon name="calendar" size={17} />
                <span>{t("semesterSettings")}</span>
              </button>
            )}
            {language}
            <span className="top-divider" />
            <button
              className="tiny-avatar"
              title={t("myAccount")}
              aria-label={t("myAccount")}
              onClick={() => setAccountOpen(true)}
            >
              {user.name[0]}
            </button>
          </div>
        </header>
        <main>
          <div className="page-heading">
            <div>
              <div className="eyebrow">{ws?.term || t("term")}</div>
              <h1>{page === "timetable" && scheduleMode === "exams" && user.role === "administrator" ? (lang === "ar" ? "جدول امتحاناتك." : "Your exam timetable.") : t(heading[page][0])}</h1>
              <p>{page === "timetable" && scheduleMode === "exams" && user.role === "administrator" ? (lang === "ar" ? "امتحانات منتصف الفصل مدتها ساعتان ضمن فترة مؤرخة." : "Two-hour midterm exams across a dated exam period.") : t(heading[page][1])}</p>
            </div>
            {page === "overview" && (
              <button
                className="btn white"
                onClick={() => {
                  setModal({ type: "rule" });
                  setError("");
                }}
              >
                <Icon name="plus" size={17} />
                {t("newrule")}
              </button>
            )}
          </div>
          {error && !modal && (
            <div className="error" role="alert">
              {error}
              <button onClick={() => void load()}>{t("retry")}</button>
            </div>
          )}
          {!ws ? (
            <div className="empty">
              <p>{errors.connection_failed[lang === "en" ? 0 : 1]}</p>
              <button className="btn primary" onClick={() => void load()}>
                {t("retry")}
              </button>
            </div>
          ) : (
            <>
              {page === "overview" && (
                <>
                  <section className="hero">
                    <div className="hero-copy">
                      <div className="eyebrow">
                        <span className="status-dot" />
                        {t("workspaceLabel")}
                      </div>
                      <h2>{t("hero")}</h2>
                      <p>{t("herotext")}</p>
                      <button
                        className="btn primary"
                        onClick={() => navigate("data")}
                      >
                        {t("continue")}
                        <Icon name="arrow" size={18} />
                      </button>
                      <div className="hero-bottom">
                        <span className="mini-avatar">CS</span>
                        <span>
                          {t("department")} <i>·</i>{" "}
                          {lang === "en"
                            ? "One department. One semester."
                            : "قسم واحد. فصل واحد."}
                        </span>
                      </div>
                    </div>
                    <ScheduleArt t={t} />
                  </section>
                  <section className="stats">
                    {(
                      [
                        "courses",
                        "instructors",
                        "rooms",
                        "groups",
                      ] as RecordKind[]
                    ).map((k) => (
                      <button
                        className="stat"
                        key={k}
                        onClick={() => navigate("data", k)}
                      >
                        <div className="stat-label">
                          <span>{t(k)}</span>
                          <span className={`stat-icon ${k}`}>
                            <Icon name={kindIcons[k]} size={18} />
                          </span>
                        </div>
                        <div className="stat-number">
                          {counts(k).toLocaleString(lang)}
                        </div>
                        <div className="stat-foot">
                          <span>
                            {k === "courses"
                              ? ws.records
                                  .filter((r) => r.kind === "courses")
                                  .reduce((s, r) => s + (r.sessions || 0), 0)
                              : k === "groups"
                                ? ws.records
                                    .filter((r) => r.kind === "groups")
                                    .reduce((s, r) => s + (r.size || 0), 0)
                                : counts(k)}{" "}
                            {t(
                              k === "courses"
                                ? "sessions"
                                : k === "instructors"
                                  ? "eligible"
                                  : k === "rooms"
                                    ? "spaces"
                                    : "students",
                            )}
                          </span>
                          <Icon name="arrow" size={16} />
                        </div>
                      </button>
                    ))}
                  </section>
                  <div className="overview-lower">
                    <section className="panel path-panel">
                      <div className="section-heading">
                        <div>
                          <h3>{t("setup")}</h3>
                          <p>{t("setupsub")}</p>
                        </div>
                        <span className="step-count">
                          {(dataReady ? 1 : 0) +
                            (approved > 0 && pending === 0 ? 1 : 0)}{" "}
                          / 3
                        </span>
                      </div>
                      {(
                        [
                          ["step1", "step1text", dataReady, "data"],
                          [
                            "step2",
                            "step2text",
                            approved > 0 && pending === 0,
                            "constraints",
                          ],
                          ["step3", "step3text", false, "timetable"],
                        ] as const
                      ).map(([title, desc, done, p], i) => (
                        <button
                          className={`path-step ${done ? "done" : ""}`}
                          key={title}
                          onClick={() => navigate(p)}
                        >
                          <span className="step-indicator">
                            {done ? (
                              <Icon name="check" size={17} />
                            ) : (
                              String(i + 1).padStart(2, "0")
                            )}
                          </span>
                          <span className="step-content">
                            <strong>{t(title)}</strong>
                            <small>{t(desc)}</small>
                          </span>
                          <span
                            className={`pill ${done ? "green" : i === 2 ? "neutral" : "amber"}`}
                          >
                            {t(
                              done
                                ? "ready"
                                : i === 2
                                  ? "upcoming"
                                  : "inprogress",
                            )}
                          </span>
                          <Icon name="chevron" size={15} />
                        </button>
                      ))}
                    </section>
                    <section className="panel recent-panel">
                      <div className="section-heading">
                        <h3>{t("recent")}</h3>
                        <Icon name="clock" size={18} />
                      </div>
                      <EventList ws={ws} t={t} lang={lang} limit={3} />
                      <button
                        className="text-link"
                        onClick={() => navigate("activity")}
                      >
                        {t("allactivity")}
                        <Icon name="arrow" size={15} />
                      </button>
                    </section>
                  </div>
                  <div className="source-note">
                    <Icon name="leaf" size={15} />
                    <span>{t("sourceText")}</span>
                    <span>
                      {t("version")} {ws.version}
                    </span>
                  </div>
                </>
              )}
              {page === "data" && (
                <>
                  {user.role === "administrator" && <SourceTimetables lang={lang}/>}
                  <div className="tabs">
                    {(
                      [
                        "instructors",
                        "groups",
                        "rooms",
                        "courses",
                      ] as RecordKind[]
                    ).map((k) => (
                      <button
                        key={k}
                        className={kind === k ? "selected" : ""}
                        onClick={() => setKind(k)}
                      >
                        <Icon name={kindIcons[k]} size={17} />
                        {t(k)}
                        <span>{counts(k)}</span>
                      </button>
                    ))}
                  </div>
                  {kind === "courses" && !!ws.course_catalog?.length && <div className="meaning-preview"><strong>{ws.course_catalog.length} {t("catalogueCourses")}</strong><p>{t("catalogueCoursesHelp")}</p></div>}
                  <section className="panel records-panel">
                    <div className="table-toolbar">
                      <div className="search-box">
                        <Icon name="search" size={17} />
                        <input
                          aria-label={t("searchRecords")}
                          placeholder={t("searchRecords")}
                          value={query}
                          onChange={(e) => setQuery(e.target.value)}
                        />
                        {query && (
                          <button
                            className="icon-btn"
                            aria-label={t("close")}
                            onClick={() => setQuery("")}
                          >
                            <Icon name="x" size={14} />
                          </button>
                        )}
                      </div>
                      {user.role === "administrator" && (
                        <button
                          className="btn white"
                          onClick={() => setImportOpen(true)}
                        >
                          <Icon name="book" size={16} />
                          {t("importCsv")}
                        </button>
                      )}
                      {kind === "courses" && user.role === "administrator" && <button className="btn white" onClick={() => setCourseSetupOpen(true)}><Icon name="sliders" size={16}/>{t("courseSetup")}</button>}
                      {kind === "groups" && user.role === "administrator" && <button className="btn white" onClick={() => setAdvisingOpen(true)}><Icon name="people" size={16}/>{lang === "ar" ? "طلاب الإرشاد" : "Advising students"}</button>}
                      <button
                        className="btn primary"
                        onClick={() => {
                          setModal({ type: "record" });
                          setError("");
                        }}
                      >
                        <Icon name="plus" size={17} />
                        {t("add")} {t(kind)}
                      </button>
                    </div>
                    {kind === "groups" ? (
                      <GroupHierarchy
                        groups={ws.records.filter(
                          (r) =>
                            r.kind === "groups" &&
                            `${r.name} ${r.code} ${r.year ?? ""} ${r.major ?? ""}`
                              .toLowerCase()
                              .includes(query.toLowerCase()),
                        )}
                        t={t}
                        administrator={user.role === "administrator"}
                        edit={(record) => {
                          setModal({ type: "record", record });
                          setError("");
                        }}
                        remove={(record) => {
                          setModal({ type: "delete", record });
                          setError("");
                        }}
                      />
                    ) : (
                      <div className="record-grid">
                        {ws.records
                          .filter(
                            (r) =>
                              r.kind === kind &&
                              `${r.name} ${r.code} ${r.year ?? ""} ${r.major ?? ""}`
                                .toLowerCase()
                                .includes(query.toLowerCase()),
                          )
                          .map((r) => (
                            <article className="record-card" key={r.id}>
                              <div className="record-top">
                                <span className={`record-icon ${kind}`}>
                                  <Icon name={kindIcons[kind]} size={23} />
                                </span>
                                <span className="record-code">{r.code}</span>
                              </div>
                              <h3>{r.name}</h3>
                              <p>
                                {kind === "instructors"
                                  ? `${r.department}${r.day_off ? ` · ${t("dayOff")}: ${t(r.day_off as Word)}` : ""}`
                                  : kind === "courses"
                                    ? `${t(r.activity_type as Word)} · ${r.sessions} × ${r.duration} ${t("minutes")}`
                                    : kind === "rooms"
                                      ? `${r.capacity == null ? t("capacityNotSet") : `${r.capacity} ${t("people")}`} · ${r.room_types?.length || r.room_type ? (r.room_types?.length ? r.room_types : [r.room_type]).map((type) => t(type as Word)).join(" / ") : t("roomTypeNotSet")}`
                                      : `${r.size} ${t("people")}`}
                              </p>
                              {kind === "rooms" && (r.reserved_majors?.length || r.reserved_course_ids?.length) ? (
                                <p className="room-reserved"><strong>{t("reservedFor")}:</strong>{" "}
                                  {[...(r.reserved_majors || []), ...(r.reserved_course_ids || []).map(id => ws?.course_catalog?.find(c => c.id === id)?.code || id)].join(", ")}</p>
                              ) : null}
                              {kind === "courses" && (
                                <div className="course-links">
                                  <Icon name="people" size={14} />
                                  {r.eligible_instructors?.length}{" "}
                                  {t("instructors")}
                                  <span>·</span>
                                  {r.group_ids?.length} {t("groups")}
                                </div>
                              )}
                              {kind === "instructors" && <p>{t("standardWeeklyHours")}: 12 · {t("extraAfter12")}</p>}
                              <div className="record-actions">
                                <button
                                  onClick={() => {
                                    setModal({ type: "record", record: r });
                                    setError("");
                                  }}
                                >
                                  <Icon name="edit" size={14} />
                                  {t("edit")}
                                </button>
                                <button
                                  aria-label={`${t("remove")} ${r.name}`}
                                  onClick={() => {
                                    setModal({ type: "delete", record: r });
                                    setError("");
                                  }}
                                >
                                  <Icon name="trash" size={14} />
                                </button>
                              </div>
                            </article>
                          ))}
                      </div>
                    )}
                    {!ws.records.some(
                      (r) =>
                        r.kind === kind &&
                        `${r.name} ${r.code} ${r.year ?? ""} ${r.major ?? ""}`
                          .toLowerCase()
                          .includes(query.toLowerCase()),
                    ) && (
                      <Empty
                        icon={kindIcons[kind]}
                        title={t(query ? "noresults" : "empty")}
                        text={t("emptysub")}
                      />
                    )}
                    <div className="table-footer">
                      <span>
                        {counts(kind)} {t("results")}
                      </span>
                      <span>
                        <span className="status-dot" />
                        {t("saved")}
                      </span>
                    </div>
                  </section>
                </>
              )}
              {page === "constraints" && (
                <>
                  <div className="constraint-toolbar">
                    <div className="tabs compact">
                      {["all", "pending", "approved"].map((f) => (
                        <button
                          key={f}
                          className={filter === f ? "selected" : ""}
                          onClick={() => setFilter(f)}
                        >
                          {t(f as Word)}
                          <span>
                            {f === "all"
                              ? ws.rules.length
                              : f === "pending"
                                ? pending
                                : approved}
                          </span>
                        </button>
                      ))}
                    </div>
                    <button
                      className="btn primary"
                      onClick={() => {
                        setModal({ type: "rule" });
                        setError("");
                      }}
                    >
                      <Icon name="plus" size={17} />
                      {t("newrule")}
                    </button>
                  </div>
                  <div className="subtle-banner">
                    <Icon name="sliders" size={16} />
                    <strong>{t("manual")}</strong>
                    <span>{t("ai")}</span>
                  </div>
                  {user.role === "administrator" && <TypedConstraint ws={ws} lang={lang} t={t} refresh={refresh}/>}
                  <AssignmentLocks ws={ws} lang={lang} administrator={user.role === "administrator"} refresh={refresh}/>
                  <div className="rules-grid">
                    {ws.rules
                      .filter(
                        (r) =>
                          filter === "all" ||
                          r.status ===
                            (filter === "pending" ? "draft" : "approved"),
                      )
                      .map((r) => (
                        <article className="panel rule-card" key={r.id}>
                          <div className="rule-top">
                            <span
                              className={`pill ${r.strength === "mandatory" ? "rose" : "lilac"}`}
                            >
                              <Icon
                                name={
                                  r.strength === "mandatory" ? "lock" : "spark"
                                }
                                size={12}
                              />
                              {t(r.strength)}
                            </span>
                            <span
                              className={`pill ${r.status === "approved" ? "green" : "amber"}`}
                            >
                              {t(r.status)}
                            </span>
                          </div>
                          <h3>{r.title}</h3>
                          <p className="rule-meaning">
                            {describeRule(r, ws.records, t).subject} <span>·</span> {t(r.type)}
                            <br />
                            <bdi>{describeRule(r, ws.records, t).detail}</bdi>
                          </p>
                          <p className="rule-caption">{t("approvalHelp")}</p>
                          <div className="rule-actions">
                            <button
                              className={`btn ${r.status === "approved" ? "white" : "primary"}`}
                              disabled={busy}
                              onClick={() =>
                                void mutate(
                                  `/rules/${r.id}/${r.status === "approved" ? "revoke" : "approve"}`,
                                  "POST",
                                  undefined,
                                  "approvedToast",
                                )
                              }
                            >
                              <Icon
                                name={
                                  r.status === "approved" ? "edit" : "check"
                                }
                                size={16}
                              />
                              {t(
                                r.status === "approved" ? "revoke" : "approve",
                              )}
                            </button>
                            {r.status === "draft" && (
                              <button
                                className="icon-btn danger"
                                aria-label={`${t("remove")} ${r.title}`}
                                onClick={() => {
                                  setModal({ type: "delete", rule: r });
                                  setError("");
                                }}
                              >
                                <Icon name="trash" size={16} />
                              </button>
                            )}
                          </div>
                        </article>
                      ))}
                  </div>
                  {ws.rules.filter(
                    (r) =>
                      filter === "all" ||
                      r.status ===
                        (filter === "pending" ? "draft" : "approved"),
                  ).length === 0 && (
                    <section className="panel">
                      <Empty
                        icon="sliders"
                        title={t("noRules")}
                        text={t("noRulesText")}
                      />
                    </section>
                  )}
                </>
              )}
              {page === "timetable" && user.role === "administrator" && <div className="schedule-mode"><button className={scheduleMode==="teaching"?"selected":""} onClick={()=>setScheduleMode("teaching")}>{lang==="ar"?"جدول التدريس":"Teaching timetable"}</button><button className={scheduleMode==="exams"?"selected":""} onClick={()=>setScheduleMode("exams")}>{lang==="ar"?"جدول الامتحانات":"Exam timetable"}</button></div>}
              {page === "timetable" && scheduleMode === "exams" && user.role === "administrator" && <ExamSchedule ws={ws} lang={lang}/>}
              {page === "timetable" && (scheduleMode === "teaching" || user.role !== "administrator") && (
                <Timetable
                  ws={ws}
                  lang={lang}
                  administrator={user.role === "administrator"}
                  refresh={refresh}
                />
              )}
              {page === "proposals" && user.role === "administrator" && <Proposals key={user.id} ws={ws} lang={lang} refresh={refresh}/>}
              {page === "evaluation" && user.role === "administrator" && <Evaluation key={user.id} lang={lang} reviewOwnerId={user.id} annotationStore={annotationStore}/>}
              {page === "accounts" && user.role === "administrator" && (
                <Accounts
                  user={user}
                  t={t}
                  lang={lang}
                  onSessionLost={clearSession}
                  onChanged={() => {
                    void refresh().catch(() => {});
                    void api<User>("/auth/me")
                      .then(setUser)
                      .catch(() => {});
                  }}
                />
              )}
              {page === "activity" && (
                <section className="panel activity-panel">
                  <EventList ws={ws} t={t} lang={lang} />
                </section>
              )}
            </>
          )}
        </main>
        <footer>
          <span>
            {BRAND.name} <i>✳</i> {t("tagline")}
          </span>
          <span>
            {t("version")} {ws?.version || "—"}
          </span>
        </footer>
      </div>
      {!modal &&
        !jaiOpen &&
        !accountOpen &&
        !calendarOpen &&
        !sessionExpired && (
          <button
            className="jai-launcher"
            onClick={() => setJaiOpen(true)}
            aria-haspopup="dialog"
          >
            <span className="jai-avatar" aria-hidden="true">
              J<span>✦</span>
            </span>
            <span>
              {t("askJai")}
              <small>{t("jaiRole")}</small>
            </span>
            <Icon name="spark" size={16} />
          </button>
        )}
      {jaiOpen && (
        <Modal title={BRAND.assistant} close={() => setJaiOpen(false)} t={t}>
          <div className="jai-intro">
            <span className="jai-avatar large" aria-hidden="true">
              J<span>✦</span>
            </span>
            <div>
              <div className="eyebrow">{t("jaiRole")}</div>
              <h3>{t("jaiGreeting")}</h3>
              <p>{t("jaiIntro")}</p>
            </div>
          </div>
          <div className="jai-status">
            <Icon name="spark" size={15} />
            {t("jaiStatus")}
          </div>
          <div className="jai-actions">
            <button
              onClick={() => {
                setJaiOpen(false);
                navigate("data");
              }}
            >
              <Icon name="book" />
              <span>
                {t("jaiData")}
                <small>{t("jaiDataHelp")}</small>
              </span>
              <Icon name="arrow" size={16} />
            </button>
            <button
              onClick={() => {
                setJaiOpen(false);
                setPage("constraints");
                setModal({ type: "rule" });
                setError("");
              }}
            >
              <Icon name="sliders" />
              <span>
                {t("jaiRule")}
                <small>{t("jaiRuleHelp")}</small>
              </span>
              <Icon name="arrow" size={16} />
            </button>
            <button
              onClick={() => {
                setJaiOpen(false);
                navigate("timetable");
              }}
            >
              <Icon name="calendar" />
              <span>
                {t("jaiSchedule")}
                <small>{t("jaiScheduleHelp")}</small>
              </span>
              <Icon name="arrow" size={16} />
            </button>
          </div>
          <p className="jai-signoff">{t("jaiSignoff")}</p>
        </Modal>
      )}
      {importOpen && (
        <ImportData
          kind={kind}
          t={t}
          lang={lang}
          close={() => setImportOpen(false)}
          onImported={async () => {
            await refresh();
            setToast(t("importComplete"));
          }}
        />
      )}
      {calendarOpen && ws && (
        <Modal
          title={t("semesterSettings")}
          close={() => {
            if (!busy) setCalendarOpen(false);
          }}
          t={t}
        >
          <CalendarSettings
            ws={ws}
            t={t}
            lang={lang}
            busy={busy}
            save={async (body) => {
              setBusy(true);
              try {
                await api("/workspace", "PUT", body, ws.version);
                await refresh();
                setCalendarOpen(false);
                setToast(t("changesSaved"));
              } catch (e) {
                if (e instanceof ApiError && e.status === 409) await refresh();
                throw e;
              } finally {
                setBusy(false);
              }
            }}
          />
        </Modal>
      )}
      {accountOpen && (
        <Modal title={t("myAccount")} close={() => setAccountOpen(false)} t={t}>
          <MyAccount user={user} t={t} lang={lang} onSignedOut={clearSession} />
        </Modal>
      )}
      {toast && (
        <div className="toast" role="status">
          <Icon name="check" size={18} />
          {toast}
        </div>
      )}
      {courseSetupOpen && ws && <CourseSetup ws={ws} t={t} close={() => setCourseSetupOpen(false)} saved={refresh} />}
      {advisingOpen && ws && <AdvisingStudents ws={ws} lang={lang} t={t} close={() => setAdvisingOpen(false)} saved={refresh} />}
      {modal && (
        <Modal
          title={
            modal.type === "delete"
              ? t("confirmDelete")
              : modal.type === "rule"
                ? t("newrule")
                : `${t(modal.record ? "edit" : "add")} · ${t(kind)}`
          }
          close={() => {
            if (!busy) {
              setModal(null);
              setError("");
            }
          }}
          t={t}
        >
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          {modal.type === "record" && ws && (
            <RecordForm
              kind={kind}
              record={modal.record}
              ws={ws}
              t={t}
              busy={busy}
              cancel={() => setModal(null)}
              submit={(body) =>
                void mutate(
                  `/records/${kind}${modal.record ? `/${modal.record.id}` : ""}`,
                  modal.record ? "PUT" : "POST",
                  body,
                )
              }
            />
          )}
          {modal.type === "rule" && ws && (
            <RuleForm
              ws={ws}
              t={t}
              busy={busy}
              cancel={() => setModal(null)}
              submit={(body) =>
                void mutate("/rules", "POST", body, "ruleSaved")
              }
            />
          )}
          {modal.type === "delete" && (
            <>
              <p className="modal-description">{t("deleteText")}</p>
              <div className="delete-target">
                {modal.record?.name || modal.rule?.title}
              </div>
              <div className="form-actions">
                <button
                  className="btn white"
                  disabled={busy}
                  onClick={() => setModal(null)}
                >
                  {t("cancel")}
                </button>
                <button
                  className="btn destructive"
                  disabled={busy}
                  onClick={() =>
                    void mutate(
                      modal.rule
                        ? `/rules/${modal.rule.id}`
                        : `/records/${kind}/${modal.record?.id}`,
                      "DELETE",
                      undefined,
                      "removedToast",
                    )
                  }
                >
                  {busy ? t("working") : t("confirm")}
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
      {sessionExpired && (
        <Modal
          title={t("sessionExpiredTitle")}
          close={() => {}}
          dismissible={false}
          t={t}
        >
          <p className="modal-description">{t("sessionExpiredHelp")}</p>
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              setBusy(true);
              setError("");
              try {
                const identity = await api<User>("/auth/login", "POST", {
                  email: user.email,
                  password: f.get("password"),
                });
                setUser(identity);
                await refresh();
                setSessionExpired(false);
                setToast(t("reviewAfterSignin"));
              } catch (e) {
                setError(message(e));
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              {t("email")}
              <input value={user.email} readOnly type="email" />
            </label>
            <label>
              {t("password")}
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={200}
              />
            </label>
            <div className="form-actions">
              <button
                type="button"
                className="btn white"
                disabled={busy}
                onClick={clearSession}
              >
                {t("discardAndSignout")}
              </button>
              <button className="btn primary" disabled={busy}>
                {t(busy ? "working" : "signinButton")}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
