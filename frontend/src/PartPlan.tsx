import type { RunProgress, ScheduleRun, ScopeItem, Workspace } from "./api";

export type Parts = { scope: ScopeItem[]; base: string | null };
type Unit = ScopeItem & { key: string; sessions: number };

export const unitKey = (u: ScopeItem) => `${u.programme}\u0000${u.year ?? ""}`;
export const unitLabel = (u: ScopeItem, ar: boolean) => (u.year ? `${u.programme} · ${ar ? "السنة" : "Year"} ${u.year}` : u.programme);

/** Sessions per programme year (an activity counts for every programme year among its groups). */
export function programmeSessions(ws: Workspace): Unit[] {
  const groups = new Map(ws.records.filter((r) => r.kind === "groups").map((g) => {
    const x = g as { id: string; major?: string | null; year?: number | null };
    return [x.id, { programme: x.major || "", year: x.year ?? null }] as const;
  }));
  const units = new Map<string, Unit>();
  for (const a of ws.records.filter((r) => r.kind === "courses") as { group_ids?: string[]; sessions?: number }[]) {
    const mine = new Map<string, ScopeItem>();
    for (const g of a.group_ids || []) {
      const u = groups.get(g);
      if (u?.programme) mine.set(unitKey(u), u);
    }
    for (const [key, u] of mine) {
      const unit = units.get(key) || { ...u, key, sessions: 0 };
      unit.sessions += a.sessions || 0;
      units.set(key, unit);
    }
  }
  return [...units.values()].sort((x, y) => x.programme.localeCompare(y.programme) || (x.year ?? 0) - (y.year ?? 0));
}

/** A run the next part can build on: valid, current, and not yet covering everything. */
export function continuable(run: ScheduleRun | undefined): RunProgress | null {
  const progress = run?.progress;
  return run && run.status === "completed" && !run.stale && run.result?.validation?.passed && progress && !progress.complete ? progress : null;
}

export function PartPlan({ ws, ar, parts, change, base, disabled }: { ws: Workspace; ar: boolean; parts: Parts | null; change: (p: Parts | null) => void; base: ScheduleRun | undefined; disabled: boolean }) {
  const units = programmeSessions(ws);
  if (units.length < 2) return null;
  const progress = continuable(base);
  const remaining = new Set((parts?.base && progress ? progress.remaining_programmes : units).map(unitKey));
  const chosen = new Set((parts?.scope || []).map(unitKey));
  const sessions = units.filter((u) => chosen.has(u.key)).reduce((n, u) => n + u.sessions, 0);
  const toggle = (u: Unit) => {
    const scope = chosen.has(u.key) ? parts!.scope.filter((x) => unitKey(x) !== u.key) : [...(parts?.scope || []), { programme: u.programme, year: u.year }];
    change({ base: parts?.base ?? null, scope });
  };
  return (
    <details className="panel part-plan" open={!!parts}>
      <summary>{ar ? "الإنشاء على أجزاء (برنامج أو سنة في كل مرة)" : "Build in parts (a few programmes or years at a time)"}</summary>
      <p>{ar
        ? "لجامعة كاملة: أنشئ سنوات البرامج المختارة أولاً، ثم أكمل من تلك المسودة بغيرها. تبقى حصص الأجزاء السابقة ثابتة، ويُتحقق من الجدول المجمّع كله. لا يُنشر إلا الجدول المكتمل."
        : "For a whole university: generate some programme years, then continue from that draft with more. Earlier parts stay fixed and the combined timetable is checked as a whole. Only a complete timetable can be published."}</p>
      <label className="check-label">
        <input type="checkbox" checked={!!parts} disabled={disabled} onChange={(e) => change(e.target.checked ? { scope: [], base: progress && base ? base.id : null } : null)} />
        {ar ? "إنشاء المختار فقط" : "Generate only the chosen programme years"}
      </label>
      {parts && (
        <>
          {progress && base && (
            <label className="check-label">
              <input type="checkbox" checked={parts.base === base.id} disabled={disabled} onChange={(e) => change({ scope: [], base: e.target.checked ? base.id : null })} />
              {ar
                ? `أكمل من المسودة المختارة (${progress.scheduled_sessions} من ${progress.total_sessions} حصة مجدولة)`
                : `Continue from the selected draft (${progress.scheduled_sessions} of ${progress.total_sessions} sessions scheduled)`}
            </label>
          )}
          <ul className="part-programmes">
            {units.map((u) => {
              const done = !remaining.has(u.key);
              return (
                <li key={u.key}>
                  <label className="check-label">
                    <input type="checkbox" checked={done || chosen.has(u.key)} disabled={disabled || done} onChange={() => toggle(u)} />
                    {unitLabel(u, ar)} <small>· {u.sessions} {ar ? "حصة" : "sessions"}{done ? (ar ? " · مجدول" : " · scheduled") : ""}</small>
                  </label>
                </li>
              );
            })}
          </ul>
          <p className={sessions > 600 ? "error" : ""}>
            {ar ? `المختار: ${sessions} حصة (الحد 600 في كل جزء).` : `Chosen: ${sessions} sessions (at most 600 per part).`}
          </p>
        </>
      )}
    </details>
  );
}
