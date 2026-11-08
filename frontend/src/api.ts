export type RecordKind = "courses" | "instructors" | "rooms" | "groups";
export type CatalogCourse = {expected_students?: number | null; source_info?: {program_semesters?: {faculty_section:string; program_or_cohort:string|null;semester:number|null}[];name_variants?:string[];source_pages?:number[];source_document?:string}; id: string; name: string; code: string; eligibility: Record<string, string[]>; group_ids: string[]};
export type DataRecord = {
  course_id?: string | null;
  id: string;
  kind: RecordKind;
  name: string;
  code: string;
  department?: string;
  max_weekly_hours?: number | null;
  source_info?: {source_document?:string; references?:{sheet:string;cell:string}[]};
  capacity?: number | null;
  size?: number;
  year?: number | null;
  major?: string | null;
  day_off?: string | null;
  position?: "doctor" | "ta" | null;
  room_type?: string;
  room_types?: string[];
  equipment?: string[];
  required_equipment?: string[];
  activity_type?: string;
  sessions?: number;
  duration?: number;
  eligible_instructors?: string[];
  group_ids?: string[];
};
export type Rule = {
  id: string;
  title: string;
  instructor_id?: string | null;
  room_id?: string | null;
  group_id?: string | null;
  activity_id?: string | null;
  type: RuleType;
  /** null = every teaching day; limit rules have no day or hours. */
  day: string | null;
  start_hour: number | null;
  end_hour: number | null;
  strength: "mandatory" | "preferred";
  status: "draft" | "approved";
  params?: RuleParams;
};
export type RuleType = "unavailable" | "preferred_period" | "room_unavailable" | "group_unavailable" | "activity_allowed" | "group_allowed"
  | "activity_room" | "activities_not_same_day" | "instructor_max_daily_hours" | "group_max_daily_hours" | "instructor_max_days";
export type RuleParams = {room_ids?: string[] | null; activity_ids?: string[] | null; hours?: number | null; days?: number | null};
export const LIMIT_RULES: RuleType[] = ["activity_room", "activities_not_same_day", "instructor_max_daily_hours", "group_max_daily_hours", "instructor_max_days"];
/** 8.5 -> "08:30" */
export const clockHour = (h: number) => `${String(Math.floor(h)).padStart(2, "0")}:${h % 1 ? "30" : "00"}`;
export type AssignmentLock = {id:string;source_run_id:string;activity_id:string;occurrence:number;instructor_id:string|null;room_id:string|null;day:string|null;start_minute:number|null;status:"draft"|"approved";approved_by?:string|null};
export type Workspace = {
  course_catalog?: CatalogCourse[];
  assignment_locks?: AssignmentLock[];
  name: string;
  term: string;
  version: number;
  calendar?: {
    timezone: string;
    days: string[];
    start_hour: number;
    end_hour: number;
    period_minutes: number;
    teaching_periods?: { start: number; end: number }[];
    realism_policy?: {student_daily_hours?: number | null; instructor_daily_hours?: number | null; spread_activity_days?: boolean; max_consecutive_periods?: number | null; max_idle_periods?: number | null; compact_days?: boolean};
    start_date: string | null;
    end_date: string | null;
  };
  records: DataRecord[];
  rules: Rule[];
  events: {
    id: string;
    action: string;
    actor: string;
    action_code?: string;
    params?: { target?: string };
    at: string;
    version: number;
  }[];
};
export type User = {
  id: string;
  name: string;
  email: string;
  role: string;
  group_id?: string | null;
  instructor_id?: string | null;
  advising_student_id?: string | null;
  active: boolean;
  version: number;
};
export class ApiError extends Error {
  constructor(
    public code: string,
    public status: number,
    public details: {errors?: string[]} = {},
  ) {
    super(code);
  }
}
export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  version?: number,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Jadwai-Request": "1",
        ...(version !== undefined ? { "If-Match": `"${version}"` } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw new ApiError("connection_failed", 0);
  }
  if (!response.ok) {
    if (
      response.status === 401 &&
      !path.startsWith("/auth/login") &&
      typeof window !== "undefined"
    )
      window.dispatchEvent(new Event("jadwai-session-expired"));
    const error = await response.json().catch(() => ({}));
    const detail = error.detail;
    throw new ApiError(
      typeof detail === "string" ? detail : typeof detail?.code === "string" ? detail.code : "invalid_input",
      response.status,
      typeof detail === "object" && detail && !Array.isArray(detail) ? detail : {},
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export type ScheduleAssignment = {
  activity_id: string;
  occurrence: number;
  instructor_id: string;
  room_id: string;
  day: string;
  start_minute: number;
  end_minute: number;
};
export type ScopeItem = { programme: string; year: number | null };
export type Repair = { status: "fixable" | "data_change_needed" | "not_found"; verified?: boolean; message?: string; findings?: string[];
  suggestions?: { kind: string; target: string | null; title: string; message: string; sessions: string[] }[] };
export type RunProgress = { scheduled_sessions: number; total_sessions: number; complete: boolean; remaining_programmes: ScopeItem[]; scope: ScopeItem[] | null; base_run_id: string | null };
export type ScheduleRun = {
  id: string;
  input_version: number;
  stale: boolean;
  status:
    | "queued"
    | "running"
    | "completed"
    | "blocked"
    | "infeasible"
    | "unknown"
    | "failed"
    | "cancelled";
  cancel_requested: boolean;
  created_at: string;
  name?: string | null;
  parent_run_id?: string | null;
  published_at?: string | null;
  /** How much of the whole timetable a run covers (runs built in parts). */
  progress?: RunProgress | null;
  snapshot: {
    name: string;
    term: string;
    calendar: NonNullable<Workspace["calendar"]>;
    records: DataRecord[];
    rules: Rule[];
  };
  result: {
    repair?: Repair;
    provenance?: { snapshot: {snapshot_sha256:string; config_sha256:string} | null; validator_version:string | null; worker_elapsed_seconds:number; reproducibility_note:string };
    solver_diagnostics?: {raw_status:string; ortools_version:string; parameters_text:string; solver_seconds:number; objective_definition:string};
    preflight?: import("./RunChecks").Preparation;
    progress?: {best_objective:number;best_bound:number;solver_seconds:number} | null;
    reason?: string;
    activity_id?: string;
    assignments: ScheduleAssignment[];
    preference_penalty?: number;
    optimal?: boolean;
    validation?: { coverage?: {check:string;status:string;applicable:number|null;basis:string}[]; conflict_basis?:string; violations?: {code:string;message:string;sessions:ScheduleAssignment[];resource_ids:string[];rule_ids:string[]}[]; passed: boolean; checks: string[]; errors: string[]; realism?: {policy: NonNullable<Workspace["calendar"]>["realism_policy"]; daily_resources: {kind:string; id:string; day:string; teaching_hours:number; idle_periods:number; max_consecutive_periods:number}[]; idle_periods:number} | null; workload?: {instructor_id: string; assigned_hours: number; max_weekly_hours: number | null; configured: boolean; exceeded: boolean; standard_weekly_hours?: number | null; regular_hours?: number | null; extra_hours?: number | null}[] | null };
  } | null;
};

export async function downloadScheduleStatistics(
  id: string,
  format: "pdf" | "html" | "json" = "pdf",
  scope: { group?: string; year?: string; major?: string } = {},
) {
  // A report for the group, or year and programme, being viewed; none = the whole timetable.
  const query = new URLSearchParams({ format, ...Object.fromEntries(Object.entries(scope).filter(([, v]) => v)) });
  const response = await fetch(
    `/api/schedules/${encodeURIComponent(id)}/statistics?${query}`,
    { credentials: "same-origin" },
  );
  if (!response.ok) {
    if (response.status === 401)
      window.dispatchEvent(new Event("jadwai-session-expired"));
    throw new ApiError("statistics_unavailable", response.status);
  }
  // Download the authenticated attachment directly; this also works in browsers
  // that restrict downloads from generated blob URLs.
  const url = `/api/schedules/${encodeURIComponent(id)}/statistics?${query}`;
  const link = document.createElement("a");
  link.href = url;
  // The server supplies a descriptive filename in Content-Disposition.
  link.download = "";
  document.body.append(link);
  link.click();
  link.remove();

}


/** The timetable as a landscape PDF built on the server, with a short descriptive file name. */
export function downloadTimetablePdf(id: string, scope: { group?: string; year?: string; major?: string } = {}) {
  const query = new URLSearchParams(Object.fromEntries(Object.entries(scope).filter(([, v]) => v)) as Record<string, string>);
  const link = document.createElement("a");
  link.href = `/api/schedules/${encodeURIComponent(id)}/timetable.pdf${query.size ? `?${query}` : ""}`;
  link.download = "";
  document.body.append(link);
  link.click();
  link.remove();
}
