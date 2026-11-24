import type { ReactNode } from "react";

// Mixed Arabic/English chat text. The browser's bidi algorithm reorders English words and numbers that
// sit next to each other inside an Arabic sentence (for example "08:30–10:00" shows as "10:00–08:30",
// or "Draft 3" drifts to the wrong end), so each English/number run is isolated in its own <bdi>.

const AR = /[؀-ۿ]/g;
const EN = /[A-Za-z]/g;
const TOKEN = "[A-Za-z0-9][A-Za-z0-9_%+'’]*";
const RUN = new RegExp(`${TOKEN}(?:[ .:/\\-–—,&+@#]+${TOKEN})*`, "g");

/** rtl when the text is mostly Arabic; a few English terms do not flip an Arabic line, and the reverse. */
export function textDir(text: string): "rtl" | "ltr" {
  const ar = (text.match(AR) || []).length;
  const en = (text.match(EN) || []).length;
  return ar > 0 && ar * 2 >= en ? "rtl" : "ltr";
}

/** One line of chat text: right direction, with English words and numbers kept in reading order. */
export function BidiLine({ text }: { text: string }): ReactNode {
  if (textDir(text) === "ltr") return text;
  const parts: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(RUN)) {
    const start = m.index ?? 0;
    if (start > last) parts.push(text.slice(last, start));
    // A run without spaces (a date, time range or code) must not wrap: a break at its hyphens would put
    // the two halves on different lines in the wrong order ("(2026-10-20" showed as "(-2026-10" + "20").
    const whole = !/\s/.test(m[0]);
    parts.push(<bdi key={start} dir="ltr" style={whole ? { whiteSpace: "nowrap" } : undefined}>{m[0]}</bdi>);
    last = start + m[0].length;
  }
  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
