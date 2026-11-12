// @vitest-environment jsdom
import React, { useState } from "react";
import { afterEach, expect, test } from "vitest";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { DEFAULT_PLAN, ExamPlanSetup, examPlanBody, plannedExams, type ExamPlan } from "./ExamPlanSetup";
import type { Workspace } from "./api";
afterEach(cleanup);

const courses = [{ id: "c1", code: "CS101", name: "Programming", quiz_count: 2, second_chance: true }, { id: "c2", code: "MA101", name: "Math", quiz_count: 3, second_chance: false }];
const ws = { course_catalog: courses } as unknown as Workspace;
let latest: ExamPlan = DEFAULT_PLAN;
function Harness() { const [v, setV] = useState(DEFAULT_PLAN); latest = v; return <ExamPlanSetup ws={ws} ar={false} value={v} change={setV} />; }

test("each timetable lists the exams from the course plans", () => {
  const keys = (plan: Partial<ExamPlan>) => plannedExams({ ...DEFAULT_PLAN, ...plan }, courses as never).map(x => x.key);
  expect(keys({ kind: "midterm" })).toEqual(["c1:midterm", "c2:midterm"]);
  expect(keys({ kind: "final" })).toEqual(["c1:final", "c1:makeup", "c2:final"]);   // only CS101 offers a second chance
  expect(keys({ kind: "quiz", quizNumber: 3 })).toEqual(["c2:quiz3"]);              // CS101 has two quizzes
});

test("finals: untick an exam, set second-chance students, and see the reserved first slot", () => {
  render(<Harness />);
  fireEvent.click(screen.getByLabelText(/Finals/));
  expect(screen.getByText("2 exams")).toBeTruthy();                                   // second chances start unticked
  expect(screen.queryByLabelText("Students expected")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Tick all second chances" }));
  expect(screen.getByText("3 exams")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Untick all finals" }));
  expect(screen.getByText("1 exams")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Tick all finals" }));
  const cs = screen.getByText("Programming").closest(".exam-plan-row") as HTMLElement;
  fireEvent.change(within(cs).getByLabelText("Students expected"), { target: { value: "12" } });
  fireEvent.click(within(screen.getByText("Math").closest(".exam-plan-row") as HTMLElement).getByRole("checkbox"));
  expect(screen.getByText("2 exams")).toBeTruthy();
  expect(examPlanBody(latest)).toEqual({ kind: "final", quiz_number: 1, quiz_minutes: 30, starts: {}, skip: ["c2:final"], makeup_students: { c1: 12 } });
  expect(screen.getByText(/first slot of each day is for second-chance midterms/)).toBeTruthy();
  expect(screen.getByText("09:00–11:00")).toBeTruthy();  // second chance, 2 h
  expect(screen.getByText("11:30–14:30")).toBeTruthy();  // final, 3 h
});
