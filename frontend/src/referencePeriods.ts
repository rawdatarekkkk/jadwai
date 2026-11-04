// Five 90-minute teaching periods approved by the owner on 18 October 2026.
export const REFERENCE_PERIODS = [
  { start: 8 * 60 + 30, end: 10 * 60 },
  { start: 10 * 60 + 15, end: 11 * 60 + 45 },
  { start: 12 * 60, end: 13 * 60 + 30 },
  { start: 13 * 60 + 45, end: 15 * 60 + 15 },
  { start: 15 * 60 + 45, end: 17 * 60 + 15 },
] as const;
