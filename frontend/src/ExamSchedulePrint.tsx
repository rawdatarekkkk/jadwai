import { examLabel, kindTitle, type Exam, type Run } from "./ExamSchedule";

const palette = ["#b6dde3", "#c7eac2", "#c9bcd7", "#fbd79e", "#b9cde3", "#f3c5c5", "#c9e7e1", "#f5e89f"];
function colorFor(program: string) {
  let hash = 0;
  for (const c of program) hash = (hash * 31 + c.charCodeAt(0)) | 0;
  return palette[Math.abs(hash) % palette.length];
}

/** Printable exam timetable: one page per exam day, exams in time order. */
export function ExamSchedulePrint({run, assignments, lang, query, stale}: {
  run: Run; assignments: Exam[]; lang: "en" | "ar"; query: string; stale: boolean;
}) {
  const ar = lang === "ar";
  const days = [...new Set(assignments.map(a => a.date))].sort();
  const title = kindTitle(run.result.assignments);
  return <section className="schedule-print exam-schedule-print" dir={ar ? "rtl" : "ltr"} lang={lang} aria-label={ar ? "جدول الامتحانات للطباعة" : "Printable exam schedule"}>
    {days.length === 0 && <p>{ar ? "لا توجد امتحانات مطابقة للبحث." : "No exams match this search."}</p>}
    {days.map(day => {
      const exams = assignments.filter(a => a.date === day).sort((a, b) => a.start_time.localeCompare(b.start_time) || a.course_code.localeCompare(b.course_code));
      return <section className="exam-print-day" key={day}>
        <header><img src="/giu-schedule-logo.png" alt="German International University"/><h1>{ar ? "جدول الامتحانات" : `${day.slice(0,4)} ${title} Schedule`} <span>({run.published_at ? (ar ? "منشور" : "Published") : (ar ? "مسودة" : "DRAFT")})</span>
          <small>{new Intl.DateTimeFormat(ar ? "ar-EG" : "en-US", {weekday:"long",month:"long",day:"numeric",year:"numeric",timeZone:"UTC"}).format(new Date(day+"T12:00:00Z"))}</small></h1></header>
        <table><thead><tr><th>{ar ? "الوقت" : "Time"}</th><th>{ar ? "الامتحان" : "Exam"}</th><th>{ar ? "المقرر" : "Course"}</th>{exams.some(a => a.programs.length) && <th>{ar ? "البرامج" : "Programmes"}</th>}<th>{ar ? "الطلاب والقاعات" : "Students and halls"}</th></tr></thead><tbody>
          {exams.map(a => {
            const programs = [...new Set(a.programs.map(p => `${p.program_or_cohort || p.faculty_section} ${p.semester ?? ""}`.trim()))];
            return <tr key={a.exam_id || a.course_id}>
              <td><b>{a.start_time}–{a.end_time}</b></td>
              <td>{examLabel(a, ar)}</td>
              <td><strong>{a.course_name}</strong> <bdi>{a.course_code}</bdi></td>
              {exams.some(x => x.programs.length) && <td style={programs.length ? {backgroundColor: colorFor(a.programs[0].program_or_cohort || a.programs[0].faculty_section)} : undefined}>{programs.join(", ")}</td>}
              <td>{a.students ? `${a.students} ${ar ? "طالباً" : "students"}` : ""}{a.halls?.length ? ` · ${a.halls.map(h => h.room_code + (h.invigilator_name ? ` (${h.invigilator_name})` : "")).join(", ")}` : ""}</td>
            </tr>;
          })}
        </tbody></table>
        <footer>{assignments.some(a => a.halls?.length)
          ? <b>{ar ? "القاعات والمراقبون كما في هذه المسودة." : "Halls and invigilators as assigned in this draft."}</b>
          : <><b>{ar ? "مسودة تواريخ وأوقات فقط." : "Draft: dates and times only."}</b> {ar ? "القاعات والمراقبون غير مشمولين." : "Rooms and invigilators are not covered."}</>}<br/>{stale && <b>{ar ? "تغيرت المدخلات. " : "Inputs have changed. "}</b>}{query && <span>{ar ? "البحث" : "Filter"}: {query} · </span>}{ar ? "إصدار المدخلات" : "Input version"}: {run.input_version} · {run.id.slice(0,8)}</footer>
      </section>;
    })}
  </section>;
}
