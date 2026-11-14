// @vitest-environment jsdom
import { test, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/react";
import { JaiChat } from "./JaiChat";
import type { Workspace } from "./api";
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const ws = { version: 7, records: [], rules: [], events: [], name: "Test", term: "Test" } as unknown as Workspace;
type Call = { path: string; body?: Record<string, unknown>; headers?: Record<string, string> };

function setup(answers: Record<string, unknown>[]) {
  const calls: Call[] = [];
  vi.stubGlobal("fetch", vi.fn(async (path: string, options?: RequestInit) => {
    const body = options?.body ? JSON.parse(String(options.body)) : undefined;
    calls.push({ path, body, headers: options?.headers as Record<string, string> });
    const json = path === "/api/assistant/configuration" ? { model: "qwen2.5:7b-instruct", local_model: true } : path === "/api/assistant" ? answers.shift() : { id: "run" };
    return { ok: true, status: 200, json: async () => json };
  }));
  const go = vi.fn(), close = vi.fn();
  render(<JaiChat ws={ws} lang="en" hidden={false} close={close} go={go} refresh={async () => {}} />);
  return { calls, go, close };
}
const reply = (text: string[], extra = {}) => ({ text, action: null, retry_with_model: false, meaning: { intent: "room_schedule", slots: { days: ["Sunday"] } }, source: "built-in", ...extra });

test("answers a question and sends the previous meaning with a follow-up", async () => {
  const { calls } = setup([reply(["Yes: A3.128 is free on Sunday 10:00."]), reply(["Yes: A3.128 is free on Monday 10:00."])]);
  expect(await screen.findByText(/qwen2.5:7b-instruct on this server/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Message to JAI"), { target: { value: "Is A3.128 free on Sunday at 10?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("Yes: A3.128 is free on Sunday 10:00.")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Message to JAI"), { target: { value: "and on Monday?" } });
  fireEvent.keyDown(screen.getByLabelText("Message to JAI"), { key: "Enter" });
  expect(await screen.findByText("Yes: A3.128 is free on Monday 10:00.")).toBeTruthy();
  const asks = calls.filter(c => c.path === "/api/assistant");
  expect(asks[1].body).toEqual({ text: "and on Monday?", previous: { intent: "room_schedule", slots: { days: ["Sunday"] } } });
});

test("a command runs only after confirming, through the website's own endpoint", async () => {
  const action = { type: "generate", scope: [{ programme: "Business Administration", year: 3 }], label: "Generate" };
  const { calls, go } = setup([reply(["I will generate a draft timetable for Business Administration year 3."], { action })]);
  fireEvent.click(await screen.findByRole("button", { name: "Generate the timetable for BA year 3" }));
  fireEvent.click(await screen.findByRole("button", { name: "Generate" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("timetable"));
  const post = calls.find(c => c.path === "/api/schedules")!;
  expect(post.body).toMatchObject({ scope: action.scope });
  expect(post.headers?.["If-Match"]).toBe('"7"');
  expect(screen.getByText(/Started. The solver is working/)).toBeTruthy();
});

test("unrecognised text goes to the local model and says so", async () => {
  const { calls } = setup([
    reply(["I didn't understand that.", "Asking the local model (qwen2.5:7b-instruct)…"], { retry_with_model: true, meaning: null }),
    reply(["Yes: A3.128 is free on Sunday 09:00."], { source: "local-model" }),
  ]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "anything on in the big hall sunday nine?" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  expect(await screen.findByText("Yes: A3.128 is free on Sunday 09:00.")).toBeTruthy();
  expect(screen.getByText("Understood by the local model")).toBeTruthy();
  expect(calls.filter(c => c.path === "/api/assistant").map(c => c.body?.use_model)).toEqual([undefined, true]);
});

test("JAI asks when it is unclear, and an answer button replies with the request still in mind", async () => {
  const asking = { intent: "generate_timetable", slots: { programmes: ["Business Administration"], year: 3 }, asking: true };
  const { calls } = setup([
    reply(["All 10 groups of Business Administration year 3, or one group?"], { meaning: asking, choices: [{ label: "All of year 3", text: "all of them" }, { label: "BA5-G7", text: "BA5-G7" }] }),
    reply(["I will generate a draft timetable for BA5-G7 only."], { action: { type: "generate", scope: [{ programme: "Business Administration", year: 3, group: "g7" }], label: "Generate" } }),
  ]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "i want a schedule for ba year 3" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await screen.findByRole("button", { name: "BA5-G7" });
  expect(screen.getByPlaceholderText("Pick an answer above, or type your own…")).toBeTruthy();  // typing stays open
  fireEvent.click(screen.getByRole("button", { name: "BA5-G7" }));
  expect(await screen.findByText("I will generate a draft timetable for BA5-G7 only.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "All of year 3" })).toBeNull();  // old answers go once answered
  expect(calls.filter(c => c.path === "/api/assistant")[1].body).toEqual({ text: "BA5-G7", previous: asking });
});

test("adding a record is asked step by step, then saved through the records endpoint after confirming", async () => {
  const body = { name: "Sara Ali", code: "T-SA", department: "Informatics", position: "ta", day_off: null, max_weekly_hours: null };
  const { calls, go } = setup([
    reply(["Sure, let us add an instructor.", "What is the instructor's full name?"], { meaning: { intent: "create_record", slots: { kind: "instructors", form: {}, field: "name" }, asking: true } }),
    reply(["Add Sara Ali (TA, Informatics, no fixed day off) with code T-SA?"], { action: { type: "create_record", kind: "instructors", body, label: "Add it" } }),
  ]);
  fireEvent.change(await screen.findByLabelText("Message to JAI"), { target: { value: "create an instructor" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  await screen.findByText("What is the instructor's full name?");
  fireEvent.change(screen.getByLabelText("Message to JAI"), { target: { value: "Sara Ali" } });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));
  fireEvent.click(await screen.findByRole("button", { name: "Add it" }));
  await waitFor(() => expect(go).toHaveBeenCalledWith("data", "instructors"));
  const post = calls.find(c => c.path === "/api/records/instructors")!;
  expect(post.body).toEqual(body);
  expect(screen.getByText(/Added the instructor T-SA/)).toBeTruthy();
});
