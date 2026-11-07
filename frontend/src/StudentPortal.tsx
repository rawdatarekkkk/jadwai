import { useEffect, useState } from "react";
import { api, type User, type DataRecord, type ScheduleRun } from "./api";
import { ScheduleGrid } from "./ScheduleGrid";
import { MyAccount } from "./Accounts";
import { Icon, Modal } from "./components";
import { words, type Word } from "./i18n";

type Exam = { course_code: string; course_name: string; date: string; start_time: string; end_time: string; halls: string[]; role: "student" | "invigilator" | "course" };
type Personal = { group?: DataRecord | null; instructor?: DataRecord | null; run: ScheduleRun | null; exams: Exam[] };

/** Read-only personal timetable for students (their group) and instructors (their sessions and invigilation). */
export function StudentPortal({user, lang, setLang, onSignedOut}: {user: User; lang: "en" | "ar"; setLang: (v: "en" | "ar") => void; onSignedOut: () => void}) {
  const [data, setData] = useState<Personal | null>(null);
  const [error, setError] = useState(false), [busy, setBusy] = useState(false), [account, setAccount] = useState(false);
  const ar = lang === "ar", t = (key: Word) => words[lang][key];
  const teacher = user.role === "instructor";
  async function load() { setBusy(true); setError(false); try { setData(await api("/me/schedule")); } catch { setError(true); } finally { setBusy(false); } }
  useEffect(() => { void load(); }, [user.id, user.group_id, user.instructor_id]);
  const who = teacher ? (data?.instructor ? [data.instructor.name, data.instructor.position && t(data.instructor.position)].filter(Boolean).join(" · ") : ar ? "لم يتم ربط مدرس" : "No instructor linked")
    : data?.group ? [data.group.year && !data.group.name.toLowerCase().startsWith(`year ${data.group.year}`) && `${ar ? "السنة" : "Year"} ${data.group.year}`, data.group.major, data.group.name].filter(Boolean).join(" · ") : ar ? "لم يتم تعيين مجموعة" : "No group assigned";
  return <div className="student-portal">
    <header className="student-header"><a className="student-brand" href="/">JadwAI ✳</a><div className="student-tools"><button className="btn white" onClick={() => setLang(ar ? "en" : "ar")}>{ar ? "English" : "العربية"}</button><button className="btn white" onClick={() => setAccount(true)}>{user.name}</button><button className="btn white" onClick={() => void api("/auth/logout", "POST").then(onSignedOut).catch(() => setError(true))}>{t("signout")}</button></div></header>
    <main className="student-content"><div className="eyebrow">{teacher ? (ar ? "بوابة المدرس" : "INSTRUCTOR PORTAL") : (ar ? "بوابة الطالب" : "STUDENT PORTAL")}</div><h1>{ar ? "جدولك، في مكان واحد." : "Your week, beautifully arranged."}</h1><p>{ar ? `مرحباً ${user.name} — هذا جدولك المنشور.` : `Welcome, ${user.name}. Here’s your published timetable.`}</p>
    <section className="panel student-timetable"><div className="student-summary"><div><h2>{t("myTimetable")}</h2><p>{who}</p>{data?.run && <small>{data.run.snapshot.term} · {data.run.snapshot.calendar.timezone}</small>}</div><div className="student-tools">{(data?.run || data?.exams.length) && <a className="btn white" href="/api/me/schedule.csv" download><Icon name="arrow" size={16}/>{t("exportCsv")}</a>}<button className="btn white" disabled={busy} onClick={() => void load()}>{busy ? t("working") : ar ? "تحديث" : "Refresh"}</button></div></div>
    {error && <div className="error" role="alert">{ar ? "تعذر تحميل الجدول. حاول مجدداً." : "Couldn’t load your schedule. Try refreshing or signing in again."}<button onClick={onSignedOut}>{ar ? "تسجيل الدخول" : "Sign in"}</button></div>}
    {data?.run ? <>{data.run.stale && <div className="error" role="status">{ar ? "تغيرت المدخلات منذ نشر هذا الجدول. تحقق مع الإدارة." : "Inputs have changed since this timetable was published. Check with your administrator for an update."}</div>}<div className="student-grid-scroll"><ScheduleGrid run={data.run} assignments={data.run.result?.assignments || []} lang={lang}/></div>{!data.run.result?.assignments.length && <p>{ar ? "لا توجد حصص لك في هذا الجدول." : "You have no sessions in this timetable."}</p>}</> : !busy && !error && <div className="student-empty"><Icon name="calendar" size={36}/><h3>{ar ? "جدولك قريباً" : "Your schedule is on its way"}</h3><p>{t("notPublished")}</p></div>}
    </section>
    {!!data?.exams.length && <section className="panel"><h2>{teacher ? (ar ? "الامتحانات" : "Exams") : t("myExams")}</h2><table className="source-timetable-table"><thead><tr><th>{ar ? "التاريخ" : "Date"}</th><th>{ar ? "الوقت" : "Time"}</th><th>{ar ? "المقرر" : "Course"}</th><th>{t("examHalls")}</th>{teacher && <th>{ar ? "الدور" : "Role"}</th>}</tr></thead><tbody>
      {data.exams.map(e => <tr key={`${e.course_code}-${e.date}-${e.role}`}><td><bdi>{e.date}</bdi></td><td><bdi>{e.start_time}–{e.end_time}</bdi></td><td>{e.course_name} · {e.course_code}</td><td>{e.halls.join(", ")}</td>{teacher && <td>{e.role === "invigilator" ? t("invigilation") : ar ? "امتحان مقررك" : "Your course"}</td>}</tr>)}
    </tbody></table></section>}
    </main>{account && <Modal title={t("myAccount")} close={() => setAccount(false)} t={t}><MyAccount user={user} t={t} lang={lang} onSignedOut={onSignedOut}/></Modal>}
  </div>;
}
