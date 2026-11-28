import { useState } from "react";
import type { CatalogCourse, Workspace } from "./api";

export type ExamKind = "quiz" | "midterm" | "final";
export type ExamPlan = {
  kind: ExamKind;
  quizNumber: number;
  quizMinutes: number;
  starts: Partial<Record<"quiz" | "midterm" | "makeup" | "final", string[]>>;
  skip: string[];
  makeupStudents: Record<string, number>;
};
export const DEFAULT_STARTS = { final: ["11:30", "15:00"], makeup: ["09:00"], midterm: ["09:00", "11:15", "13:30"], quiz: ["09:00", "10:15", "11:30", "13:00", "14:15"] };
export const DEFAULT_PLAN: ExamPlan = { kind: "midterm", quizNumber: 1, quizMinutes: 30, starts: {}, skip: [], makeupStudents: {} };
const TYPES_OF: Record<ExamKind, ("quiz" | "midterm" | "makeup" | "final")[]> = { quiz: ["quiz"], midterm: ["midterm"], final: ["final", "makeup"] };

/** The exams a timetable will hold, from each course's plan: [exam key, label, course]. */
export function plannedExams(plan: ExamPlan, courses: CatalogCourse[]) {
  const out: { key: string; type: "quiz" | "midterm" | "makeup" | "final"; course: CatalogCourse }[] = [];
  for (const c of courses) {
    if (plan.kind === "quiz" && (c.quiz_count ?? 3) >= plan.quizNumber) out.push({ key: `${c.id}:quiz${plan.quizNumber}`, type: "quiz", course: c });
    if (plan.kind === "midterm") out.push({ key: `${c.id}:midterm`, type: "midterm", course: c });
    if (plan.kind === "final") {
      out.push({ key: `${c.id}:final`, type: "final", course: c });
      if (c.second_chance ?? true) out.push({ key: `${c.id}:makeup`, type: "makeup", course: c });
    }
  }
  return out;
}

/** Seminars, capstones, theses, internships and projects usually have no quizzes: they start unticked (tick them if they do). */
export const NO_QUIZ = /\b(seminar|capstone|thesis|internship|bachelor project|graduation project)\b/i;
export function noQuizKeys(courses: CatalogCourse[], n: number) {
  return courses.filter(c => NO_QUIZ.test(c.name)).map(c => `${c.id}:quiz${n}`);
}

/** Second-chance midterms start unticked: the admin adds the courses that need one. */
export function makeupKeys(courses: CatalogCourse[]) {
  return courses.filter(c => c.second_chance ?? true).map(c => `${c.id}:makeup`);
}

export function examPlanBody(p: ExamPlan) {
  return { kind: p.kind, quiz_number: p.quizNumber, quiz_minutes: p.quizMinutes, starts: p.starts, skip: p.skip, makeup_students: p.makeupStudents };
}

/** Create an exam timetable: choose what it is for, then which courses' exams it holds. */
export function ExamPlanSetup({ ws, ar, value, change }: { ws: Workspace; ar: boolean; value: ExamPlan; change: (v: ExamPlan) => void }) {
  const [search, setSearch] = useState("");
  const say = (en: string, arText: string) => (ar ? arText : en);
  const courses = ws.course_catalog || [];
  const maxQuizzes = Math.max(1, ...courses.map(c => c.quiz_count ?? 3));
  const exams = plannedExams(value, courses);
  const shown = exams.filter(x => `${x.course.code} ${x.course.name}`.toLowerCase().includes(search.toLowerCase()));
  const on = (key: string) => !value.skip.includes(key);
  const setOn = (keys: string[], yes: boolean) => change({ ...value, skip: yes ? value.skip.filter(k => !keys.includes(k)) : [...new Set([...value.skip, ...keys])] });
  const chosen = exams.filter(x => on(x.key));
  const label = (t: string) => ({ quiz: say(`Quiz ${value.quizNumber}`, `اختبار قصير ${value.quizNumber}`), midterm: say("Midterm", "منتصف الفصل"), final: say("Final", "نهائي"), makeup: say("Second-chance midterm", "فرصة ثانية لمنتصف الفصل") } as Record<string, string>)[t];
  const length = (t: string) => (t === "quiz" ? value.quizMinutes : t === "final" ? 180 : 120);
  const byCourse = new Map<string, typeof shown>();
  for (const x of shown) byCourse.set(x.course.id, [...(byCourse.get(x.course.id) || []), x]);
  const kinds: [ExamKind, string, string][] = [
    ["quiz", say("Quizzes", "اختبارات قصيرة"), say("One quiz round, 15–60 minutes", "جولة اختبار قصير، 15–60 دقيقة")],
    ["midterm", say("Midterms", "منتصف الفصل"), say("Each course's midterm, 2 hours", "امتحان منتصف الفصل لكل مقرر، ساعتان")],
    ["final", say("Finals", "النهائي"), say("Finals (3 h) and second-chance midterms (2 h) in the first slot", "النهائي (3 ساعات) والفرصة الثانية (ساعتان) في أول فترة")],
  ];
  return (
    <div className="exam-plan-setup">
      <fieldset className="exam-kind-choice">
        <legend>{say("What is this timetable for?", "لماذا هذا الجدول؟")}</legend>
        {kinds.map(([k, title, help]) => (
          <label key={k} className={`exam-kind ${value.kind === k ? "selected" : ""}`}>
            <input type="radio" name="exam_kind" value={k} checked={value.kind === k} onChange={() => change({ ...value, kind: k, skip: k === "final" ? makeupKeys(courses) : k === "quiz" ? noQuizKeys(courses, value.quizNumber) : [] })} />
            <strong>{title}</strong><small>{help}</small>
          </label>
        ))}
      </fieldset>
      {value.kind === "quiz" && (
        <div className="exam-settings">
          <label>{say("Which quiz", "أي اختبار")}<select value={value.quizNumber} onChange={e => change({ ...value, quizNumber: Number(e.target.value), skip: noQuizKeys(courses, Number(e.target.value)) })}>
            {Array.from({ length: maxQuizzes }, (_, i) => <option key={i} value={i + 1}>{say(`Quiz ${i + 1}`, `اختبار قصير ${i + 1}`)}</option>)}
          </select></label>
          <label>{say("Length", "المدة")}<select value={value.quizMinutes} onChange={e => change({ ...value, quizMinutes: Number(e.target.value) })}>
            {[15, 30, 45, 60].map(m => <option key={m} value={m}>{m} {say("minutes", "دقيقة")}</option>)}
          </select></label>
        </div>
      )}
      <section className="exam-plan-courses">
        <div className="exam-plan-toolbar">
          <strong>{say(`${chosen.length} exams`, `${chosen.length} امتحان`)}</strong>
          <span>{(["quiz", "midterm", "final", "makeup"] as const).map(t => { const n = chosen.filter(x => x.type === t).length; return n ? `${n} × ${label(t)}` : ""; }).filter(Boolean).join(" · ")}</span>
          <input type="search" aria-label={say("Search courses", "ابحث عن مقرر")} placeholder={say("Search courses…", "ابحث عن مقرر…")} value={search} onChange={e => setSearch(e.target.value)} />
          {(value.kind === "final" ? (["final", "makeup"] as const) : [null]).map(t => {
            const keys = shown.filter(x => !t || x.type === t).map(x => x.key);
            const what = t === "final" ? say(" finals", " النهائي") : t === "makeup" ? say(" second chances", " الفرص الثانية") : "";
            return <span key={t ?? "all"} className="exam-plan-tick">
              <button type="button" className="btn white" disabled={!keys.length} onClick={() => setOn(keys, true)}>{say(`Tick all${what}`, `تحديد كل${what || " المعروض"}`)}</button>
              <button type="button" className="btn white" disabled={!keys.length} onClick={() => setOn(keys, false)}>{say(`Untick all${what}`, `إلغاء كل${what || " المعروض"}`)}</button>
            </span>;
          })}
        </div>
        <div className="exam-plan-list">
          {[...byCourse.entries()].map(([id, rows]) => (
            <div className="exam-plan-row" key={id}>
              <span><b>{rows[0].course.code}</b> {rows[0].course.name}</span>
              {rows.map(x => (
                <label key={x.key} className="check-label">
                  <input type="checkbox" checked={on(x.key)} onChange={e => setOn([x.key], e.target.checked)} />
                  {label(x.type)}
                  {x.type === "makeup" && on(x.key) && <input className="makeup-students" type="number" min={1} max={5000} aria-label={say("Students expected", "الطلاب المتوقعون")}
                    placeholder={say("students", "طلاب")} value={value.makeupStudents[id] ?? ""} onChange={e => {
                      const next = { ...value.makeupStudents }; const n = Number(e.target.value);
                      if (n >= 1) next[id] = n; else delete next[id];
                      change({ ...value, makeupStudents: next });
                    }} />}
                </label>
              ))}
            </div>
          ))}
          {!exams.length && <p className="room-type-help">{say("No course has this exam. Check the quiz count in Course setup.", "لا يوجد مقرر بهذا الامتحان. راجع عدد الاختبارات في إعداد المقررات.")}</p>}
        </div>
        {value.kind === "quiz" && <p className="room-type-help">{say("Seminars, capstones, theses, internships and projects start unticked because they usually have no quizzes. Tick any that do.", "الندوات ومشروعات التخرج والرسائل والتدريب العملي غير محددة في البداية لأنها عادةً بلا اختبارات قصيرة. حدد ما له اختبار منها.")}</p>}
        {value.kind === "final" && <p className="room-type-help">{say("Second-chance midterms start unticked: tick the courses that need one. They seat the students who missed the midterm; leave the number empty to use 10% of the course.", "الفرص الثانية غير محددة في البداية: حدد المقررات التي تحتاجها. هي لمن فاتهم امتحان منتصف الفصل؛ اترك العدد فارغًا لاستخدام 10% من طلاب المقرر.")}</p>}
      </section>
      <details className="exam-times">
        <summary>{say("Change exam times", "تغيير مواعيد الامتحانات")}</summary>
        <p className="room-type-help">{value.kind === "final"
          ? say("The first slot of each day is for second-chance midterms; finals start after it.", "أول فترة في كل يوم للفرصة الثانية؛ يبدأ النهائي بعدها.")
          : say("Each exam starts at one of these times and lasts its own length.", "يبدأ كل امتحان في أحد هذه المواعيد ويستمر مدته.")}</p>
        {TYPES_OF[value.kind].map(t => {
          const times = value.starts[t] ?? DEFAULT_STARTS[t];
          const set = (next: string[]) => change({ ...value, starts: { ...value.starts, [t]: [...new Set(next)].sort() } });
          return (
            <div key={t} className="exam-times-row">
              <strong>{label(t)} · {length(t) >= 60 ? `${length(t) / 60} h` : `${length(t)} min`}</strong>
              {times.map(time => <span key={time} className="exam-time-chip">{time}–{(() => { const [h, m] = time.split(":").map(Number); const e = h * 60 + m + length(t); return `${String(Math.floor(e / 60)).padStart(2, "0")}:${String(e % 60).padStart(2, "0")}`; })()}
                <button type="button" aria-label={say(`Remove ${time}`, `حذف ${time}`)} disabled={times.length <= 1} onClick={() => set(times.filter(x => x !== time))}>×</button></span>)}
              <input type="time" step={900} aria-label={say(`Add a start time for ${label(t)}`, `أضف موعدًا`)} onChange={e => { if (e.target.value) { set([...times, e.target.value]); e.target.value = ""; } }} />
            </div>
          );
        })}
      </details>
    </div>
  );
}
