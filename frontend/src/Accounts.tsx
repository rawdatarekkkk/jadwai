import { useEffect, useState } from "react";
import { api, ApiError, type User, type Workspace } from "./api";
import { Icon, Modal } from "./components";
import { errors, type Word } from "./i18n";

type Account = User & { id: string; active: boolean; version: number };
type Reset = { token: string; expires_at: string };
type Props = {
  user: User;
  t: (key: Word) => string;
  lang: "en" | "ar";
  onSessionLost: () => void;
  onChanged: () => void;
};
export function Accounts({ user, t, lang, onSessionLost, onChanged }: Props) {
  const [groups, setGroups] = useState<Workspace["records"]>([]);
  const [selectedRole, setSelectedRole] = useState("viewer");
  const [rows, setRows] = useState<Account[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const [modal, setModal] = useState<{
    type: "create" | "edit" | "reset" | "revoke" | "link";
    row?: Account;
    reset?: Reset;
    self?: boolean;
  } | null>(null);
  const explain = (e: unknown) =>
    errors[e instanceof ApiError ? e.code : "connection_failed"]?.[
      lang === "en" ? 0 : 1
    ] || t("unsaved");
  const load = async () => {
    try {
      setRows(await api<Account[]>("/users"));
    } catch (e) {
      setError(explain(e));
    }
  };
  useEffect(() => {
    void load();
    void api<Workspace>("/workspace").then(w => setGroups(w.records.filter(r => r.kind === "groups"))).catch(() => {});
  }, []);
  const close = () => {
    if (busy) return;
    const self = modal?.self;
    setModal(null);
    setError("");
    if (self) onSessionLost();
  };
  const act = async (work: () => Promise<void>) => {
    setBusy(true);
    setError("");
    try {
      await work();
      if (!(
        modal?.row?.id === user.id &&
        (modal.type === "reset" || modal.type === "revoke")
      ))
        onChanged();
    } catch (e) {
      setError(explain(e));
      await load();
    } finally {
      setBusy(false);
    }
  };
  const resetLink = modal?.reset
    ? `${window.location.origin}/#reset=${encodeURIComponent(modal.reset.token)}`
    : "";
  return (
    <>
      <div className="account-toolbar">
        <p>{t("accountsHelp")}</p>
        <button
          className="btn primary"
          onClick={() => {
            setError("");
            setSelectedRole("viewer");
            setModal({ type: "create" });
          }}
        >
          <Icon name="plus" size={16} />
          {t("addAccount")}
        </button>
      </div>
      {error && !modal && (
        <div className="error" role="alert">
          {error}
          <button onClick={() => void load()}>{t("retry")}</button>
        </div>
      )}
      <div className="account-grid">
        {rows.map((row) => (
          <article className="panel account-card" key={row.id}>
            <div className="account-card-top">
              <span className="avatar">{row.name[0]}</span>
              <span className={`pill ${row.active ? "green" : "neutral"}`}>
                {t(row.active ? "activeAccount" : "inactiveAccount")}
              </span>
            </div>
            <h3>{row.name}</h3>
            <p dir="ltr">{row.email}</p>
            <span className="pill neutral">
              {row.role === "student" ? (lang === "ar" ? "طالب" : "Student") : t(row.role === "administrator" ? "admin" : "viewer")}
            </span>
            {row.id === user.id && (
              <span className="pill lilac">{t("you")}</span>
            )}
            <div className="account-card-actions">
              <button
                onClick={() => {
                  setError("");
                  setSelectedRole(row.role);
                  setModal({ type: "edit", row });
                }}
              >
                <Icon name="edit" size={14} />
                {t("edit")}
              </button>
              <button
                disabled={!row.active}
                onClick={() => {
                  setError("");
                  setModal({ type: "reset", row });
                }}
              >
                {t("resetAccess")}
              </button>
              <button
                onClick={() => {
                  setError("");
                  setModal({ type: "revoke", row });
                }}
              >
                {t("revokeSessions")}
              </button>
            </div>
          </article>
        ))}
      </div>
      {modal && (
        <Modal
          title={t(
            modal.type === "create"
              ? "addAccount"
              : modal.type === "edit"
                ? "editAccount"
                : modal.type === "link"
                  ? "resetLink"
                  : modal.type === "reset"
                    ? "resetAccess"
                    : "revokeSessions",
          )}
          close={close}
          t={t}
        >
          {error && (
            <div className="error" role="alert">
              {error}
            </div>
          )}
          {(modal.type === "create" || modal.type === "edit") && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const f = new FormData(e.currentTarget);
                void act(async () => {
                  if (modal.type === "create") {
                    const result = await api<{ user: Account; reset: Reset }>(
                      "/users",
                      "POST",
                      {
                        name: f.get("name"),
                        email: f.get("email"),
                        role: f.get("role"),
                        group_id: f.get("role") === "student" ? f.get("group_id") : null,
                      },
                    );
                    setModal({ type: "link", reset: result.reset });
                    await load();
                  } else {
                    await api(
                      `/users/${modal.row!.id}`,
                      "PUT",
                      {
                        name: f.get("name"),
                        role: f.get("role"),
                        group_id: f.get("role") === "student" ? f.get("group_id") : null,
                        active: f.get("active") === "on",
                      },
                      modal.row!.version,
                    );
                    if (
                      modal.row!.id === user.id &&
                      (f.get("active") !== "on" || f.get("role") !== user.role)
                    ) {
                      onSessionLost();
                      return;
                    }
                    setModal(null);
                    await load();
                  }
                });
              }}
            >
              <label>
                {t("name")}
                <input
                  name="name"
                  required
                  minLength={1}
                  maxLength={100}
                  pattern=".*\S.*"
                  defaultValue={modal.row?.name}
                />
              </label>
              {modal.type === "create" && (
                <label>
                  {t("email")}
                  <input name="email" type="email" required maxLength={200} />
                </label>
              )}
              <label>
                {t("accountRole")}
                <select name="role" value={selectedRole} onChange={e => setSelectedRole(e.target.value)}>
                  <option value="student">{lang === "ar" ? "طالب" : "Student"}</option>
                  <option value="viewer">{t("viewer")}</option>
                  <option value="administrator">{t("admin")}</option>
                </select>
              </label>
              {selectedRole === "student" && <label>{lang === "ar" ? "مجموعة الطالب" : "Student group"}<select name="group_id" required defaultValue={modal.row?.group_id || ""}><option value="">{lang === "ar" ? "اختر المجموعة" : "Choose a group"}</option>{groups.map(g => <option key={g.id} value={g.id}>{g.year ? `Year ${g.year} · ` : ""}{g.major || ""} · {g.name}</option>)}</select></label>}
              {modal.type === "edit" && (
                <label className="check-label">
                  <input
                    name="active"
                    type="checkbox"
                    defaultChecked={modal.row?.active}
                  />
                  {t("activeAccount")}
                </label>
              )}
              <p className="modal-description">{t("accountChangeHelp")}</p>
              <div className="form-actions">
                <button
                  type="button"
                  className="btn white"
                  disabled={busy}
                  onClick={close}
                >
                  {t("cancel")}
                </button>
                <button className="btn primary" disabled={busy}>
                  {t(busy ? "working" : "save")}
                </button>
              </div>
            </form>
          )}
          {(modal.type === "reset" || modal.type === "revoke") && (
            <>
              <p className="modal-description">
                {t(modal.type === "reset" ? "resetWarning" : "revokeWarning")}
              </p>
              <div className="delete-target">{modal.row?.name}</div>
              <div className="form-actions">
                <button className="btn white" disabled={busy} onClick={close}>
                  {t("cancel")}
                </button>
                <button
                  className="btn primary"
                  disabled={busy}
                  onClick={() =>
                    void act(async () => {
                      const row = modal.row!;
                      if (modal.type === "reset") {
                        const result = await api<{ reset: Reset }>(
                          `/users/${row.id}/reset`,
                          "POST",
                          undefined,
                          row.version,
                        );
                        setModal({
                          type: "link",
                          reset: result.reset,
                          self: row.id === user.id,
                        });
                        if (row.id !== user.id) await load();
                      } else {
                        await api(
                          `/users/${row.id}/revoke-sessions`,
                          "POST",
                          undefined,
                          row.version,
                        );
                        if (row.id === user.id) {
                          onSessionLost();
                          return;
                        }
                        setModal(null);
                        await load();
                      }
                    })
                  }
                >
                  {t(
                    busy
                      ? "working"
                      : modal.type === "reset"
                        ? "createResetLink"
                        : "revokeSessions",
                  )}
                </button>
              </div>
            </>
          )}
          {modal.type === "link" && (
            <>
              <p className="modal-description">{t("resetLinkHelp")}</p>
              <label>
                {t("resetLink")}
                <input
                  className="reset-link-input"
                  value={resetLink}
                  readOnly
                  onFocus={(e) => e.target.select()}
                  dir="ltr"
                />
              </label>
              <p className="reset-expiry">
                {t("expiresAt")}{" "}
                {new Date(modal.reset!.expires_at).toLocaleString(lang, {
                  timeZone: "Africa/Cairo",
                })}
              </p>
              <div className="form-actions">
                <button className="btn primary" onClick={close}>
                  {t("done")}
                </button>
              </div>
            </>
          )}
        </Modal>
      )}
    </>
  );
}

export function ResetAccess({
  token,
  t,
  lang,
  onDone,
}: {
  token: string;
  t: (key: Word) => string;
  lang: "en" | "ar";
  onDone: () => void;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [done, setDone] = useState(false);
  return (
    <div className="recovery-page">
      <div className="panel recovery-card">
        <div className="eyebrow">JadwAI</div>
        <h1>{t(done ? "passwordReady" : "setPassword")}</h1>
        <p>{t(done ? "passwordReadyHelp" : "resetHelp")}</p>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {done ? (
          <button className="btn primary wide" onClick={onDone}>
            {t("backToSignin")}
          </button>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              const f = new FormData(e.currentTarget);
              if (f.get("password") !== f.get("confirm")) {
                setError(t("passwordMismatch"));
                return;
              }
              setBusy(true);
              setError("");
              void api("/auth/reset-password", "POST", {
                token,
                new_password: f.get("password"),
              })
                .then(() => setDone(true))
                .catch((e) =>
                  setError(
                    errors[
                      e instanceof ApiError ? e.code : "connection_failed"
                    ]?.[lang === "en" ? 0 : 1] || t("unsaved"),
                  ),
                )
                .finally(() => setBusy(false));
            }}
          >
            <PasswordFields t={t} />
            <button className="btn primary wide" disabled={busy}>
              {t(busy ? "working" : "setPassword")}
            </button>
            <button className="text-link" type="button" onClick={onDone}>
              {t("backToSignin")}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

export function PasswordFields({ t }: { t: (key: Word) => string }) {
  return (
    <>
      <label>
        {t("newPassword")}
        <input
          name="password"
          type="password"
          required
          minLength={15}
          maxLength={200}
          autoComplete="new-password"
        />
      </label>
      <label>
        {t("confirmPassword")}
        <input
          name="confirm"
          type="password"
          required
          minLength={15}
          maxLength={200}
          autoComplete="new-password"
        />
      </label>
      <p className="password-hint">{t("passwordHint")}</p>
    </>
  );
}

export function MyAccount({
  user,
  t,
  lang,
  onSignedOut,
}: {
  user: User;
  t: (key: Word) => string;
  lang: "en" | "ar";
  onSignedOut: () => void;
}) {
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  return (
    <>
      <p className="modal-description">
        {user.name} · {user.email}
      </p>
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          const f = new FormData(e.currentTarget);
          if (f.get("password") !== f.get("confirm")) {
            setError(t("passwordMismatch"));
            return;
          }
          setBusy(true);
          void api("/auth/password", "POST", {
            current_password: f.get("current"),
            new_password: f.get("password"),
          })
            .then(onSignedOut)
            .catch((e) =>
              setError(
                errors[e instanceof ApiError ? e.code : "connection_failed"]?.[
                  lang === "en" ? 0 : 1
                ] || t("unsaved"),
              ),
            )
            .finally(() => setBusy(false));
        }}
      >
        <label>
          {t("currentPassword")}
          <input
            type="password"
            name="current"
            autoComplete="current-password"
            required
            maxLength={200}
          />
        </label>
        <PasswordFields t={t} />
        <div className="form-actions">
          <button
            type="button"
            className="btn white"
            onClick={() =>
              void api("/auth/logout", "POST")
                .then(onSignedOut)
                .catch((e) =>
                  setError(
                    errors[
                      e instanceof ApiError ? e.code : "connection_failed"
                    ]?.[lang === "en" ? 0 : 1] || t("unsaved"),
                  ),
                )
            }
          >
            {t("signout")}
          </button>
          <button className="btn primary" disabled={busy}>
            {t(busy ? "working" : "changePassword")}
          </button>
        </div>
      </form>
    </>
  );
}
