import { expect, test } from "vitest";
import { instructorCode } from "./components";

test("instructor codes come from position and initials and stay unique", () => {
  const records = [{ id: "1", kind: "instructors", code: "D-SS" }, { id: "2", kind: "rooms", code: "T-MA" }];
  expect(instructorCode("Dr. Sara Saleh", "doctor", records)).toBe("D-SS2");
  expect(instructorCode("Mona Adel", "ta", records)).toBe("T-MA");
  expect(instructorCode("Dr. Sara Saleh", "doctor", records, "1")).toBe("D-SS"); // editing keeps its own code free
});

test("group codes come from major, year and group number and stay unique", async () => {
  const { groupCode } = await import("./components");
  const records = [{ id: "1", kind: "groups", code: "BA3-G7" }];
  expect(groupCode("Business Administration", 3, "Business Administration Core G7", records)).toBe("BA3-G7-2");
  expect(groupCode("Finance, Banking & Accounting", 2, "FBA Group 4", records)).toBe("FBA2-G4");
  expect(groupCode("Business Administration", 3, "Core G7", records, "1")).toBe("BA3-G7");
});
