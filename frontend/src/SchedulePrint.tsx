import type { ScheduleAssignment, ScheduleRun } from "./api";
import { ScheduleGrid } from "./ScheduleGrid";

export function SchedulePrint({
  run,
  assignments,
  lang,
  scope,
  stale,
}: {
  run: ScheduleRun;
  assignments: ScheduleAssignment[];
  lang: "en" | "ar";
  scope: string;
  stale: boolean;
}) {
  const ar = lang === "ar";
  const record = (id: string) => run.snapshot.records.find((r) => r.id === id);
  const group = (id: string) => {
    const g = record(id);
    return [
      g?.year ? `${ar ? "السنة" : "Year"} ${g.year}` : "",
      g?.major,
      g?.name,
    ]
      .filter(Boolean)
      .join(" / ");
  };
  return (
    <section
      className="schedule-print"
      dir={ar ? "rtl" : "ltr"}
      lang={lang}
      aria-label={ar ? "نسخة الجدول للطباعة" : "Printable schedule"}
    >
      <header>
        <div className="print-brand" dir="ltr">
          Jadw<span>AI</span>
        </div>
        <div>
          <h1>{run.snapshot.term}</h1>
          <p>
            {run.snapshot.name} · {ar ? "مسودة الجدول" : "Draft timetable"}
          </p>
        </div>
      </header>
      <div className="print-meta">
        <p>
          <b>{ar ? "النطاق" : "Scope"}:</b> {scope} · {assignments.length}{" "}
          {ar ? "حصة" : "sessions"}
        </p>
        <p>
          {ar ? "إصدار المدخلات" : "Input version"}: {run.input_version} ·{" "}
          {ar ? "المنطقة الزمنية" : "Timezone"}:{" "}
          <bdi>{run.snapshot.calendar.timezone}</bdi>
        </p>
        <p>
          {ar ? "تاريخ إنشاء المسودة" : "Draft created"}:{" "}
          {new Date(run.created_at).toLocaleString(ar ? "ar-EG" : "en-GB", {
            timeZone: run.snapshot.calendar.timezone,
          })}
        </p>
      </div>
      {stale && (
        <p className="print-warning">
          {ar
            ? "مسودة قديمة: تغيرت المدخلات منذ الإنشاء. تعكس هذه النسخة المدخلات المحفوظة وقت الإنشاء."
            : "Outdated draft: inputs have changed since generation. This copy reflects the saved generation snapshot."}
        </p>
      )}
      <p className="print-validation">
        {ar
          ? "اجتازت المسودة الفحوص المدعومة للمدخلات المحفوظة. قد تمثل هذه النسخة عرضاً مفلترًا للجدول الكامل."
          : "The draft passed supported checks against its saved inputs. This export may be a filtered view of the complete timetable."}
      </p>
      <ScheduleGrid run={run} assignments={assignments} lang={lang} />
      <div className="print-group-key">
        <strong>{ar ? "دليل المجموعات" : "Group key"}</strong>
        <p>
          {[
            ...new Set(
              assignments.flatMap(
                (a) => record(a.activity_id)?.group_ids ?? [],
              ),
            ),
          ]
            .map((id) => `${record(id)?.code}: ${group(id)}`)
            .join("; ")}
        </p>
      </div>
      {!assignments.length && (
        <p>
          {ar
            ? "لا توجد حصص تطابق الفلاتر المحددة."
            : "No sessions match the selected filters."}
        </p>
      )}
      <footer>
        <strong>
          {ar ? "مسودة فقط — غير منشورة" : "DRAFT ONLY — UNPUBLISHED"}
        </strong>
        <p>
          {ar
            ? "تُطبق الفحوصات المسجلة لهذه المسودة فقط. الحدود غير المحددة لا تُفحص. تصدير الملف لا يعني اعتماد الجدول للنشر."
            : "Only the checks recorded for this saved draft apply. Unconfigured limits remain unchecked. Exporting does not approve this timetable for publication."}
        </p>
        <small>
          {ar ? "مرجع المسودة" : "Draft reference"}: <bdi>{run.id}</bdi>
        </small>
      </footer>
    </section>
  );
}
