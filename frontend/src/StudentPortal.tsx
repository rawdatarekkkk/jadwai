import { useEffect, useState } from "react";
import { api, type User, type DataRecord, type ScheduleRun } from "./api";
import { ScheduleGrid } from "./ScheduleGrid";
import { MyAccount } from "./Accounts";
import { Icon, Modal } from "./components";
import { words, type Word } from "./i18n";
export function StudentPortal({user, lang, setLang, onSignedOut}: {user: User; lang: "en" | "ar"; setLang: (v: "en" | "ar") => void; onSignedOut: () => void}) {
  const [data, setData] = useState<{group: DataRecord | null; run: ScheduleRun | null} | null>(null);
  const [error, setError] = useState(false), [busy, setBusy] = useState(false), [account, setAccount] = useState(false);
  const ar = lang === "ar", t = (key: Word) => words[lang][key];
  async function load() { setBusy(true); setError(false); try { setData(await api("/student/schedule")); } catch { setError(true); } finally { setBusy(false); } }
  useEffect(() => { void load(); }, [user.id, user.group_id]);
  return <div className="student-portal">
    <header className="student-header"><a className="student-brand" href="/">JadwAI ✳</a><div className="student-tools"><button className="btn white" onClick={() => setLang(ar ? "en" : "ar")}>{ar ? "English" : "العربية"}</button><button className="btn white" onClick={() => setAccount(true)}>{user.name}</button><button className="btn white" onClick={() => void api("/auth/logout", "POST").then(onSignedOut).catch(() => setError(true))}>{t("signout")}</button></div></header>
    <main className="student-content"><div className="eyebrow">{ar ? "بوابة الطالب" : "STUDENT PORTAL"}</div><h1>{ar ? "جدولك، في مكان واحد." : "Your week, beautifully arranged."}</h1><p>{ar ? `مرحباً ${user.name} — هذا جدول مجموعتك.` : `Welcome, ${user.name}. Here’s your group’s weekly timetable.`}</p>
    <section className="panel student-timetable"><div className="student-summary"><div><h2>{ar ? "جدولي" : "My schedule"}</h2><p>{data?.group ? [data.group.year && !data.group.name.toLowerCase().startsWith(`year ${data.group.year}`) && `${ar ? "السنة" : "Year"} ${data.group.year}`, data.group.major, data.group.name].filter(Boolean).join(" · ") : ar ? "لم يتم تعيين مجموعة" : "No group assigned"}</p>{data?.run && <small>{data.run.snapshot.term} · {data.run.snapshot.calendar.timezone}</small>}</div><button className="btn white" disabled={busy} onClick={() => void load()}>{busy ? t("working") : ar ? "تحديث" : "Refresh"}</button></div>
    {error && <div className="error" role="alert">{ar ? "تعذر تحميل الجدول. حاول مجدداً." : "Couldn’t load your schedule. Try refreshing or signing in again."}<button onClick={onSignedOut}>{ar ? "تسجيل الدخول" : "Sign in"}</button></div>}
    {data?.run ? <><div className="subtle-banner">{ar ? "مسودة تم التحقق منها — لم يتم نشر الجدول النهائي بعد." : "Validated draft — the final timetable has not been published yet."}</div>{data.run.stale && <div className="error" role="status">{ar ? "تغيرت المدخلات منذ إنشاء هذا الجدول. تحقق مع الإدارة." : "Inputs have changed since this schedule was generated. Check with your administrator for an updated timetable."}</div>}<div className="student-grid-scroll"><ScheduleGrid run={data.run} assignments={data.run.result?.assignments || []} lang={lang}/></div>{!data.run.result?.assignments.length && <p>{ar ? "لا توجد محاضرات لهذه المجموعة." : "Your group has no sessions in this timetable."}</p>}</> : !busy && !error && <div className="student-empty"><Icon name="calendar" size={36}/><h3>{ar ? "جدولك قريباً" : "Your schedule is on its way"}</h3><p>{ar ? "ستظهر هنا محاضرات مجموعتك بعد إنشاء جدول صالح." : "Your group’s sessions will appear here once a valid timetable is generated."}</p></div>}
    </section></main>{account && <Modal title={t("myAccount")} close={() => setAccount(false)} t={t}><MyAccount user={user} t={t} lang={lang} onSignedOut={onSignedOut}/></Modal>}
  </div>;
}
