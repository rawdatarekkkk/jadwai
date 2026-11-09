import React, { useEffect, useRef, useState, useId } from "react";
import { clockHour, LIMIT_RULES, type Workspace, type DataRecord, type RecordKind, type Rule, type RuleType } from "./api";
import { describeRule, ruleTarget } from "./RuleText";
import { auditLabels, type Word } from "./i18n";
import { DEFAULT_CALENDAR } from "./CalendarSettings";
export type IconName =
  | "grid"
  | "book"
  | "people"
  | "room"
  | "sliders"
  | "calendar"
  | "clock"
  | "arrow"
  | "plus"
  | "check"
  | "search"
  | "chevron"
  | "logout"
  | "globe"
  | "x"
  | "edit"
  | "trash"
  | "lock"
  | "spark"
  | "leaf";
export function Icon({ name, size = 20 }: { name: IconName; size?: number }) {
  const paths: Record<IconName, React.ReactNode> = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    book: (
      <>
        <path d="M12 5c-3-2-6-2-9-1v15c3-1 6-1 9 1 3-2 6-2 9-1V4c-3-1-6-1-9 1Z" />
        <path d="M12 5v15" />
      </>
    ),
    people: (
      <>
        <circle cx="9" cy="7" r="3" />
        <path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6m2 3a5 5 0 0 1 3 5v3" />
      </>
    ),
    room: (
      <>
        <path d="M4 21V3h16v18M2 21h20M9 21v-7h6v7M8 7h1m6 0h1M8 10h1m6 0h1" />
      </>
    ),
    sliders: (
      <>
        <path d="M4 7h6m6 0h4M4 17h12m4 0h0" />
        <circle cx="13" cy="7" r="3" />
        <circle cx="17" cy="17" r="3" />
      </>
    ),
    calendar: (
      <>
        <rect x="3" y="5" width="18" height="16" rx="3" />
        <path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3 2" />
      </>
    ),
    arrow: <path d="M4 12h15m-5-5 5 5-5 5" />,
    plus: <path d="M12 5v14M5 12h14" />,
    check: <path d="m5 12 4 4L19 6" />,
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </>
    ),
    chevron: <path d="m9 5 7 7-7 7" />,
    logout: (
      <>
        <path d="M9 4H4v16h5m4-8h8m-4-4 4 4-4 4" />
      </>
    ),
    globe: (
      <>
        <circle cx="12" cy="12" r="9" />
        <ellipse cx="12" cy="12" rx="4" ry="9" />
        <path d="M3 12h18" />
      </>
    ),
    x: <path d="m6 6 12 12M6 18 18 6" />,
    edit: (
      <>
        <path d="m15 4 5 5M4 20l5-1L21 7l-5-5L4 14Z" />
      </>
    ),
    trash: (
      <>
        <path d="M3 6h18M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7m4-7v7" />
      </>
    ),
    lock: (
      <>
        <rect x="5" y="10" width="14" height="11" rx="2" />
        <path d="M8 10V6a4 4 0 0 1 8 0v4m-4 5v2" />
      </>
    ),
    spark: (
      <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" />
    ),
    leaf: (
      <>
        <path d="M5 20C2 9 9 2 21 3c0 12-7 18-16 17Zm0 0L16 8" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}
export function ScheduleArt({ t }: { t: (key: Word) => string }) {
  return (
    <div className="schedule-art" aria-label={t("illustrationNote")}>
      <div className="art-orbit orbit-one" />
      <div className="art-orbit orbit-two" />
      <span className="art-spark spark-one">✳</span>
      <span className="art-spark spark-two">✦</span>
      <div className="paper-week">
        <div className="paper-heading">
          <span>THE WEEK, IN BALANCE</span>
          <span>↗</span>
        </div>
        <div className="paper-days">
          {["S", "M", "T", "W", "T"].map((d, i) => (
            <span key={i}>{d}</span>
          ))}
        </div>
        <div className="paper-grid">
          {Array.from({ length: 20 }, (_, i) => (
            <i key={i} />
          ))}
          <span className="block block-a" />
          <span className="block block-b" />
          <span className="block block-c" />
          <span className="block block-d" />
          <span className="block block-e" />
        </div>
        <div className="paper-foot">
          <span />
          <span />
          <span />
        </div>
      </div>
      <div className="balance-tag">
        <span>
          <Icon name="check" size={13} />
        </span>
        {t("illustration")}
      </div>
      <small className="art-disclaimer">{t("illustrationNote")}</small>
    </div>
  );
}
export function Empty({
  icon,
  title,
  text,
}: {
  icon: IconName;
  title: string;
  text: string;
}) {
  return (
    <div className="empty">
      <span>
        <Icon name={icon} size={28} />
      </span>
      <h3>{title}</h3>
      <p>{text}</p>
    </div>
  );
}
export function EventList({
  ws,
  t,
  lang,
  limit,
}: {
  ws: Workspace;
  t: (key: Word) => string;
  lang: string;
  limit?: number;
}) {
  return (
    <div className="events">
      {ws.events.slice(0, limit).map((e) => (
        <div className="event" key={e.id}>
          <span className="event-dot">
            <Icon name="check" size={12} />
          </span>
          <div>
            <strong>
              {e.action_code && auditLabels[e.action_code]
                ? `${auditLabels[e.action_code][lang === "ar" ? 1 : 0]}${e.params?.target ? `: ${e.params.target}` : ""}`
                : e.action}
            </strong>
            <small>
              {t("actor")} {e.actor} <span>·</span>{" "}
              {new Date(e.at).toLocaleString(lang, {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                timeZone: ws.calendar?.timezone || "Africa/Cairo",
              })}
            </small>
          </div>
          <span className="event-version">v{e.version}</span>
        </div>
      ))}
      {!ws.events.length && <p>{t("noactivity")}</p>}
    </div>
  );
}
export function Modal({
  title,
  close,
  t,
  children,
  dismissible = true,
}: {
  dismissible?: boolean;
  title: string;
  close: () => void;
  t: (key: Word) => string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const titleId = useId();
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    const element = ref.current;
    const selector =
      "button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled)";
    (element?.querySelector(selector) as HTMLElement)?.focus();
    const key = (e: KeyboardEvent) => {
      if (
        Array.from(document.querySelectorAll('[role="dialog"]')).at(-1) !==
        element
      )
        return;
      if (e.key === "Escape" && dismissible) close();
      if (e.key === "Tab" && element) {
        const items = Array.from(
          element.querySelectorAll<HTMLElement>(selector),
        );
        const first = items[0],
          last = items.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", key);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = "";
      before?.focus();
    };
  }, []);
  return (
    <div className="modal-backdrop">
      <div
        ref={ref}
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
      >
        <div className="modal-heading">
          <h2 id={titleId}>{title}</h2>
          {dismissible && (
            <button
              className="icon-btn"
              aria-label={t("close")}
              onClick={close}
            >
              <Icon name="x" />
            </button>
          )}
        </div>
        {children}
      </div>
    </div>
  );
}
/** A short unique code from position and initials: Dr. Sara Saleh (doctor) -> D-SS, then D-SS2... */
export function instructorCode(name: string, position: string, records: { id: string; kind: string; code?: string }[], self?: string) {
  const words = name.replace(/^(dr|prof|eng|mr|ms|mrs)\.?\s+/i, "").split(/\s+/).filter(Boolean);
  const initials = words.map(w => w[0]).join("").toUpperCase().replace(/[^A-Z0-9\u0600-\u06FF]/g, "").slice(0, 6) || "X";
  const base = `${position === "ta" ? "T" : "D"}-${initials}`;
  const taken = new Set(records.filter(r => r.kind === "instructors" && r.id !== self).map(r => (r.code || "").toUpperCase()));
  for (let n = 1; ; n++) { const code = n === 1 ? base : `${base}${n}`; if (!taken.has(code)) return code; }
}

export function RecordForm({
  kind,
  record,
  ws,
  t,
  busy,
  cancel,
  submit,
}: {
  kind: RecordKind;
  record?: DataRecord;
  ws: Workspace;
  t: (key: Word) => string;
  busy: boolean;
  cancel: () => void;
  submit: (body: unknown) => void;
}) {
  const [instructors, setInstructors] = useState<string[]>(
      record?.eligible_instructors || [],
    ),
    [groups, setGroups] = useState<string[]>(record?.group_ids || []);
  const [courseId, setCourseId] = useState(record?.course_id || "");
  const [activityType, setActivityType] = useState(record?.activity_type || "lecture");
  const course = ws.course_catalog?.find(c => c.id === courseId);
  const eligible = ws.records.filter((r) => r.kind === "instructors" && (kind !== "courses" || (!course && !!record && !record.course_id) || course?.eligibility[activityType]?.includes(r.id))),
    groupOptions = ws.records.filter((r) => r.kind === "groups" && (kind !== "courses" || (!course && !!record && !record.course_id) || course?.group_ids.includes(r.id)));
  const changeCourse = (id: string) => { setCourseId(id); setInstructors([]); setGroups([]); };
  const changeType = (type: string) => { setActivityType(type); setInstructors([]); };
  const input = (
    name: string,
    label: Word,
    def: unknown,
    type = "text",
    min?: number,
    max?: number,
    step?: number,
  ) => (
    <label>
      {t(label)}
      <input
        name={name}
        type={type}
        required
        defaultValue={String(def ?? "")}
        min={min}
        max={max}
        step={step}
        maxLength={type === "text" ? (name === "code" ? 20 : 100) : undefined}
        pattern={type === "text" ? ".*\\S.*" : undefined}
      />
    </label>
  );
  const toggle = (id: string, list: string[], setter: (s: string[]) => void) =>
    setter(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const body: Record<string, unknown> = {
          name: f.get("name"),
          code: f.get("code"),
        };
        if (kind === "instructors") {
          body.department = String(f.get("department") || "").trim();
          body.day_off = f.get("day_off") || null;
          body.position = f.get("position");
          body.code = String(f.get("code") || "").trim() || instructorCode(String(f.get("name") || ""), String(f.get("position") || ""), ws.records, record?.id);
          body.max_weekly_hours = record?.max_weekly_hours ?? null;
        }
        if (kind === "groups") {
          body.size = Number(f.get("size"));
          body.year = Number(f.get("year"));
          body.major = f.get("major");
        }
        if (kind === "rooms") {
          body.capacity = Number(f.get("capacity"));
          body.room_types = f.getAll("room_types");
          body.equipment = String(f.get("equipment") || "")
            .split("|")
            .map((x) => x.trim())
            .filter(Boolean);
        }
        if (kind === "courses") {
          Object.assign(body, {
            course_id: courseId || null,
            name: course?.name || record?.name || f.get("name"),
            activity_type: activityType,
            sessions: Number(f.get("sessions")),
            duration: Number(f.get("duration")),
            eligible_instructors: instructors,
            group_ids: groups,
            required_equipment: String(f.get("required_equipment") || "")
              .split("|")
              .map((x) => x.trim())
              .filter(Boolean),
          });
        }
        if (kind === "rooms" && f.getAll("room_types").length === 0) {
          const checkbox = e.currentTarget.querySelector<HTMLInputElement>('input[name="room_types"]');
          checkbox?.setCustomValidity(t("selectRoomType"));
          checkbox?.reportValidity();
          return;
        }
        submit(body);
      }}
    >
      <div className="form-grid">
        {kind === "courses" ? <label className="course-select-field">{t("courseName")}
          <select name="name" value={courseId} required={!record || !!record.course_id} onChange={e => changeCourse(e.target.value)}>
            <option value="" disabled>{record && !record.course_id ? record.name : t("chooseCourse")}</option>
            {(ws.course_catalog || []).map(c => <option key={c.id} value={c.id}>{c.name} · {c.code}</option>)}
          </select><small>{t("courseSelectionHelp")}</small>
        </label> : input("name", "name", record?.name)}
        {kind !== "courses" && kind !== "instructors" && input("code", "code", record?.code)}
        {kind === "instructors" && <>
          {/* What an instructor needs: who they are and what they may teach; the rest is optional. */}
          <label>{t("position")}<select name="position" required defaultValue={record?.position || ""}>
            <option value="" disabled>{t("choosePosition")}</option>
            <option value="doctor">{t("doctor")}</option>
            <option value="ta">{t("ta")}</option>
          </select><small>{t("positionHelp")}</small></label>
          <label>{t("departmentField")}<input name="department" required maxLength={100} pattern=".*\S.*" list="known-departments" defaultValue={record?.department || ""} />
            <datalist id="known-departments">{[...new Set(ws.records.filter(r => r.kind === "instructors" && r.department).map(r => r.department as string))].sort().map(d => <option key={d} value={d} />)}</datalist>
            <small>{t("departmentHelp")}</small></label>
          <label>{t("dayOff")}<select name="day_off" defaultValue={record?.day_off || ""}>
            <option value="">{t("noDayOff")}</option>
            {(ws.calendar?.days || ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]).map(day => <option key={day} value={day}>{t(day as Word)}</option>)}
          </select><small>{t("dayOffHelp")}</small></label>
          <label>{t("codeOptional")}<input name="code" maxLength={20} defaultValue={record?.code || ""} /><small>{t("codeHelp")}</small></label>
        </>}
        {kind === "instructors" && <div className="meaning-preview" style={{gridColumn:"1 / -1"}}><strong>{t("standardWeeklyHours")}: 12</strong><p>{t("overtimeHelp")}</p></div>}
        {kind === "groups" && (
          <>
            {input("year", "studyYear", record?.year ?? "", "number", 1, 12)}
            {input("major", "major", record?.major ?? "")}
            {input("size", "size", record?.size || 30, "number", 1, 2000)}
          </>
        )}
        {kind === "rooms" && (
          <>
            {input(
              "capacity",
              "capacity",
              record ? (record.capacity ?? "") : 40,
              "number",
              1,
              2000,
            )}
            <fieldset className="room-type-field">
              <legend>{t("roomtype")}</legend>
              <p className="room-type-help">{t("roomTypesHelp")}</p>
              <div className="room-type-options">
              {["lecture", "lab", "flexible", "exam_hall"].map((k) => (
                <label key={k} className="room-type-choice">
                  <span className="room-type-icon" aria-hidden="true"><Icon name={k === "lecture" ? "book" : k === "lab" ? "grid" : k === "exam_hall" ? "edit" : "room"} size={20} /></span>
                  <span className="room-type-name">{t(k as Word)}</span>
                  <input type="checkbox" name="room_types" value={k} onChange={(e) => { e.currentTarget.form?.querySelector<HTMLInputElement>('input[name="room_types"]')?.setCustomValidity(""); }}
                    defaultChecked={(record?.room_types || [record?.room_type || "lecture"]).includes(k)} />
                </label>
              ))}
              </div>
            </fieldset>
          </>
        )}
        {kind === "courses" && (
          <>
            <label>
              {t("activitytype")}
              <select
                name="activity_type"
                value={activityType}
                onChange={e => changeType(e.target.value)}
              >
                {["lecture", "tutorial", "lab"].map((k) => (
                  <option key={k} value={k}>
                    {t(k as Word)}
                  </option>
                ))}
              </select>
            </label>
            {input("code", "code", record?.code)}
            {input(
              "sessions",
              "sessioncount",
              record?.sessions || 2,
              "number",
              1,
              10,
            )}
            {ws.calendar?.teaching_periods?.length ? (
              <label>
                {t("duration")}
                <select
                  name="duration"
                  defaultValue={
                    record?.duration ||
                    ws.calendar.teaching_periods[0].end -
                      ws.calendar.teaching_periods[0].start
                  }
                >
                  {[
                    ...new Set(
                      ws.calendar.teaching_periods.map((p) => p.end - p.start),
                    ),
                  ].map((n) => (
                    <option key={n} value={n}>
                      {n} {t("minutes")}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              input(
                "duration",
                "duration",
                record?.duration ||
                  (ws.calendar?.teaching_periods?.[0]
                    ? ws.calendar.teaching_periods[0].end -
                      ws.calendar.teaching_periods[0].start
                    : 60),
                "number",
                30,
                240,
                30,
              )
            )}
          </>
        )}
      </div>
      {kind === "rooms" && record?.source_info?.source_document && <p className="modal-description">{t("roomImportHelp")}</p>}
      <datalist id="room-features">{[...new Set(ws.records.flatMap(r => r.equipment || []))].map(f => <option key={f} value={f} />)}</datalist>
      {kind === "rooms" && (
        <label>
          {t("roomFeatures")}
          <input
            name="equipment"
            maxLength={500}
            list="room-features"
            defaultValue={record?.equipment?.join(" | ") || ""}
            placeholder={t("roomFeaturesHelp")}
          />
          <small>{t("roomFeaturesHelp")}</small>
        </label>
      )}
      {kind === "courses" && (
        <label>
          {t("requiredFeatures")}
          <input
            name="required_equipment"
            maxLength={500}
            list="room-features"
            defaultValue={record?.required_equipment?.join(" | ") || ""}
            placeholder={t("requiredFeaturesHelp")}
          />
          <small>{t("requiredFeaturesHelp")}</small>
        </label>
      )}
      {kind === "courses" && (
        <>
          {!course && !record && <div className="meaning-preview">{t("chooseCourseFirst")}</div>}
          {course && !eligible.length && <div className="meaning-preview">{t("noCourseInstructors")}</div>}
          {course && !groupOptions.length && <div className="meaning-preview">{t("noCourseGroups")}</div>}
          <fieldset>
            <legend>
              {t("instructorEligibility")} <small>· {t("selection")}</small>
            </legend>
            <div className="check-options">
              {eligible.map((r) => (
                <label key={r.id}>
                  <input
                    type="checkbox"
                    checked={instructors.includes(r.id)}
                    onChange={() => toggle(r.id, instructors, setInstructors)}
                  />
                  {r.name}
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>
              {t("studentGroups")} <small>· {t("selection")}</small>
            </legend>
            <div className="check-options">
              {groupOptions.map((r) => (
                <label key={r.id}>
                  <input
                    type="checkbox"
                    checked={groups.includes(r.id)}
                    onChange={() => toggle(r.id, groups, setGroups)}
                  />
                  {r.year ? `${t("studyYear")} ${r.year} / ` : ""}
                  {r.major ? `${r.major} / ` : ""}
                  {r.name}
                </label>
              ))}
            </div>
          </fieldset>
        </>
      )}
      <div className="form-actions">
        <button
          className="btn white"
          type="button"
          disabled={busy}
          onClick={cancel}
        >
          {t("cancel")}
        </button>
        <button
          className="btn primary"
          disabled={
            busy ||
            (kind === "courses" && ((!courseId && (!record || !!record.course_id)) || !instructors.length || !groups.length))
          }
        >
          {t(busy ? "working" : "save")}
          <Icon name="check" size={16} />
        </button>
      </div>
    </form>
  );
}
export function RuleForm({
  ws,
  t,
  busy,
  cancel,
  submit,
}: {
  ws: Workspace;
  t: (key: Word) => string;
  busy: boolean;
  cancel: () => void;
  submit: (body: unknown) => void;
}) {
  const calendar = ws.calendar || DEFAULT_CALENDAR;
  const [type, setType] = useState<RuleType>("unavailable"),
    [target, setTarget] = useState(""),
    [day, setDay] = useState<string>(calendar.days[0]),
    [start, setStart] = useState(calendar.start_hour),
    [end, setEnd] = useState(Math.min(calendar.start_hour + 3, calendar.end_hour)),
    [picked, setPicked] = useState<string[]>([]),
    [amount, setAmount] = useState(4);
  const limit = LIMIT_RULES.includes(type);
  const spec = ruleTarget(type);
  const targets = spec ? ws.records.filter(r => r.kind === spec[1]) : [];
  const targetId = targets.some(r => r.id === target) ? target : targets[0]?.id || "";
  const choices = type === "activity_room" ? ws.records.filter(r => r.kind === "rooms") : type === "activities_not_same_day" ? ws.records.filter(r => r.kind === "courses") : [];
  // Half-hour steps across the teaching day.
  const halfHours = Array.from({ length: (calendar.end_hour - calendar.start_hour) * 2 + 1 }, (_, i) => calendar.start_hour + i / 2);
  const params = { room_ids: type === "activity_room" ? picked : null, activity_ids: type === "activities_not_same_day" ? picked : null,
    hours: type.endsWith("daily_hours") ? amount : null, days: type === "instructor_max_days" ? amount : null };
  const body = { type, ...(spec ? { [spec[0]]: targetId } : {}), day: limit ? null : day === "every" ? null : day,
    start_hour: limit ? null : start, end_hour: limit ? null : end, strength: type === "preferred_period" ? "preferred" : "mandatory", params };
  const meaning = describeRule(body as unknown as Rule, ws.records, t);
  const valid = (!spec || targetId) && (limit ? (type === "activity_room" ? picked.length > 0 : type === "activities_not_same_day" ? picked.length >= 2 : amount > 0) : end > start);
  if (!ws.records.some(r => ["instructors", "rooms", "groups"].includes(r.kind)))
    return (
      <>
        <div className="empty">
          <p>{t("needInstructor")}</p>
        </div>
        <button className="btn white" onClick={cancel}>
          {t("cancel")}
        </button>
      </>
    );
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit({ title: new FormData(e.currentTarget).get("title"), ...body });
      }}
    >
      <p className="modal-description">{t("ruleHelp")}</p>
      {type.endsWith("_allowed") && <p>{t("activity_allowed") === "Activity permitted window" ? "Approved windows for the same target are alternatives across the whole week. Every session must fit one window. Different targets apply together; days without a window are excluded." : "النوافذ المعتمدة لنفس الهدف بدائل خلال الأسبوع. يجب أن تقع كل حصة بالكامل داخل نافذة؛ تُطبق قيود الأهداف المختلفة معًا، وتُستبعد الأيام بلا نافذة."}</p>}
      <label>
        {t("ruleTitle")}
        <input name="title" required maxLength={100} pattern=".*\S.*" />
      </label>
      <div className="form-grid">
        <label>
          {t("type")}
          <select value={type} onChange={(e) => { setType(e.target.value as RuleType); setPicked([]); setAmount(e.target.value === "instructor_max_days" ? 3 : 4); }}>
            {(["unavailable", "room_unavailable", "group_unavailable", "activity_allowed", "group_allowed", "preferred_period", ...LIMIT_RULES] as RuleType[]).map(v => (
              <option key={v} value={v}>{t(v as Word)}</option>
            ))}
          </select>
        </label>
        {spec && <label>
          {t(spec[1] === "instructors" ? "instructor" : spec[1])}
          <select required value={targetId} onChange={(e) => setTarget(e.target.value)}>
            {targets.map((r) => (
              <option key={r.id} value={r.id}>
                {r.name}{r.kind === "courses" && r.activity_type ? ` (${t(r.activity_type as Word)})` : ""}
              </option>
            ))}
          </select>
        </label>}
        {!limit && <label>
          {t("day")}
          <select value={day} onChange={(e) => setDay(e.target.value)}>
            <option value="every">{t("everyDay")}</option>
            {calendar.days.map((d) => (
              <option key={d} value={d}>
                {t(d as Word)}
              </option>
            ))}
          </select>
        </label>}
        {!limit && <div className="time-fields">
          <label>
            {t("start")}
            <select value={start} onChange={(e) => setStart(Number(e.target.value))}>
              {halfHours.slice(0, -1).map((h) => <option key={h} value={h}>{clockHour(h)}</option>)}
            </select>
          </label>
          <label>
            {t("end")}
            <select value={end} onChange={(e) => setEnd(Number(e.target.value))}>
              {halfHours.slice(1).map((h) => <option key={h} value={h}>{clockHour(h)}</option>)}
            </select>
          </label>
        </div>}
        {(type.endsWith("daily_hours") || type === "instructor_max_days") && <label>
          {t(type === "instructor_max_days" ? "daysPerWeek" : "hoursPerDay")}
          <input type="number" min={type === "instructor_max_days" ? 1 : 0.5} max={type === "instructor_max_days" ? 7 : 24} step={type === "instructor_max_days" ? 1 : 0.5} value={amount} onChange={(e) => setAmount(Number(e.target.value))} />
        </label>}
      </div>
      {choices.length > 0 && <fieldset className="choice-list">
        <legend>{t(type === "activity_room" ? "allowedRooms" : "activitiesSeparate")}</legend>
        {choices.map(r => <label key={r.id} className="check-row"><input type="checkbox" checked={picked.includes(r.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, r.id] : picked.filter(x => x !== r.id))} />{r.name}{r.kind === "courses" && r.activity_type ? ` (${t(r.activity_type as Word)})` : ""}</label>)}
      </fieldset>}
      <div className="meaning-preview">
        <span className="eyebrow">{t("meaning")}</span>
        <p>
          {meaning.subject} · {meaning.type}
          <br />
          <bdi>{meaning.detail}</bdi> · {t(type === "preferred_period" ? "preferred" : "mandatory")}
        </p>
        <span className="pill amber">{t("draft")}</span>
      </div>
      <div className="form-actions">
        <button
          type="button"
          className="btn white"
          disabled={busy}
          onClick={cancel}
        >
          {t("cancel")}
        </button>
        <button className="btn primary" disabled={busy || !valid}>
          {t(busy ? "working" : "save")}
        </button>
      </div>
    </form>
  );
}
