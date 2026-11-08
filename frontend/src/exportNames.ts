const SMALL_WORDS = new Set(["and", "of", "the", "for", "in", "&"]);
/** "Business Administration" -> "BA" (same rule as the server's PDF name). */
export const initials = (name: string) =>
  name.split(/[\s,/&-]+/).filter((w) => w && !SMALL_WORDS.has(w.toLowerCase())).map((w) => w[0].toUpperCase()).join("") || name.slice(0, 3);

/** Short, descriptive name: "BA Y3 G7 Schedule", "BA Y3 Schedule", "Full Schedule". */
export function shortScheduleName(group: { name?: string; code?: string; year?: number | null; major?: string | null } | undefined, year: string, major: string) {
  const groupNumber = (g: { name?: string; code?: string }) =>
    [g.name ?? "", g.code ?? ""].map((t) => t.match(/\bG\d+\b/gi)?.pop()?.toUpperCase()).find(Boolean) ?? g.code ?? g.name ?? "Group";
  const parts = group
    ? [group.major ? initials(group.major) : "", group.year ? `Y${group.year}` : "", groupNumber(group)]
    : [major && major !== "__unassigned" ? initials(major) : "", year && year !== "unassigned" ? `Y${year}` : ""];
  return `${parts.filter(Boolean).join(" ") || "Full"} Schedule`;
}
