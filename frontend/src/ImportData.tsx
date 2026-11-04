import { useState } from "react";
import { api, ApiError, type RecordKind } from "./api";
import { Icon, Modal } from "./components";
import { errors, type Word } from "./i18n";
const HEADERS: Record<RecordKind, string> = {
  instructors: "name,code,department,max_weekly_hours,day_off",
  groups: "name,code,size,year,major",
  rooms: "name,code,capacity,room_type,equipment",
  courses:
    "name,code,activity_type,sessions,duration,eligible_instructor_codes,group_codes,required_equipment",
};
type Preview = {
  version: number;
  valid: boolean;
  count: number;
  rows: {
    line: number;
    valid: boolean;
    data: { name: string; code: string };
    errors: string[];
  }[];
};
export function ImportData({
  kind,
  t,
  lang,
  close,
  onImported,
}: {
  kind: RecordKind;
  t: (key: Word) => string;
  lang: "en" | "ar";
  close: () => void;
  onImported: () => Promise<void>;
}) {
  const [text, setText] = useState(""),
    [preview, setPreview] = useState<Preview | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const explain = (code: string) =>
    errors[code]?.[lang === "ar" ? 1 : 0] || t("unsaved");
  const perform = async (commit = false) => {
    setBusy(true);
    setError("");
    try {
      if (commit) {
        await api(
          `/imports/${kind}/commit`,
          "POST",
          { csv: text },
          preview!.version,
        );
        await onImported();
        close();
      } else
        setPreview(
          await api<Preview>(`/imports/${kind}/preview`, "POST", { csv: text }),
        );
    } catch (e) {
      setError(explain(e instanceof ApiError ? e.code : "connection_failed"));
      if (e instanceof ApiError && e.status === 409) setPreview(null);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      title={`${t("importCsv")} · ${t(kind)}`}
      close={() => {
        if (!busy) close();
      }}
      t={t}
    >
      <p className="modal-description">{t("importHelp")}</p>
      <div className="csv-template">
        <span>{t("expectedHeaders")}</span>
        <code dir="ltr">{HEADERS[kind]}</code>
      </div>
      <label>
        {t("chooseCsv")}
        <input
          type="file"
          accept=".csv,text/csv"
          disabled={busy}
          onChange={async (e) => {
            const file = e.target.files?.[0];
            setPreview(null);
            setError("");
            setText("");
            if (!file) return;
            if (file.size > 1000000) {
              setError(explain("import_row_limit"));
              return;
            }
            setBusy(true);
            try {
              setText(await file.text());
            } catch {
              setError(explain("invalid_csv"));
            } finally {
              setBusy(false);
            }
          }}
        />
      </label>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      {preview && (
        <>
          <div
            className={`import-summary ${preview.valid ? "valid" : "invalid"}`}
          >
            <Icon name={preview.valid ? "check" : "sliders"} size={17} />
            {preview.count} {t("importRows")} ·{" "}
            {t(preview.valid ? "importReady" : "importNeedsCorrection")}
          </div>
          <div className="import-rows">
            {preview.rows.map((row) => (
              <div className="import-row" key={row.line}>
                <span>
                  {t("line")} {row.line}
                </span>
                <div>
                  <strong>
                    {row.data.code} · {row.data.name}
                  </strong>
                  <small>
                    {row.valid
                      ? t("rowValid")
                      : row.errors.map(explain).join(" ")}
                  </small>
                </div>
                <Icon name={row.valid ? "check" : "x"} size={15} />
              </div>
            ))}
          </div>
        </>
      )}
      <div className="form-actions">
        <button className="btn white" disabled={busy} onClick={close}>
          {t("cancel")}
        </button>
        <button
          className="btn white"
          disabled={busy || !text}
          onClick={() => void perform()}
        >
          {t(busy ? "working" : "previewImport")}
        </button>
        {preview?.valid && (
          <button
            className="btn primary"
            disabled={busy}
            onClick={() => void perform(true)}
          >
            {t(busy ? "working" : "commitImport")}
          </button>
        )}
      </div>
    </Modal>
  );
}
