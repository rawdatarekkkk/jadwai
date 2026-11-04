// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
  waitFor,
} from "@testing-library/react";
import App from "./App";
import { ResetAccess } from "./Accounts";
import { words } from "./i18n";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.localStorage.clear();
  window.history.replaceState(null, "", "/");
});
const user = {
  id: "admin",
  name: "Admin",
  email: "admin@example.test",
  role: "administrator",
  active: true,
  version: 1,
};
const workspace = {
  name: "CS",
  term: "Fall",
  version: 1,
  records: [
    {
      id: "room",
      kind: "rooms",
      name: "Room A",
      code: "A",
      capacity: 30,
      room_type: "lecture",
    },
  ],
  rules: [],
  events: [],
};
function response(body: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => structuredClone(body),
  };
}

test("session expiry preserves a draft through reauthentication", async () => {
  let expired = false;
  const fetcher = vi.fn(
    async (path: string, options: { method: string; body?: string }) => {
      if (path === "/api/auth/me") return response(user);
      if (path === "/api/workspace") return response(workspace);
      if (path === "/api/auth/login") {
        expired = false;
        return response(user);
      }
      if (path === "/api/records/rooms/room" && options.method === "PUT") {
        expired = true;
        return response({ detail: "session_expired" }, 401);
      }
      throw new Error("Unexpected path " + path);
    },
  );
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  await screen.findByRole("heading", { name: "A clearer week starts here." });
  fireEvent.click(screen.getByRole("button", { name: "Academic data" }));
  fireEvent.click(screen.getByRole("button", { name: /^Rooms\s*1$/ }));
  fireEvent.click(screen.getByRole("button", { name: "Edit" }));
  fireEvent.change(screen.getByLabelText("Name", { exact: true }), {
    target: { value: "Unsaved revised room" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
  const overlay = await screen.findByRole("dialog", {
    name: "Sign in to continue",
  });
  expect(expired).toBe(true);
  fireEvent.change(
    within(overlay).getByLabelText("Password", { exact: true }),
    { target: { value: "test-password-123" } },
  );
  fireEvent.click(
    within(overlay).getByRole("button", {
      name: "Enter workspace",
    }),
  );
  await waitFor(() =>
    expect(
      screen.queryByRole("dialog", { name: "Sign in to continue" }),
    ).toBeNull(),
  );
  expect(
    (screen.getByLabelText("Name", { exact: true }) as HTMLInputElement).value,
  ).toBe("Unsaved revised room");
  expect(expired).toBe(false);
});

test("password reset checks matching values before transmitting token", async () => {
  const fetcher = vi.fn();
  vi.stubGlobal("fetch", fetcher);
  render(
    <ResetAccess
      token="one-time-token"
      t={(key) => words.en[key]}
      lang="en"
      onDone={() => {}}
    />,
  );
  fireEvent.change(screen.getByLabelText("New password", { exact: true }), {
    target: { value: "first-password-123" },
  });
  fireEvent.change(
    screen.getByLabelText("Confirm new password", { exact: true }),
    { target: { value: "other-password-123" } },
  );
  fireEvent.click(screen.getByRole("button", { name: "Set your password" }));
  expect(screen.getByRole("alert").textContent).toContain("do not match");
  expect(fetcher).not.toHaveBeenCalled();
});

test("CSV commit uses the preview version and waits for a valid preview", async () => {
  const { ImportData } = await import("./ImportData");
  const imported = vi.fn(async () => {}),
    close = vi.fn();
  const fetcher = vi.fn(async (path: string) =>
    path.endsWith("/preview")
      ? response({
          version: 12,
          valid: true,
          count: 1,
          rows: [
            {
              line: 2,
              valid: true,
              data: { name: "Room B", code: "B" },
              errors: [],
            },
          ],
        })
      : response({ count: 1, version: 13 }, 201),
  );
  vi.stubGlobal("fetch", fetcher);
  render(
    <ImportData
      kind="rooms"
      t={(key) => words.en[key]}
      lang="en"
      close={close}
      onImported={imported}
    />,
  );
  expect(
    (screen.getByRole("button", { name: "Preview rows" }) as HTMLButtonElement)
      .disabled,
  ).toBe(true);
  const file = new File(
    ["name,code,capacity,room_type\nRoom B,B,30,lecture\n"],
    "rooms.csv",
    { type: "text/csv" },
  );
  Object.defineProperty(file, "text", {
    value: async () => "name,code,capacity,room_type\nRoom B,B,30,lecture\n",
  });
  fireEvent.change(screen.getByLabelText("Choose a CSV file"), {
    target: { files: [file] },
  });
  await waitFor(() =>
    expect(
      (
        screen.getByRole("button", {
          name: "Preview rows",
        }) as HTMLButtonElement
      ).disabled,
    ).toBe(false),
  );
  fireEvent.click(screen.getByRole("button", { name: "Preview rows" }));
  fireEvent.click(
    await screen.findByRole("button", { name: "Import all rows" }),
  );
  await waitFor(() => expect(imported).toHaveBeenCalledOnce());
  expect(fetcher).toHaveBeenLastCalledWith(
    "/api/imports/rooms/commit",
    expect.objectContaining({
      headers: expect.objectContaining({ "If-Match": '"12"' }),
    }),
  );
  expect(close).toHaveBeenCalledOnce();
});

test("room and group availability forms submit only the chosen typed target", async () => {
  const { RuleForm } = await import("./components");
  const submit = vi.fn();
  const ws = {...workspace, records: [
    ...workspace.records,
    {id: "teacher", kind: "instructors", name: "Teacher", code: "T"},
    {id: "group", kind: "groups", name: "Year 2 Group A", code: "G", size: 20},
  ]} as import("./api").Workspace;
  render(<RuleForm ws={ws} t={k => words.en[k]} busy={false} cancel={() => {}} submit={submit}/>);
  fireEvent.change(screen.getByLabelText("Rule title"), {target: {value: "Closed"}});
  fireEvent.change(screen.getByLabelText("Requirement type"), {target: {value: "room_unavailable"}});
  expect(screen.getByLabelText("Rooms").textContent).toContain("Room A");
  fireEvent.click(screen.getByRole("button", {name: "Save changes"}));
  expect(submit).toHaveBeenLastCalledWith(expect.objectContaining({type: "room_unavailable", room_id: "room", strength: "mandatory"}));
  expect(submit.mock.calls[0][0]).not.toHaveProperty("instructor_id");
  fireEvent.change(screen.getByLabelText("Requirement type"), {target: {value: "group_unavailable"}});
  fireEvent.click(screen.getByRole("button", {name: "Save changes"}));
  expect(submit).toHaveBeenLastCalledWith(expect.objectContaining({type: "group_unavailable", group_id: "group", strength: "mandatory"}));
});

test("instructor form explains the 12-hour standard and extra time", async () => {
  const { RecordForm } = await import("./components");
  render(<RecordForm kind="instructors" ws={workspace as import("./api").Workspace} t={k => words.en[k]} busy={false} cancel={() => {}} submit={vi.fn()}/>);
  expect(screen.getByText(/Standard weekly teaching hours: 12/)).toBeTruthy();
  expect(screen.getByText(words.en.overtimeHelp)).toBeTruthy();
  expect(screen.queryByRole("spinbutton")).toBeNull();
});

test("practical-day settings use explicit editable demo caps and can be disabled", async () => {
  const { CalendarSettings } = await import("./CalendarSettings");
  const save = vi.fn(async () => {});
  const {container} = render(<CalendarSettings ws={workspace as import("./api").Workspace} t={k => words.en[k]} lang="en" save={save} busy={false}/>);
  fireEvent.click(screen.getByRole("checkbox", {name: "Enable practical-day scheduling policy"}));
  expect((screen.getByLabelText("Student daily teaching hours") as HTMLInputElement).value).toBe("6");
  expect((screen.getByLabelText("Instructor daily teaching hours") as HTMLInputElement).value).toBe("6");
  fireEvent.submit(container.querySelector("form")!);
  expect(save).toHaveBeenLastCalledWith(expect.objectContaining({realism_policy: {student_daily_hours:6,instructor_daily_hours:6,spread_activity_days:true,max_consecutive_periods:3,max_idle_periods:1,compact_days:true}}));
  fireEvent.click(screen.getByRole("checkbox", {name: "Enable practical-day scheduling policy"}));
  fireEvent.submit(container.querySelector("form")!);
  expect(save).toHaveBeenLastCalledWith(expect.objectContaining({realism_policy: {}}));
});
