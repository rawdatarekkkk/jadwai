import { expect, test } from "vitest";
import { instructorCode } from "./components";

test("instructor codes come from position and initials and stay unique", () => {
  const records = [{ id: "1", kind: "instructors", code: "D-SS" }, { id: "2", kind: "rooms", code: "T-MA" }];
  expect(instructorCode("Dr. Sara Saleh", "doctor", records)).toBe("D-SS2");
  expect(instructorCode("Mona Adel", "ta", records)).toBe("T-MA");
  expect(instructorCode("Dr. Sara Saleh", "doctor", records, "1")).toBe("D-SS"); // editing keeps its own code free
});
