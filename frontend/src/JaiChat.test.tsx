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
