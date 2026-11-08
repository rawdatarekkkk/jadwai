import { describe, expect, it } from "vitest";
import { continuable, programmeSessions } from "./PartPlan";
import type { ScheduleRun, Workspace } from "./api";

const ws = { records: [
  { id: "g1", kind: "groups", major: "A", year: 1 }, { id: "g2", kind: "groups", major: "B", year: 2 },
  { id: "c1", kind: "courses", group_ids: ["g1"], sessions: 2 },
  { id: "c2", kind: "courses", group_ids: ["g1", "g2"], sessions: 1 },
] } as unknown as Workspace;

describe("building in parts", () => {
  it("counts sessions per programme, shared activities in each", () => {
    expect(programmeSessions(ws).map((u) => [u.programme, u.year, u.sessions])).toEqual([["A", 1, 3], ["B", 2, 1]]);
  });
  it("continues only from a current, valid, incomplete part", () => {
    const run = { status: "completed", stale: false, result: { validation: { passed: true } }, progress: { complete: false, scheduled_sessions: 2, total_sessions: 3, remaining_programmes: [{ programme: "B", year: 2 }] } } as unknown as ScheduleRun;
    expect(continuable(run)?.remaining_programmes).toEqual([{ programme: "B", year: 2 }]);
    expect(continuable({ ...run, stale: true })).toBeFalsy();
    expect(continuable({ ...run, progress: { ...run.progress!, complete: true } })).toBeFalsy();
  });
});
