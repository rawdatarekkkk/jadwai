// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { Timetable } from "./Timetable";
import type { Workspace, ScheduleRun } from "./api";

beforeEach(() => { vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {}); });
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});
const records: Workspace["records"] = [
  {
    id: "a",
    kind: "courses",
    name: "Algorithms",
    code: "CS1",
    sessions: 2,
    duration: 60,
    activity_type: "lecture",
    group_ids: ["g"],
    eligible_instructors: ["t"],
  },
  { id: "t", kind: "instructors", name: "Dr Noor", code: "N" },
  { id: "g", kind: "groups", name: "Group A", code: "G", size: 20 },
  {
    id: "r",
    kind: "rooms",
    name: "Cedar",
    code: "R",
    capacity: 30,
    room_type: "lecture",
  },
];
const ws: Workspace = {
  name: "CS",
  term: "Fall 2026",
  version: 4,
  calendar: {
    days: ["Sunday", "Monday"],
    start_hour: 8,
    end_hour: 18,
    period_minutes: 30,
    timezone: "Africa/Cairo",
    start_date: null,
    end_date: null,
  },
  records,
  rules: [],
  events: [],
};
const run: ScheduleRun = {
  id: "job",
  status: "completed",
  input_version: 4,
  stale: false,
  created_at: "2026-10-17T12:00:00Z",
  cancel_requested: false,
  snapshot: {
    name: ws.name,
    term: ws.term,
    calendar: ws.calendar!,
    records,
    rules: [],
  },
  result: {
    assignments: [
      {
        activity_id: "a",
        occurrence: 0,
        instructor_id: "t",
        room_id: "r",
        day: "Sunday",
        start_minute: 480,
        end_minute: 540,
      },
      {
        activity_id: "a",
        occurrence: 1,
        instructor_id: "t",
        room_id: "r",
        day: "Monday",
        start_minute: 600,
        end_minute: 660,
      },
    ],
    validation: { passed: true, errors: [], checks: [] },
    preference_penalty: 0,
  },
};
const response = (body: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => structuredClone(body),
});

test("generates with the current version and presents the actual assignments", async () => {
  const fetcher = vi.fn(async (_path: string, init?: RequestInit) =>
    response(init?.method === "POST" ? run : []),
  );
  vi.stubGlobal("fetch", fetcher);
  render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  const button = await screen.findByRole("button", {
    name: "Generate schedule",
  });
  await waitFor(() =>
    expect((button as HTMLButtonElement).disabled).toBe(false),
  );
  fireEvent.click(button);
  expect(await screen.findAllByText("Algorithms")).toHaveLength(2);
  expect(screen.getByText("08:00 – 09:00")).toBeTruthy();
  expect(screen.getByText("Supported checks passed")).toBeTruthy();
  expect(screen.getByText(/Generation evidence was not recorded for this older draft/)).toBeTruthy();
  const post = fetcher.mock.calls.find(([, init]) => init?.method === "POST");
  expect((post?.[1]?.headers as Record<string, string>)["If-Match"]).toBe(
    '"4"',
  );
  expect(screen.getByText(/publishing re-checks it against the current inputs/)).toBeTruthy();
});

test("shows frozen names and stale warning after data changes", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([run])),
  );
  render(
    <Timetable
      ws={{ ...ws, version: 5, records: [] }}
      lang="en"
      administrator
      refresh={async () => {}}
    />,
  );
  expect(await screen.findByText(/Your inputs have changed/)).toBeTruthy();
  expect(screen.getAllByText("Algorithms")).toHaveLength(2);
});

test("Arabic draft displays actual time and translated generation control", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([run])),
  );
  render(
    <Timetable ws={ws} lang="ar" administrator refresh={async () => {}} />,
  );
  expect(await screen.findByText("الأحد")).toBeTruthy();
  expect(screen.getByRole("button", { name: "إنشاء الجدول" })).toBeTruthy();
});

test("viewer cannot request unpublished schedules", () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  render(
    <Timetable
      ws={ws}
      lang="en"
      administrator={false}
      refresh={async () => {}}
    />,
  );
  expect(fetcher).not.toHaveBeenCalled();
  expect(
    screen.queryByRole("button", { name: "Generate schedule" }),
  ).toBeNull();
});

test("icon-only layouts are accessible and persist across remounts", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([run])),
  );
  const view = render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  const columns = await screen.findByRole("button", {
    name: "Days across the top",
  });
  expect(columns.textContent).toBe("");
  fireEvent.click(columns);
  expect(columns.getAttribute("aria-pressed")).toBe("true");
  expect(localStorage.getItem("jadwai-schedule-layout")).toBe("columns");
  view.unmount();
  render(
    <Timetable ws={ws} lang="ar" administrator refresh={async () => {}} />,
  );
  expect(
    (
      await screen.findByRole("button", { name: "الأيام في الأعلى" })
    ).getAttribute("aria-pressed"),
  ).toBe("true");
});

test("layout works when storage reads and writes are denied", async () => {
  vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("denied");
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([run])),
  );
  render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  const left = await screen.findByRole("button", { name: "Days on the left" });
  expect(left.getAttribute("aria-pressed")).toBe("true");
  fireEvent.click(screen.getByRole("button", { name: "Days across the top" }));
  expect(left.getAttribute("aria-pressed")).toBe("false");
});

test("hostile multilingual text is rendered as text, never markup", async () => {
  const hostile = "<img src=x onerror=alert(1)> العربية 🧪 " + "W".repeat(100);
  const changed = structuredClone(run);
  changed.snapshot.records.find((r) => r.id === "a")!.name = hostile;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([changed])),
  );
  const view = render(
    <Timetable ws={ws} lang="ar" administrator refresh={async () => {}} />,
  );
  expect(await screen.findAllByText(hostile)).toHaveLength(2);
  expect(view.container.querySelector("img")).toBeNull();
});

test("network retries reuse the same generation key", async () => {
  const keys: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (_path: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        keys.push(JSON.parse(init.body as string).request_key);
        if (keys.length === 1) throw new Error("offline");
        return response(run);
      }
      return response([]);
    }),
  );
  render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  const button = await screen.findByRole("button", {
    name: "Generate schedule",
  });
  await waitFor(() =>
    expect((button as HTMLButtonElement).disabled).toBe(false),
  );
  fireEvent.click(button);
  await screen.findByRole("alert");
  fireEvent.click(button);
  await screen.findAllByText("Algorithms");
  expect(keys).toHaveLength(2);
  expect(keys[0]).toBe(keys[1]);
});

test("unknown search status never appears as proven infeasible", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      response([
        {
          ...run,
          status: "unknown",
          result: { reason: "search_limit", assignments: [] },
        },
      ]),
    ),
  );
  render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  expect(
    await screen.findByText(/This does not prove the inputs are impossible/, {
      selector: "p",
    }),
  ).toBeTruthy();
  expect(screen.queryByText("These inputs don’t fit together yet.")).toBeNull();
  expect(screen.queryByText("Supported checks passed")).toBeNull();
});

test("year and major filters narrow groups and clear dependent selections", async () => {
  const classified = structuredClone(run);
  classified.snapshot.records.find((r) => r.id === "g")!.year = 1;
  classified.snapshot.records.find((r) => r.id === "g")!.major =
    "Computer Science";
  classified.snapshot.records.push({
    id: "h",
    kind: "groups",
    name: "Group B",
    code: "B",
    year: 2,
    major: "Software Engineering",
    size: 20,
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([classified])),
  );
  render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  const year = await screen.findByRole("combobox", { name: "Study year" });
  fireEvent.change(year, { target: { value: "1" } });
  const group = screen.getByRole("combobox", {
    name: "Student group",
  }) as HTMLSelectElement;
  expect(
    [...group.options].some((o) => o.textContent?.includes("Group B")),
  ).toBe(false);
  fireEvent.change(screen.getByRole("combobox", { name: "Major" }), {
    target: { value: "Computer Science" },
  });
  fireEvent.change(group, { target: { value: "g" } });
  expect(screen.getAllByText("Algorithms")).toHaveLength(2);
  fireEvent.change(year, { target: { value: "2" } });
  expect(group.value).toBe("");
  expect(
    (screen.getByRole("combobox", { name: "Major" }) as HTMLSelectElement)
      .value,
  ).toBe("");
  expect(screen.queryByText("Algorithms")).toBeNull();
});

test("PDF print view includes only filtered sessions and preserves draft warnings", async () => {
  const data = structuredClone(run);
  data.snapshot.records.find((r) => r.id === "g")!.year = 1;
  data.snapshot.records.find((r) => r.id === "g")!.major = "Computer Science";
  data.snapshot.records.push({
    id: "h",
    kind: "groups",
    name: "Other group",
    code: "H",
    year: 2,
    major: "Other major",
    size: 20,
  });
  data.snapshot.records.push({
    id: "b",
    kind: "courses",
    name: "Hidden course",
    code: "B",
    sessions: 1,
    group_ids: ["h"],
  });
  data.result!.assignments.push({
    ...data.result!.assignments[0],
    activity_id: "b",
  });
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([data])),
  );
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  const view = render(
    <Timetable
      ws={{ ...ws, version: 5 }}
      lang="en"
      administrator
      refresh={async () => {}}
    />,
  );
  const year = await screen.findByRole("combobox", { name: "Study year" });
  fireEvent.change(year, { target: { value: "1" } });
  fireEvent.click(screen.getByRole("button", { name: "Save as PDF" }));
  expect(print).toHaveBeenCalledOnce();
  const exportView = document.querySelector(".schedule-print")!;
  expect(exportView.textContent).toContain("2 sessions");
  expect(exportView.textContent).toContain("Year 1");
  expect(exportView.textContent).toContain("Outdated draft");
  expect(exportView.textContent).toContain("DRAFT ONLY");
  expect(exportView.textContent).not.toContain("Hidden course");
  fireEvent(window, new Event("afterprint"));
  expect(document.querySelector(".schedule-print")).toBeNull();
  view.unmount();
});

test("Arabic PDF output retains multilingual names and timezone", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([run])),
  );
  vi.spyOn(window, "print").mockImplementation(() => {});
  render(
    <Timetable ws={ws} lang="ar" administrator refresh={async () => {}} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "حفظ بصيغة PDF" }));
  const exportView = document.querySelector(".schedule-print")!;
  expect(exportView.getAttribute("dir")).toBe("rtl");
  expect(exportView.textContent).toContain("الأحد");
  expect(exportView.textContent).toContain("Africa/Cairo");
  expect(exportView.querySelectorAll("tbody tr")).toHaveLength(2);
  fireEvent(window, new Event("afterprint"));
});

test("PDF places days on rows and configured time slots on columns", async () => {
  const data = structuredClone(run);
  const base = data.result!.assignments[0];
  data.result!.assignments = [
    { ...base, occurrence: 0 },
    { ...base, occurrence: 1 },
    { ...base, occurrence: 2, end_minute: 600 },
    { ...base, occurrence: 3, day: "Monday" },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([data])),
  );
  vi.spyOn(window, "print").mockImplementation(() => {});
  render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Save as PDF" }));
  const exported = document.querySelector(".schedule-print")!;
  expect(exported.querySelectorAll(".matrix-day-label")).toHaveLength(2);
  expect(exported.querySelectorAll("tbody tr")).toHaveLength(2);
  expect(exported.querySelectorAll(".matrix-session")).toHaveLength(4);
  expect(exported.querySelectorAll("thead th")).toHaveLength(21);
  const sessions = exported.querySelectorAll<HTMLElement>(".matrix-session");
  expect(sessions[0].style.gridColumn).toBe("1 / span 4");
  expect(sessions[1].style.gridColumn).toBe("1 / span 2");
  expect(sessions[0].style.gridRow).not.toBe(sessions[1].style.gridRow);
  expect(exported.querySelector(".matrix-free")).not.toBeNull();
  fireEvent(window, new Event("afterprint"));
});

test("historical seven-period snapshots retain their exact time columns", async () => {
  const data = structuredClone(run);
  data.snapshot.calendar.teaching_periods = [
    { start: 510, end: 600 },
    { start: 615, end: 705 },
    { start: 720, end: 810 },
    { start: 825, end: 915 },
    { start: 945, end: 1035 },
    { start: 1065, end: 1155 },
    { start: 1185, end: 1275 },
  ];
  data.snapshot.calendar.end_hour = 22;
  data.result!.assignments[0].start_minute = 510;
  data.result!.assignments[0].end_minute = 600;
  data.result!.assignments[1].start_minute = 1185;
  data.result!.assignments[1].end_minute = 1275;
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => response([data])),
  );
  vi.spyOn(window, "print").mockImplementation(() => {});
  render(
    <Timetable ws={ws} lang="en" administrator refresh={async () => {}} />,
  );
  fireEvent.click(await screen.findByRole("button", { name: "Save as PDF" }));
  const exported = document.querySelector(".schedule-print")!;
  expect(exported.querySelectorAll("thead th")).toHaveLength(8);
  expect(exported.textContent).toContain("First Period");
  expect(exported.textContent).toContain("Seventh Period");
  for (const text of [
    "08:30",
    "10:00",
    "10:15",
    "11:45",
    "12:00",
    "13:30",
    "13:45",
    "15:15",
    "15:45",
    "17:15",
    "17:45",
    "19:15",
    "19:45",
    "21:15",
  ])
    expect(exported.textContent).toContain(text);
  expect(
    exported.querySelectorAll<HTMLElement>(".matrix-session")[1].style
      .gridColumn,
  ).toBe("7 / span 1");
  fireEvent(window, new Event("afterprint"));
});

test("generation does not download a report; PDF downloads only on request", async () => {
  const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  const fetcher = vi.fn(async (path: string, init?: RequestInit) => {
    if (path.includes("/statistics?")) return {ok: true, status: 200};
    return response(init?.method === "POST" ? run : []);
  });
  vi.stubGlobal("fetch", fetcher);
  render(<Timetable ws={ws} lang="en" administrator refresh={async () => {}} />);
  const button = await screen.findByRole("button", {name: "Generate schedule"});
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(button);
  const download = await screen.findByRole("button", {name: "Download report PDF"});
  expect(click).not.toHaveBeenCalled();
  expect(fetcher.mock.calls.filter(([path]) => path.includes("/statistics?"))).toHaveLength(0);
  expect(screen.queryByRole("button", {name: "JSON"})).toBeNull();
  fireEvent.click(download);
  await waitFor(() => expect(click).toHaveBeenCalledOnce());
  expect(fetcher.mock.calls.filter(([path]) => path.includes("/statistics?format=pdf"))).toHaveLength(1);
});


test("current preset prints only five periods and no evening columns", async () => {
  const { REFERENCE_PERIODS } = await import("./referencePeriods");
  expect(REFERENCE_PERIODS).toHaveLength(5);
  const data = structuredClone(run);
  data.snapshot.calendar.teaching_periods = [...REFERENCE_PERIODS];
  data.snapshot.calendar.end_hour = 22;
  data.result!.assignments.forEach((a, i) => { a.start_minute = REFERENCE_PERIODS[i % 5].start; a.end_minute = REFERENCE_PERIODS[i % 5].end; });
  vi.stubGlobal("fetch", vi.fn(async () => response([data])));
  vi.spyOn(window, "print").mockImplementation(() => {});
  render(<Timetable ws={ws} lang="en" administrator refresh={async () => {}} />);
  fireEvent.click(await screen.findByRole("button", {name: "Save as PDF"}));
  const exported = document.querySelector(".schedule-print")!;
  expect(exported.querySelectorAll("thead th")).toHaveLength(6);
  expect(exported.textContent).toContain("Fifth Period");
  expect(exported.textContent).not.toContain("Sixth Period");
  expect(exported.textContent).not.toContain("Seventh Period");
  expect(exported.textContent).not.toContain("19:45");
  fireEvent(window, new Event("afterprint"));
});


test("print suggests a descriptive filename and restores the page title", async () => {
  document.title = "Original JadwAI title";
  vi.stubGlobal("fetch", vi.fn(async () => response([run])));
  const print = vi.spyOn(window, "print").mockImplementation(() => {});
  render(<Timetable ws={ws} lang="en" administrator refresh={async () => {}} />);
  fireEvent.click(await screen.findByRole("button", {name: "Save as PDF"}));
  expect(print).toHaveBeenCalledOnce();
  expect(document.title).toContain("JadwAI_");
  expect(document.title).toContain("_Timetable_All-Groups_Draft_");
  fireEvent(window, new Event("afterprint"));
  expect(document.title).toBe("Original JadwAI title");
});

test("assignment lock is saved as a draft with selected fields", async () => {
  const { LockSessionButton } = await import("./AssignmentLocks");
  const fetcher = vi.fn(async (_path: string, _init?: RequestInit) => new Response(JSON.stringify({ id: "lock", status: "draft" }), { status: 201, headers: { "Content-Type": "application/json" } }));
  vi.stubGlobal("fetch", fetcher);
  const refresh = vi.fn(async () => {});
  render(<LockSessionButton ws={ws} run={run} assignment={run.result!.assignments[0]} lang="en" refresh={refresh}/>);
  fireEvent.click(screen.getByRole("button", {name:/Keep session fixed/}));
  fireEvent.click(screen.getByRole("checkbox", {name:/Keep room/}));
  fireEvent.click(screen.getByRole("button", {name:"Save draft lock"}));
  await waitFor(() => expect(refresh).toHaveBeenCalledOnce());
  const [path, init] = fetcher.mock.calls[0];
  expect(path).toContain('/locks');
  expect(JSON.parse(init!.body as string)).toMatchObject({keep_instructor:true, keep_time:true, keep_room:false});
  expect(fetcher).toHaveBeenCalledOnce();
});


test("preflight reports blockers without starting generation", async () => {
  const { RunSettings, defaultSettings } = await import("./RunChecks");
  const fetcher=vi.fn(async(_path:string)=>response({input_version:4,ready:false,blockers:[{code:"no_suitable_room",message:"No room matches capacity.",activity_id:"a",rule_ids:[]}],warnings:[],activity_domains:[],definition:"Necessary checks only."}));
  vi.stubGlobal("fetch",fetcher);
  render(<RunSettings ws={ws} ar={false} settings={defaultSettings} change={()=>{}} disabled={false}/>);
  fireEvent.click(screen.getByRole("button",{name:"Check inputs"}));
  expect(await screen.findByText("No room matches capacity.",{exact:false})).toBeTruthy();
  expect(fetcher).toHaveBeenCalledOnce();
  expect(fetcher.mock.calls[0][0]).toContain("/preflight/current");
});

test("search settings change an explicit objective and time limit", async () => {
  const { RunSettings, defaultSettings } = await import("./RunChecks");
  const change=vi.fn();
  render(<RunSettings ws={ws} ar={false} settings={defaultSettings} change={change} disabled={false}/>);
  fireEvent.change(screen.getByLabelText("Time limit (seconds)"),{target:{value:"20"}});
  expect(change).toHaveBeenLastCalledWith({...defaultSettings,time_limit_seconds:20});
  fireEvent.change(screen.getByLabelText("Search objective"),{target:{value:"weighted-v1"}});
  expect(change).toHaveBeenLastCalledWith({...defaultSettings,objective_profile:"weighted-v1"});
});
