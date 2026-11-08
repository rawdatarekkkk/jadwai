// @vitest-environment jsdom
import React from "react";
import { afterEach, expect, test } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { RepairPanel } from "./RepairPanel";
afterEach(cleanup);

test("shows each verified fix with the sessions it moves", () => {
  render(<RepairPanel ar={false} repair={{ status: "fixable", verified: true, suggestions: [
    { kind: "move_session", target: "l2", title: "Move Biology (session 1)", message: "It is fixed at Sunday 08:00. Move it to Sunday 09:00 in Room S.", sessions: ["Biology (G) Sunday 09:00 in Room S with Dr. U"] }] }} />);
  expect(screen.getByText(/One change is enough\. Verified/)).toBeTruthy();
  expect(screen.getByText("Move Biology (session 1)")).toBeTruthy();
  expect(screen.getByText("Biology (G) Sunday 09:00 in Room S with Dr. U")).toBeTruthy();
});

test("explains when only a data change can help", () => {
  render(<RepairPanel ar={false} repair={{ status: "data_change_needed", message: "Even with every rule relaxed, no timetable fits.", findings: ["Required group teaching minutes exceed the week’s teaching capacity."] }} />);
  expect(screen.getByText(/Even with every rule relaxed/)).toBeTruthy();
  expect(screen.getByText(/exceed the week/)).toBeTruthy();
});
