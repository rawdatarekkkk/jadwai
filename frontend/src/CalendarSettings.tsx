import { REFERENCE_PERIODS } from "./referencePeriods";
import { useState } from "react";
import { ApiError, type Workspace } from "./api";
import { errors, type Word } from "./i18n";
export const DEFAULT_CALENDAR = {
  timezone: "Africa/Cairo",
  days: ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"],
  start_hour: 8,
  end_hour: 18,
  period_minutes: 30,
  start_date: null as string | null,
  end_date: null as string | null,
};
export function CalendarSettings({
  ws,
  t,
  lang,
  save,
  busy,
}: {
  ws: Workspace;
  t: (key: Word) => string;
  lang: "en" | "ar";
  save: (body: unknown) => Promise<void>;
  busy: boolean;
}) {
  const calendar = ws.calendar || DEFAULT_CALENDAR;
  const [namedPeriods, setNamedPeriods] = useState(
    !!ws.calendar?.teaching_periods?.length,
  );
  const policy = ws.calendar?.realism_policy;
  const savedPolicyActive = !!(policy?.spread_activity_days || policy?.compact_days || policy?.student_daily_hours != null || policy?.instructor_daily_hours != null || policy?.max_consecutive_periods != null || policy?.max_idle_periods != null);
  const [realistic, setRealistic] = useState(savedPolicyActive);
  const [days, setDays] = useState(calendar.days),
    [error, setError] = useState("");
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        setError("");
        void save({
          name: f.get("name"),
          term: f.get("term"),
          timezone: f.get("timezone"),
          days,
          start_hour: namedPeriods ? 8 : Number(f.get("start")),
          end_hour: namedPeriods ? 22 : Number(f.get("end")),
          period_minutes: namedPeriods ? 30 : Number(f.get("period")),
          teaching_periods: namedPeriods ? REFERENCE_PERIODS : [],
          realism_policy: realistic ? {
            student_daily_hours: f.get("student_daily_hours") === "" ? null : Number(f.get("student_daily_hours")),
            instructor_daily_hours: f.get("instructor_daily_hours") === "" ? null : Number(f.get("instructor_daily_hours")),
            spread_activity_days: f.get("spread_activity_days") === "on",
            max_consecutive_periods: f.get("max_consecutive_periods") === "" ? null : Number(f.get("max_consecutive_periods")),
            max_idle_periods: f.get("max_idle_periods") === "" ? null : Number(f.get("max_idle_periods")),
            compact_days: f.get("compact_days") === "on",
          } : {},
          start_date: f.get("start_date") || null,
          end_date: f.get("end_date") || null,
        }).catch((e) =>
          setError(
            errors[e instanceof ApiError ? e.code : "connection_failed"]?.[
              lang === "en" ? 0 : 1
            ] || t("unsaved"),
          ),
        );
      }}
    >
      <p className="modal-description">{t("calendarHelp")}</p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <label>
        {lang === "ar" ? "نظام الفترات" : "Teaching periods"}
        <select
          value={namedPeriods ? "reference" : "regular"}
          onChange={(e) => {setNamedPeriods(e.target.value === "reference"); if (e.target.value !== "reference") setRealistic(false);}}
        >
          <option value="regular">
            {lang === "ar" ? "شبكة زمنية منتظمة" : "Regular time grid"}
          </option>
          <option value="reference">
            {lang === "ar"
              ? "الفترات الخمس · ٩٠ دقيقة"
              : "Five periods · 90 minutes"}
          </option>
        </select>
      </label>
      {namedPeriods && (
        <p className="modal-description">
          {REFERENCE_PERIODS.map(
            (p) =>
              `${String(Math.floor(p.start / 60)).padStart(2, "0")}:${String(p.start % 60).padStart(2, "0")}–${String(Math.floor(p.end / 60)).padStart(2, "0")}:${String(p.end % 60).padStart(2, "0")}`,
          ).join(" · ")}
        </p>
      )}
      <div className="form-grid">
        <label>
          {t("departmentName")}
          <input
            name="name"
            defaultValue={ws.name}
            required
            maxLength={100}
            pattern=".*\S.*"
          />
        </label>
        <label>
          {t("termName")}
          <input
            name="term"
            defaultValue={ws.term}
            required
            maxLength={100}
            pattern=".*\S.*"
          />
        </label>
        <label>
          {t("timezone")}
          <input
            name="timezone"
            defaultValue={calendar.timezone}
            list="timezones"
            required
            maxLength={100}
          />
          <datalist id="timezones">
            <option value="Africa/Cairo" />
            <option value="UTC" />
          </datalist>
        </label>
        {!namedPeriods && (
          <>
            <label>
              {t("periodLength")}
              <select name="period" defaultValue={calendar.period_minutes}>
                <option value="30">30 {t("minutes")}</option>
                <option value="60">60 {t("minutes")}</option>
              </select>
            </label>
            <label>
              {t("teachingStart")}
              <input
                type="number"
                name="start"
                min={0}
                max={23}
                required
                defaultValue={calendar.start_hour}
              />
            </label>
            <label>
              {t("teachingEnd")}
              <input
                type="number"
                name="end"
                min={1}
                max={24}
                required
                defaultValue={calendar.end_hour}
              />
            </label>
          </>
        )}
        <label>
          {t("termStart")}
          <input
            type="date"
            name="start_date"
            defaultValue={calendar.start_date || ""}
          />
        </label>
        <label>
          {t("termEnd")}
          <input
            type="date"
            name="end_date"
            defaultValue={calendar.end_date || ""}
          />
        </label>
      </div>
      <fieldset>
        <legend>{t("teachingDays")}</legend>
        <div className="check-options">
          {[
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
          ].map((day) => (
            <label key={day}>
              <input
                type="checkbox"
                checked={days.includes(day)}
                onChange={() =>
                  setDays(
                    days.includes(day)
                      ? days.filter((d) => d !== day)
                      : [...days, day],
                  )
                }
              />
              {t(day as Word)}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend>{lang === "ar" ? "جودة اليوم الدراسي" : "Daily timetable quality"}</legend>
        <label className="check-label"><input type="checkbox" checked={realistic} onChange={e => {setRealistic(e.target.checked); if(e.target.checked) setNamedPeriods(true);}}/>{lang === "ar" ? "تفعيل سياسة يوم دراسي عملي" : "Enable practical-day scheduling policy"}</label>
        {realistic && <>
          <p className="modal-description">{lang === "ar" ? "ساعات تدريس فعلية بدون الاستراحات. الفجوات هي فترات تدريس فارغة بين أول وآخر حصة. الإعدادات التجريبية قابلة للتعديل وليست سياسة جامعية معتمدة." : "Teaching hours exclude breaks. Gaps count empty teaching periods between the first and last session. Editable demo settings; not approved university policy."}</p>
          <div className="form-grid">
            <label>{lang === "ar" ? "أقصى ساعات الطالب يومياً" : "Student daily teaching hours"}<input name="student_daily_hours" type="number" min={0} max={24} step={0.5} defaultValue={savedPolicyActive ? policy?.student_daily_hours ?? "" : 6}/></label>
            <label>{lang === "ar" ? "أقصى ساعات المدرس يومياً" : "Instructor daily teaching hours"}<input name="instructor_daily_hours" type="number" min={0} max={24} step={0.5} defaultValue={savedPolicyActive ? policy?.instructor_daily_hours ?? "" : 6}/></label>
            <label>{lang === "ar" ? "أقصى فترات متتالية" : "Maximum consecutive teaching periods"}<input name="max_consecutive_periods" type="number" min={1} max={24} step={1} defaultValue={savedPolicyActive ? policy?.max_consecutive_periods ?? "" : 3}/></label>
            <label>{lang === "ar" ? "أقصى فترات فراغ يومياً" : "Maximum idle teaching periods per day"}<input name="max_idle_periods" type="number" min={0} max={24} step={1} defaultValue={savedPolicyActive ? policy?.max_idle_periods ?? "" : 1}/></label>
          </div>
          <label className="check-label"><input name="spread_activity_days" type="checkbox" defaultChecked={savedPolicyActive ? policy?.spread_activity_days ?? false : true}/>{lang === "ar" ? "توزيع حصص النشاط على أيام مختلفة" : "Keep each activity’s weekly sessions on different days"}</label>
          <label className="check-label"><input name="compact_days" type="checkbox" defaultChecked={savedPolicyActive ? policy?.compact_days ?? false : true}/>{lang === "ar" ? "تقليل الفجوات بعد تلبية تفضيلات المدرسين" : "Minimise gaps after instructor time preferences"}</label>
        </>}
      </fieldset>
      <div className="form-actions">
        <button className="btn primary" disabled={busy || !days.length}>
          {t(busy ? "working" : "save")}
        </button>
      </div>
    </form>
  );
}
