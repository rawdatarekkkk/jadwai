import type { Repair } from "./api";

/** What must give way for an impossible timetable, with a fix the solver and validator proved. */
export function RepairPanel({ repair, ar }: { repair: Repair; ar: boolean }) {
  if (repair.status === "fixable" && !repair.suggestions?.length) return null;
  return (
    <div className="feasibility-recommendations repair-panel">
      <h4>{ar ? "كيف يمكن إصلاحه" : "How to fix it"}</h4>
      {repair.status === "fixable" ? (
        <>
          <p>
            {ar
              ? `يكفي تغيير ${repair.suggestions!.length === 1 ? "أمر واحد" : `${repair.suggestions!.length} أمور`}. `
              : `${repair.suggestions!.length === 1 ? "One change is" : `${repair.suggestions!.length} changes are`} enough. `}
            {repair.verified
              ? ar ? "تم التحقق: مع هذا التغيير يوجد جدول كامل يجتاز كل الفحوصات الأخرى." : "Verified: with this, a complete timetable exists that passes every other check."
              : ar ? "لم يتم التحقق من الحل." : "This fix was not verified."}
          </p>
          <ol>
            {repair.suggestions!.map((s, i) => (
              <li key={i}>
                <strong>{s.title}</strong>
                <p>{s.message}</p>
                {!!s.sessions.length && <ul>{s.sessions.slice(0, 8).map((x) => <li key={x}><small>{x}</small></li>)}</ul>}
              </li>
            ))}
          </ol>
          <p><small>{ar ? "غيّر القيد أو الحصة المقترحة ثم أنشئ الجدول مرة أخرى." : "Change the suggested rule or session, then generate again."}</small></p>
        </>
      ) : (
        <>
          <p>{repair.message}</p>
          {!!repair.findings?.length && <ul>{repair.findings.map((f) => <li key={f}>{f}</li>)}</ul>}
        </>
      )}
    </div>
  );
}
