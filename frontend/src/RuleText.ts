import { clockHour, LIMIT_RULES, type DataRecord, type Rule } from "./api";
import type { Word } from "./i18n";

const TARGET_FIELD = { instructor_id: "instructors", room_id: "rooms", group_id: "groups", activity_id: "courses" } as const;

/** Which record field a rule type targets, and that record's kind (null when it uses params). */
export function ruleTarget(type: Rule["type"]): [keyof typeof TARGET_FIELD, DataRecord["kind"]] | null {
  if (type === "activities_not_same_day") return null;
  if (type === "room_unavailable") return ["room_id", "rooms"];
  if (["group_unavailable", "group_allowed", "group_max_daily_hours"].includes(type)) return ["group_id", "groups"];
  if (["activity_allowed", "activity_room"].includes(type)) return ["activity_id", "courses"];
  return ["instructor_id", "instructors"];
}

/** Human-readable meaning of a rule, e.g. "Dr. A · Instructor unavailable — Every day · 08:00–10:30". */
export function describeRule(rule: Pick<Rule, "type" | "day" | "start_hour" | "end_hour" | "params" | "instructor_id" | "room_id" | "group_id" | "activity_id">, records: DataRecord[], t: (key: Word) => string) {
  const name = (id?: string | null) => {
    const record = records.find(r => r.id === id);
    return record ? record.name + (record.kind === "courses" && record.activity_type ? ` (${t(record.activity_type as Word)})` : "") : "?";
  };
  const target = ruleTarget(rule.type);
  const subject = target ? name(rule[target[0]]) : (rule.params?.activity_ids || []).map(name).join(", ");
  let detail: string;
  if (!LIMIT_RULES.includes(rule.type)) detail = `${rule.day ? t(rule.day as Word) : t("everyDay")} · ${clockHour(rule.start_hour ?? 0)}–${clockHour(rule.end_hour ?? 0)}`;
  else if (rule.type === "activity_room") detail = (rule.params?.room_ids || []).map(name).join(", ");
  else if (rule.type === "instructor_max_days") detail = `≤ ${rule.params?.days} ${t("daysPerWeek")}`;
  else if (rule.type === "activities_not_same_day") detail = t("activities_not_same_day");
  else detail = `≤ ${rule.params?.hours} ${t("hoursPerDay")}`;
  return { subject, type: t(rule.type as Word), detail };
}
