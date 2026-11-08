import { expect, test } from "vitest";
import { question } from "./TypedConstraint";

test("parser question codes read as plain questions in both languages", () => {
  expect(question("day_required", false)).toBe("Which day? Add a day, or say “every day”.");
  expect(question("ambiguous_instructor", true)).toContain("اكتب الاسم كاملًا");
  expect(question("no_groups_in_year_4", false)).toBe("There are no groups in year 4.");
  expect(question("something_new", false)).toBe("something new");
});
