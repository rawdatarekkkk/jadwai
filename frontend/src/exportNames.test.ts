import { expect, test } from "vitest";
import { initials, shortScheduleName } from "./exportNames";

test("schedule names are short and descriptive", () => {
  expect(initials("Business Administration")).toBe("BA");
  expect(initials("Finance, Banking & Accounting")).toBe("FBA");
  expect(shortScheduleName({ name: "Business Administration Core G7", code: "BA5-G7", year: 3, major: "Business Administration" }, "", "")).toBe("BA Y3 G7 Schedule");
  expect(shortScheduleName(undefined, "3", "Business Administration")).toBe("BA Y3 Schedule");
  expect(shortScheduleName(undefined, "", "")).toBe("Full Schedule");
});
