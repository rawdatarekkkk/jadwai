import type { ScheduleAssignment, ScheduleRun } from "./api";
const names: Record<string, string> = {
  Sunday: "الأحد",
  Monday: "الاثنين",
  Tuesday: "الثلاثاء",
  Wednesday: "الأربعاء",
  Thursday: "الخميس",
  Friday: "الجمعة",
  Saturday: "السبت",
};
const clock = (m: number) =>
  `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;

export function ScheduleGrid({
  run,
  assignments,
  lang,
}: {
  run: ScheduleRun;
  assignments: ScheduleAssignment[];
  lang: "en" | "ar";
}) {
  const ar = lang === "ar",
    cal = run.snapshot.calendar;
  const start = cal.start_hour * 60,
    end = cal.end_hour * 60,
    step = cal.period_minutes;
  const periods = cal.teaching_periods?.length
    ? cal.teaching_periods
    : Array.from({ length: (end - start) / step }, (_, i) => ({
        start: start + i * step,
        end: start + (i + 1) * step,
      }));
  const slots = periods.map((p) => p.start);
  const record = (id: string) => run.snapshot.records.find((r) => r.id === id);
  return (
    <table className="schedule-matrix" dir="ltr">
      <colgroup>
        <col className="matrix-day-column" />
        {slots.map((s) => (
          <col key={s} />
        ))}
      </colgroup>
      <thead>
        <tr>
          <th scope="col">{ar ? "اليوم" : "Day"}</th>
          {slots.map((s, i) => (
            <th scope="col" key={s}>
              <span>
                {ar
                  ? `الفترة ${i + 1}`
                  : cal.teaching_periods?.length
                    ? [
                        "First Period",
                        "Second Period",
                        "Third Period",
                        "Fourth Period",
                        "Fifth Period",
                        "Sixth Period",
                        "Seventh Period",
                      ][i] || `Period ${i + 1}`
                    : `Slot ${i + 1}`}
              </span>
              <small dir="ltr">
                {clock(s)}
                <br />
                {clock(periods[i].end)}
              </small>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {cal.days.map((day) => {
          const sessions = assignments
            .filter((a) => a.day === day)
            .sort(
              (a, b) =>
                a.start_minute - b.start_minute ||
                b.end_minute - a.end_minute ||
                a.activity_id.localeCompare(b.activity_id),
            );
          const laneEnds: number[] = [];
          const placed = sessions.map((a) => {
            let lane = laneEnds.findIndex((e) => e <= a.start_minute);
            if (lane < 0) lane = laneEnds.length;
            laneEnds[lane] = a.end_minute;
            return { assignment: a, lane };
          });
          const free: { from: number; span: number }[] = [];
          for (let i = 0; i < slots.length; i++) {
            if (
              sessions.some(
                (a) =>
                  a.start_minute < periods[i].end && a.end_minute > slots[i],
              )
            )
              continue;
            const from = i;
            while (
              i + 1 < slots.length &&
              !sessions.some(
                (a) =>
                  a.start_minute < periods[i + 1].end &&
                  a.end_minute > slots[i + 1],
              )
            )
              i++;
            free.push({ from, span: i - from + 1 });
          }
          return (
            <tr key={day}>
              <th scope="row" className="matrix-day-label">
                {ar ? (names[day] ?? day) : day}
              </th>
              <td colSpan={slots.length} className="matrix-day-body">
                <div
                  className="matrix-track"
                  style={{
                    gridTemplateColumns: `repeat(${slots.length}, minmax(0, 1fr))`,
                    gridTemplateRows: `repeat(${Math.max(1, laneEnds.length)}, auto)`,
                  }}
                >
                  {free.map((f) => (
                    <div
                      className="matrix-free"
                      key={f.from}
                      style={{
                        gridColumn: `${f.from + 1} / span ${f.span}`,
                        gridRow: `1 / span ${Math.max(1, laneEnds.length)}`,
                      }}
                    >
                      {ar ? "خالي" : "Free"}
                    </div>
                  ))}
                  {placed.map(({ assignment: a, lane }) => (
                    <article
                      className="matrix-session"
                      key={`${a.activity_id}-${a.occurrence}`}
                      dir={ar ? "rtl" : "ltr"}
                      style={{
                        gridColumn: `${periods.findIndex((p) => p.start === a.start_minute) + 1} / span ${periods.filter((p) => p.start >= a.start_minute && p.end <= a.end_minute).length}`,
                        gridRow: lane + 1,
                      }}
                    >
                      <time dir="ltr">
                        {clock(a.start_minute)}–{clock(a.end_minute)}
                      </time>
                      <strong>{record(a.activity_id)?.name}</strong>
                      <small>{record(a.activity_id)?.code}</small>
                      <span>{record(a.instructor_id)?.name}</span>
                      <span>{record(a.room_id)?.code}</span>
                      <small>
                        {record(a.activity_id)
                          ?.group_ids?.map((id) => record(id)?.code)
                          .join(" · ")}
                      </small>
                    </article>
                  ))}
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
