// @vitest-environment jsdom
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { BidiLine, textDir } from "./bidi";

describe("mixed Arabic and English chat text", () => {
  it("picks the direction from the main language, not from the first word", () => {
    expect(textDir("Draft 3 فيها 212 حصة، تقصد أنهي جروب؟")).toBe("rtl");
    expect(textDir("Use the Student groups page, then press حفظ.")).toBe("ltr");
    expect(textDir("No sessions at 08:30.")).toBe("ltr");
  });

  it("isolates English words, codes and time ranges inside an Arabic line", () => {
    const { container } = render(<p><BidiLine text="الحصة من 08:30–10:00 في Room H12، والـ solver بيحترم Check inputs." /></p>);
    const runs = [...container.querySelectorAll("bdi")].map(b => [b.textContent, b.getAttribute("dir")]);
    expect(runs).toEqual([["08:30–10:00", "ltr"], ["Room H12", "ltr"], ["solver", "ltr"], ["Check inputs", "ltr"]]);
    expect(container.textContent).toBe("الحصة من 08:30–10:00 في Room H12، والـ solver بيحترم Check inputs.");
  });

  it("leaves English lines untouched", () => {
    const { container } = render(<p><BidiLine text="Draft 3 has 212 sessions." /></p>);
    expect(container.querySelector("bdi")).toBeNull();
  });
});
