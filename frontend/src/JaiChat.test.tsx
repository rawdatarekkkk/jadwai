// @vitest-environment jsdom
import { test, expect, vi, afterEach, beforeEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { JaiChat } from "./JaiChat";
import type { Workspace } from "./api";
import { timetableOnScreen } from "./Timetable";
beforeEach(() => { try { localStorage.clear(); } catch { /* none */ } });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const ws = { version: 7, records: [], rules: [], events: [], name: "Test", term: "Test" } as unknown as Workspace;
type Call = { path: string; method: string; body?: Record<string, unknown>; headers?: Record<string, string> };

function setup(answers: Record<string, unknown>[], extra: Record<string, unknown> = {}) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    const body = options?.body ? JSON.parse(String(options.body)) : undefined;
    const method = options?.method || "GET";
    calls.push({ path, method, body, headers: options?.headers as Record<string, string> });
    const json = path === "/api/assistant/configuration" ? { model: "qwen2.5:7b-instruct", local_model: true }
      : path === "/api/assistant" ? answers.shift()
      : path in extra ? extra[path]
      : path === "/api/assistant/chats" ? [] : path.endsWith("/done") ? { note: null } : { id: "run" };
    return { ok: true, status: 200, json: async () => json };
  }));
  const go = vi.fn(), close = vi.fn();
  render(<JaiChat ws={ws} lang="en" hidden={false} close={close} go={go} refresh={async () => {}} />);
  return { calls, go, close };
}
const reply = (text: string[], extra = {}) => ({ text, action: null, retry_with_model: false, source: "built-in", chat_id: "c1", message_id: `m${Math.random()}`, ...extra });
const type = (value: string) => { fireEvent.change(screen.getByLabelText("Message to JAI"), { target: { value } }); fireEvent.click(screen.getByRole("button", { name: "Send" })); };

test("a chat keeps its id, so the server keeps the context of follow-ups", async () => {
  const { calls } = setup([reply(["No: A3.128 is busy on Sunday 09:00:"]), reply(["Yes: A3.128 is free on Sunday 11:00."])]);
  expect(await screen.findByText(/qwen2.5:7b-instruct on this server/)).toBeTruthy();
  type("Is A3.128 free on Sunday at 9?");
  await screen.findByText("No: A3.128 is busy on Sunday 09:00:");
  type("is it free at 11?");
  await screen.findByText("Yes: A3.128 is free on Sunday 11:00.");
  const asks = calls.filter(c => c.path === "/api/assistant");
  expect(asks.map(c => c.body)).toEqual([{ text: "Is A3.128 free on Sunday at 9?" }, { text: "is it free at 11?", chat_id: "c1" }]);
  expect(localStorage.getItem("jadwai-jai-chat")).toBe("c1");
});

test("past chats are listed and reopened; New chat starts empty", async () => {
  const chats = [{ id: "old", title: "Is room A3.128 free?", updated_at: "2026-11-14T10:00:00Z" }];
  const { calls } = setup([reply(["Fresh answer"], { chat_id: "c2" })], {
    "/api/assistant/chats": chats,
    "/api/assistant/chats/old": { id: "old", messages: [{ id: "a", from: "you", text: "Is room A3.128 free?" }, { id: "b", from: "jai", text: ["Which day and time?"] }] },
  });
  fireEvent.click(await screen.findByRole("button", { name: "Chats" }));
  fireEvent.click(await screen.findByRole("button", { name: /^Is room A3.128 free\?/ }));
  expect(await screen.findByText("Which day and time?")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "New chat" }));
  expect(screen.queryByText("Which day and time?")).toBeNull();
  type("hello");
  await screen.findByText("Fresh answer");
  expect(calls.filter(c => c.path === "/api/assistant").at(-1)!.body).toEqual({ text: "hello" });  // no old chat id
});

test("a command runs only after confirming, and the chat records it", async () => {
  const action = { type: "generate", scope: [{ programme: "Business Administration", year: 3 }], label: "Generate" };
  const { calls, go } = setup([reply(["I will generate a draft timetable for Business Administration year 3."], { action, message_id: "m1" })], { "/api/workspace": { version: 7 } });
  fireEvent.click(await screen.findByRole("button", { name: "Generate the timetable for BA year 3" }));
  fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("timetable"));
  const post = calls.find(c => c.path === "/api/schedules")!;
  expect(post.body).toMatchObject({ scope: action.scope });
  expect(post.headers?.["If-Match"]).toBe('"7"');
  expect(calls.find(c => c.path === "/api/assistant/chats/c1/messages/m1/done")!.body).toEqual({ note: [expect.stringMatching(/^Started/)], cancelled: false, subject_kind: "schedules", subject_id: "run" });
  expect(screen.getByText(/Started. The solver is working/)).toBeTruthy();
});

test("unrecognised text goes to the local model in the same chat", async () => {
  const { calls } = setup([
    reply(["I didn't understand that.", "Asking the local model (qwen2.5:7b-instruct)…"], { retry_with_model: true }),
    reply(["Yes: A3.128 is free on Sunday 09:00."], { source: "local-model" }),
  ]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "anything on in the big hall sunday nine?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("Yes: A3.128 is free on Sunday 09:00.")).toBeTruthy();
  expect(screen.getByText("Understood by the local model")).toBeTruthy();
  expect(calls.filter(c => c.path === "/api/assistant").map(c => c.body)).toEqual([
    { text: "anything on in the big hall sunday nine?" }, { text: "anything on in the big hall sunday nine?", use_model: true, chat_id: "c1" }]);
});

test("JAI asks when unclear; an answer button or a typed answer replies", async () => {
  setup([
    reply(["All 10 groups of Business Administration year 3, or one group?"], { choices: [{ label: "All of year 3", text: "all of them" }, { label: "BA5-G7", text: "BA5-G7" }] }),
    reply(["I will generate a draft timetable for BA5-G7 only."], { action: { type: "generate", scope: [{ programme: "Business Administration", year: 3, group: "g7" }], label: "Generate" } }),
  ]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "i want a schedule for ba year 3" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await screen.findByRole("button", { name: "BA5-G7" });
  expect(screen.getByPlaceholderText("Pick an answer above, or type your own…")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "BA5-G7" }));
  expect(await screen.findByText("I will generate a draft timetable for BA5-G7 only.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "All of year 3" })).toBeNull();
});

test("adding a record is saved through the records endpoint after confirming", async () => {
  const body = { name: "Sara Ali", code: "T-SA", department: "Informatics", position: "ta", day_off: null, max_weekly_hours: null };
  const { calls, go } = setup([reply(["Add Sara Ali (TA, Informatics, no fixed day off) with code T-SA?"], { action: { type: "create_record", kind: "instructors", body, label: "Add it" }, message_id: "m9" })]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "add a TA named Sara Ali in Informatics, no day off" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Add it" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("data", "instructors"));
  expect(calls.find(c => c.path === "/api/records/instructors")!.body).toEqual(body);
  // The chat is now about the new instructor ("give her a day off", "create an account for her").
  expect(calls.find(c => c.path === "/api/assistant/chats/c1/messages/m9/done")!.body).toMatchObject({ subject_kind: "instructors", subject_id: "run" });
  expect(screen.getByText(/Next, add Sara Ali to the tutorials or labs of a course/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Open Course setup" }));
  expect(go).toHaveBeenLastCalledWith("data", "courses");
});


test("on the Timetable page each message says which draft and filters are on screen", async () => {
  Object.assign(timetableOnScreen, { run_id: "draft9", group: "g7" });
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    calls.push({ path, method: options?.method || "GET", body: options?.body ? JSON.parse(String(options.body)) : undefined });
    return { ok: true, status: 200, json: async () => (path === "/api/assistant" ? reply(["Here is the PDF for BA5-G7."]) : path === "/api/assistant/chats" ? [] : {}) };
  }));
  render(<JaiChat ws={ws} lang="en" hidden={false} close={() => {}} go={() => {}} refresh={async () => {}} screen="teaching" />);
  type("save as pdf");
  await screen.findByText("Here is the PDF for BA5-G7.");
  expect(calls.find(c => c.path === "/api/assistant")!.body).toEqual({ text: "save as pdf", screen: { page: "timetable", run_id: "draft9", group: "g7" } });
  for (const k of Object.keys(timetableOnScreen)) delete (timetableOnScreen as Record<string, unknown>)[k];
});


test("publishing runs only after confirming, through the publish endpoint", async () => {
  const { calls, go } = setup([reply(["Publish the timetable on your screen (448 sessions)?"], { action: { type: "publish", what: "teaching", run_id: "r9", label: "Publish" }, message_id: "m5" })]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "publish it" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Publish" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("timetable"));
  const post = calls.find(c => c.path === "/api/schedules/r9/publish")!;
  expect(post.method).toBe("POST");
  expect(post.headers?.["If-Match"]).toBe('"7"');
  expect(screen.getByText(/Published. Students and instructors now see it/)).toBeTruthy();
});

test("a typed constraint is added and approved through the constraints endpoints after confirming", async () => {
  const { calls } = setup([reply(["I read this as:", "• Dr. Sara · unavailable · Sunday 08:00–10:30 · required", "Add and approve it?"],
    { action: { type: "add_rules", text: "Dr. Sara can't teach Sunday before 10:30", count: 1, label: "Add and approve" }, message_id: "m7" })],
    { "/api/workspace": { version: 9 }, "/api/proposals/interpret": { id: "p1" }, "/api/proposals/p1/review": { rule_ids: ["rA"] } });
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "Dr. Sara can't teach Sunday before 10:30" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Add and approve" }));
  await screen.findByText(/Added and approved 1 rule/);
  expect(calls.filter(c => c.method === "POST" && c.path !== "/api/assistant" && !c.path.endsWith("/done")).map(c => c.path))
    .toEqual(["/api/proposals/interpret", "/api/proposals/p1/review", "/api/rules/rA/approve"]);
  expect(calls.find(c => c.path === "/api/rules/rA/approve")!.headers?.["If-Match"]).toBe('"9"');
});

test("creating an account shows the one-time setup link", async () => {
  setup([reply(["Create a student account for Omar Adel (BA5-G7), omar@x.test?"], { action: { type: "create_account", body: { name: "Omar Adel", email: "omar@x.test", role: "student", group_id: "g7" }, label: "Create account" }, message_id: "m8" })],
    { "/api/users": { user: {}, reset: { token: "tok123" } } });
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "create a student account for omar" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Create account" }));
  expect(await screen.findByText(`${window.location.origin}/#reset=tok123`)).toBeTruthy();
});

test("'open X' goes to the page straight away", async () => {
  const { go } = setup([reply(["Opening Accounts."], { action: { type: "open", page: "accounts", label: "Open Accounts" }, auto_open: true })]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "open the accounts page" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("accounts", undefined));
});

test("a part is published into the published timetable after confirming", async () => {
  const { calls } = setup([reply(["This draft covers only BA5-G7. I can publish it into the published timetable…"], { action: { type: "publish_merged", run_id: "part1", label: "Publish into the published timetable" }, message_id: "m3" })],
    { "/api/workspace": { version: 12 } });
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "publish it" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Publish into the published timetable" }));
  await screen.findByText(/everyone else's week is unchanged/);
  const post = calls.find(c => c.path === "/api/schedules/part1/publish-merged")!;
  expect(post.body).toMatchObject({ request_key: expect.any(String) });
  expect(post.headers?.["If-Match"]).toBe('"12"');
});

test("a new course is saved like Course setup does: the course, then its sessions", async () => {
  const catalog = { name: "Network Security", code: "SEC301", eligibility: { lecture: ["d1"], tutorial: [], lab: ["t1"] }, group_ids: ["g4"], quiz_count: 3, second_chance: true };
  const activities = [{ code: "SEC301-L", activity_type: "lecture" }, { code: "SEC301-LAB-G4", activity_type: "lab" }];
  const { calls, go } = setup([reply(["Create Network Security (SEC301) for IS3-G4:"], { action: { type: "create_course", catalog, activities, label: "Create course" }, message_id: "m4" })],
    { "/api/workspace": { version: 5 }, "/api/course-catalog": { id: "cat9" } });
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "create a new course" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Create course" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("data", "courses"));
  const saves = calls.filter(c => c.method === "POST" && (c.path === "/api/course-catalog" || c.path === "/api/records/courses"));
  expect(saves.map(c => c.path)).toEqual(["/api/course-catalog", "/api/records/courses", "/api/records/courses"]);
  expect(saves[1].body).toEqual({ ...activities[0], course_id: "cat9" });
  expect(screen.getByText(/Created Network Security with 2 teaching sessions/)).toBeTruthy();
});

test("a new group joins its cohort's courses in one confirm, then generating is offered", async () => {
  const items = [{ course_id: "c1", catalog: { code: "ALG201" }, updates: [{ id: "a1", body: { code: "ALG201-L" } }], creates: [{ code: "ALG201-G2" }] },
                 { course_id: "c2", catalog: { code: "DB202" }, updates: [], creates: [{ code: "DB202-LAB-G2" }] }];
  const { calls } = setup([reply(["CS2-G2 is not in any course yet…"], { action: { type: "update_courses", items, group_code: "CS2-G2", label: "Add to these 2 courses" }, message_id: "m6" })],
    { "/api/workspace": { version: 3 } });
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "create a schedule for them" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Add to these 2 courses" }));
  expect(await screen.findByRole("button", { name: "Generate its timetable" })).toBeTruthy();
  const writes = calls.filter(c => ["PUT", "POST"].includes(c.method) && (c.path.startsWith("/api/course-catalog") || c.path.startsWith("/api/records/courses"))).map(c => `${c.method} ${c.path}`);
  expect(writes).toEqual(["PUT /api/course-catalog/c1", "PUT /api/records/courses/a1", "POST /api/records/courses", "PUT /api/course-catalog/c2", "POST /api/records/courses"]);
});

test("Fix and generate applies the fixes in order, then starts the generation", async () => {
  const steps = [{ method: "PUT", path: "/records/groups/g4", body: { size: 30 } }, { method: "PUT", path: "/records/courses/l1", body: { code: "ALG201-L-I" } },
                 { method: "POST", path: "/records/courses", body: { code: "ALG201-L-II" } }];
  const then = { type: "generate", scope: [{ programme: "CS", year: 2 }], label: "Generate" };
  const { calls, go } = setup([reply(["Before generating CS year 2: 2 session(s) couldn't be scheduled as things are."], { action: { type: "apply_changes", steps, then, label: "Fix and generate" }, message_id: "m2" })],
    { "/api/workspace": { version: 4 } });
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "generate the timetable for CS year 2" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Fix and generate" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("timetable"));
  const writes = calls.filter(c => ["PUT", "POST"].includes(c.method) && !c.path.startsWith("/api/assistant")).map(c => `${c.method} ${c.path}`);
  expect(writes).toEqual(["PUT /api/records/groups/g4", "PUT /api/records/courses/l1", "POST /api/records/courses", "POST /api/schedules"]);
  expect(screen.getByText(/Fixed: 3 changes saved/)).toBeTruthy();
});

test("a fix can create a record and use its id in the next steps", async () => {
  const steps = [{ method: "POST", path: "/records/groups", body: { code: "CS2-G3" }, save_as: "new" },
                 { method: "PUT", path: "/records/courses/l1", body: { group_ids: ["g1", "$new"] } }];
  const { calls } = setup([reply(["Split CS2-G2 into two?"], { action: { type: "apply_changes", steps, then: null, label: "Split it" }, message_id: "m1" })],
    { "/api/workspace": { version: 2 }, "/api/records/groups": { id: "g3" } });
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "split CS2-G2 into two groups" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Split it" }));
  await screen.findByText(/Fixed: 2 changes saved/);
  expect(calls.find(c => c.path === "/api/records/courses/l1")!.body).toEqual({ group_ids: ["g1", "g3"] });
});


test("a refused move says what the server found and offers other options", async () => {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    calls.push({ path, method: options?.method || "GET", body: options?.body ? JSON.parse(String(options.body)) : undefined });
    if (path.endsWith("/edits")) return { ok: false, status: 422, json: async () => ({ detail: { code: "edit_breaks_rules", errors: ["resource_conflicts"] } }) };
    const json = path === "/api/assistant" ? reply(["Move Programming III to Sunday 12:00?"], { action: { type: "move_session", run_id: "r1", change: { activity_id: "a", occurrence: 0 }, label: "Move it" } })
      : path === "/api/workspace" ? { version: 3 } : path === "/api/assistant/chats" ? [] : {};
    return { ok: true, status: 200, json: async () => json };
  }));
  render(<JaiChat ws={ws} lang="en" hidden={false} close={() => {}} go={() => {}} refresh={async () => {}} />);
  type("move first slot on monday to third on sunday");
  fireEvent.click(await screen.findByRole("button", { name: "Move it" }));
  expect(await screen.findByText("It found: a room, instructor or group would be in two places at once.")).toBeTruthy();
  expect(screen.getByRole("button", { name: "Show other options" })).toBeTruthy();
});

test("a draft made before the latest changes says so plainly and offers to generate again", async () => {
  vi.stubGlobal("fetch", vi.fn(async (path: string) => {
    if (path.endsWith("/publish-merged")) return { ok: false, status: 409, json: async () => ({ detail: { code: "merge_validation_failed", errors: ["complete_assignment"] } }) };
    const json = path === "/api/assistant" ? reply(["This draft covers only ACSI2-G19…"], { action: { type: "publish_merged", run_id: "p1", label: "Publish into the published timetable", again: "generate a timetable for ACSI2-G19" } })
      : path === "/api/workspace" ? { version: 3 } : path === "/api/assistant/chats" ? [] : {};
    return { ok: true, status: 200, json: async () => json };
  }));
  render(<JaiChat ws={ws} lang="en" hidden={false} close={() => {}} go={() => {}} refresh={async () => {}} />);
  type("okay publish schedule");
  fireEvent.click(await screen.findByRole("button", { name: "Publish into the published timetable" }));
  expect(await screen.findByText(/this draft was made before the latest changes/)).toBeTruthy();
  expect(screen.getByRole("button", { name: "Generate it again" })).toBeTruthy();
});

test("a timetable built in parts sends all the parts in one request", async () => {
  const action = { type: "generate", scope: [{ programme: "A", year: null }], then: [[{ programme: "B", year: null }], [{ programme: "C", year: null }]],
                   settings: { time_limit_seconds: 240, search_workers: 4 }, label: "Generate in 3 parts" };
  const { calls } = setup([reply(["The whole university is 774 sessions…"], { action, message_id: "m1" })], { "/api/workspace": { version: 8 } });
  type("generate the whole university timetable");
  fireEvent.click(await screen.findByRole("button", { name: "Generate in 3 parts" }));
  await screen.findByText(/Started part 1 of 3/);
  expect(calls.find(c => c.path === "/api/schedules")!.body).toMatchObject({ scope: action.scope, then: action.then, settings: action.settings });
});

test("summarises website results without leaking credential fields", async () => {
  const { describeWebsiteResult } = await import("./JaiChat");
  const lines = describeWebsiteResult([{name: "Sara", role: "student", password: "secret", reset: {token: "private"}}], en => en);
  expect(lines.join(" ")).toContain("Sara");
  expect(lines.join(" ")).not.toContain("secret");
  expect(lines.join(" ")).not.toContain("private");
});

test("typed confirmation executes the latest proposed website action with its original version", async () => {
  const { calls } = setup([reply(["Change the room to 90 seats?"], {action: {type: "website_request", method: "PUT", path: "/records/rooms/r1", body: {capacity: 90}, version: 7, label: "Review and run"}})]);
  type("Set the room capacity to 90");
  await screen.findByText("Change the room to 90 seats?");
  await waitFor(() => expect(screen.getByRole("button", {name: "Review and run"}).hasAttribute("disabled")).toBe(false));
  type("yes, do it");
  // A qualified confirmation with a comma is still the same explicit acceptance.
  await waitFor(() => expect(calls.some(c => c.path === "/api/records/rooms/r1")).toBe(true));
  expect(calls.find(c => c.path === "/api/records/rooms/r1")?.headers?.["If-Match"]).toBe('"7"');
  expect(calls.filter(c => c.path === "/api/assistant")).toHaveLength(1);
});

test("website result references preserve ordering and remove private fields", async () => {
  const { websiteResultContext } = await import("./JaiChat");
  expect(websiteResultContext([{id: "first", name: "Sara", password: "private"}, {id: "second", name: "Omar", reset: {token: "private"}}]))
    .toEqual([{id: "first", name: "Sara"}, {id: "second", name: "Omar"}]);
});

test("exam confirmation uses the real endpoint, retains scope, and remembers the resulting exam", async () => {
  const action = {type: "exam", scope_verified: true, body: {kind: "midterm", start_date: "2026-12-20", end_date: "2026-12-31", course_ids: ["ba-course"]}, label: "Create exam timetable", version: 7};
  const {calls,go}=setup([reply(["Create the BA midterm draft?"],{action,message_id:"exam-message"})],{"/api/exam-schedules":{id:"exam1",result:{status:"completed",validation:{passed:true}}}});
  type("create a midterm schedule for BA");
  fireEvent.click(await screen.findByRole("button",{name:"Create exam timetable"}));
  await screen.findByText(/The exam timetable draft is ready/);
  const post=calls.find(c=>c.path==="/api/exam-schedules")!;
  expect(post.body).toEqual(action.body);
  expect(post.headers?.["If-Match"]).toBe('"7"');
  expect(calls.some(c=>c.path==="/api/exams")).toBe(false);
  expect(calls.find(c=>c.path.endsWith("exam-message/done"))!.body).toMatchObject({subject_kind:"exam_schedules",subject_id:"exam1"});
  expect(go).toHaveBeenCalledWith("exams");
});

test("an infeasible exam attempt is reported honestly", async()=>{
  setup([reply(["Create exam draft?"],{action:{type:"exam",scope_verified:true,body:{kind:"midterm"},label:"Create exam timetable"}})],{"/api/exam-schedules":{id:"failed1",result:{status:"infeasible",reason:"not_enough_days"}}});
  type("create an exam draft");
  fireEvent.click(await screen.findByRole("button",{name:"Create exam timetable"}));
  await screen.findByText(/exam attempt was saved with status infeasible/);
  expect(screen.queryByText(/The exam timetable draft is ready/)).toBeNull();
});

test("locally interpreted chat rules are saved exactly as reviewed without reinterpretation",async()=>{
  const rules=[{title:"Later tutorials",type:"teaching_preferred",strength:"preferred",day:null,start_hour:10,end_hour:18,params:{activity_types:["tutorial"]}}];
  const {calls}=setup([reply(["Prefer tutorials after 10:00. Add and approve?"],{action:{type:"add_rules",text:"Ideally tutorials after ten",rules,count:1,label:"Add and approve",version:7}})],{"/api/workspace":{version:7},"/api/proposals":{id:"p-local"},"/api/proposals/p-local/review":{rule_ids:["local-rule"]}});
  type("Ideally tutorials after ten");
  expect(calls.some(c=>c.path==="/api/rules/local-rule/approve")).toBe(false);
  fireEvent.click(await screen.findByRole("button",{name:"Add and approve"}));
  await screen.findByText(/Added and approved 1 rule/);
  expect(calls.find(c=>c.path==="/api/proposals"&&c.method==="POST")!.body).toMatchObject({output:{decision:"ready",proposals:[{kind:"rule",data:rules[0]}]}});
  expect(calls.some(c=>c.path==="/api/proposals/interpret")).toBe(false);
});

test("older exam proposals cannot silently generate an unscoped timetable",async()=>{
  const {calls}=setup([reply(["Old exam proposal"],{action:{type:"exam",body:{kind:"midterm"},label:"Create old exam"}})]);
  type("retry my old exam request");
  fireEvent.click(await screen.findByRole("button",{name:"Create old exam"}));
  await screen.findByText(/older exam proposal needs its programme scope checked again/);
  expect(calls.some(c=>c.path==="/api/exam-schedules")).toBe(false);
});
