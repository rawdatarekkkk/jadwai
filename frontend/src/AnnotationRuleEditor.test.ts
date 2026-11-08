import { expect, test } from "vitest";
import { annotationRule } from "./AnnotationRuleEditor";

const context = { id: "c", calendar: { days: ["Sunday"], start_hour: 8, end_hour: 18 }, instructors: [{ id: "sara", name: "Dr. Sara Saleh" }], rooms: [], groups: [], activities: [] };
const draft = { type: "unavailable", target: "sara", day: "Sunday", start: "8", end: "10.5" };

test("proposal review keeps half hours; the evaluation guide stays on whole hours", () => {
  expect(annotationRule(draft, context, 0.5)?.data.end_hour).toBe(10.5);
  expect(annotationRule(draft, context)).toBeNull();
});
