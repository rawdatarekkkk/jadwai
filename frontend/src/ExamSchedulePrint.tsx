import type {CSSProperties} from "react";
import type {Exam, Run} from "./ExamSchedule";

const facultyOrder = ["ENGINEERING", "INFORMATICS", "BUSINESS INFORMATICS", "BUSINESS ADMINISTRATION", "PHE/BIO", "PHYSICAL THERAPY"];
const palette = ["#b6dde3", "#c7eac2", "#c9bcd7", "#fbd79e", "#b9cde3", "#f3c5c5", "#c9e7e1", "#f5e89f"];
function colorFor(program: string) {
  let hash = 0;
  for (const c of program) hash = (hash * 31 + c.charCodeAt(0)) | 0;
  return palette[Math.abs(hash) % palette.length];
}

export function ExamSchedulePrint({run, assignments, lang, query, stale}: {
  run: Run; assignments: Exam[]; lang: "en" | "ar"; query: string; stale: boolean;
}) {
  const ar = lang === "ar";
  const days = [...new Set(assignments.map(a => a.date))].sort();
  return <section className="schedule-print exam-schedule-print" dir={ar ? "rtl" : "ltr"} lang={lang} aria-label={ar ? "جدول الامتحانات للطباعة" : "Printable exam schedule"}>
    {days.length === 0 && <p>{ar ? "لا توجد امتحانات مطابقة للبحث." : "No exams match this search."}</p>}
    {days.map(day => {
      const exams = assignments.filter(a => a.date === day);
      const faculties = [...new Set(exams.flatMap(a => a.programs.length ? a.programs.map(p => p.faculty_section) : ["OTHER"]))].sort((a,b) => {
        const ai=facultyOrder.indexOf(a), bi=facultyOrder.indexOf(b);
        return (ai<0?99:ai)-(bi<0?99:bi)||a.localeCompare(b);
      });
      const sections = faculties.map(faculty => ({faculty, slots: ["09:00", "11:15", "13:30"].map(time => exams.filter(a => a.start_time === time).flatMap(a => {
        const programs = a.programs.filter(p => p.faculty_section === faculty);
        return programs.length ? programs.map(p => ({exam:a, program:p.program_or_cohort || faculty, semester:p.semester})) : faculty === "OTHER" && !a.programs.length ? [{exam:a, program:"", semester:null}] : [];
      }))}));
      const rowCount = sections.reduce((n,s) => n + 1 + Math.max(...s.slots.map(s => s.length)),0);
      return <section className="exam-print-day" key={day} style={{"--exam-font": rowCount > 28 ? "5.5pt" : rowCount > 20 ? "6pt" : "7pt"} as CSSProperties}>
        <header><img src="/giu-schedule-logo.png" alt="German International University"/><h1>{ar ? "جدول امتحانات منتصف الفصل" : `${day.slice(0,4)} Mid Term Exams Schedule`} <span>({ar ? "مسودة" : "DRAFT"})</span></h1></header>
        <table><thead><tr><th className="exam-date-heading"/><th>9:00-11:00</th><th>11:15-13:15</th><th>13:30-15:30</th></tr></thead><tbody>
          {sections.flatMap((section, si) => [
            <tr key={`${section.faculty}-heading`}>
              {si===0 && <th rowSpan={rowCount} className="exam-print-date"><span>{new Intl.DateTimeFormat(ar ? "ar-EG" : "en-US", {weekday:"long",month:"long",day:"numeric",year:"numeric",timeZone:"UTC"}).format(new Date(day+"T12:00:00Z"))}</span></th>}
              <th colSpan={3} className="exam-faculty">{section.faculty}</th>
            </tr>,
            ...Array.from({length:Math.max(...section.slots.map(s => s.length))}, (_,i) => <tr key={`${section.faculty}-${i}`}>{section.slots.map((slot,j) => {
              const entry=slot[i];
              return <td key={j} style={entry ? {backgroundColor:colorFor(entry.program)} : undefined}>{entry && <>{entry.program && <span>GIU-Cairo.{entry.program} {entry.semester !== null ? `${entry.semester}${ar ? "" : " Semester"}` : ""} - </span>}<strong>{entry.exam.course_name}</strong> <bdi>{entry.exam.course_code}</bdi></>}</td>;
            })}</tr>)
          ])}
        </tbody></table>
        <footer>{assignments.some(a => a.halls?.length)
          ? <b>{ar ? "القاعات والمراقبون كما في هذه المسودة." : "Halls and invigilators as assigned in this draft."}</b>
          : <><b>{ar ? "مسودة تواريخ وأوقات فقط." : "Draft: dates and times only."}</b> {ar ? "القاعات والمراقبون غير مشمولين." : "Rooms and invigilators are not covered."}</>}<br/>{stale && <b>{ar ? "تغيرت المدخلات. " : "Inputs have changed. "}</b>}{query && <span>{ar ? "البحث" : "Filter"}: {query} · </span>}{ar ? "إصدار المدخلات" : "Input version"}: {run.input_version} · {run.id.slice(0,8)}</footer>
      </section>;
    })}
  </section>;
}
