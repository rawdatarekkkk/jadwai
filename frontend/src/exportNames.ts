import type { ScheduleRun } from "./api";

// Keep Unicode names, but strip filesystem-reserved characters and control codes.
const part = (value: string, limit = 45) => value.normalize("NFKC")
  .replace(/[<>:"/\\|?*\u0000-\u001f\u007f]/g, " ")
  .trim().replace(/\s+/g, "-").replace(/[. -]+$/g, "").slice(0, limit) || "Schedule";

export function timetableFilename(run: ScheduleRun, scope: string) {
  return ["JadwAI", part(run.snapshot.term), part(run.snapshot.name), "Timetable",
    part(scope, 65), "Draft", `v${run.input_version}`, run.created_at.slice(0, 10), run.id.slice(0, 8)].join("_");
}
