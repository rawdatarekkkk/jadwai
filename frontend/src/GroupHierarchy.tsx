import type { DataRecord } from "./api";
import type { Word } from "./i18n";
import { Icon } from "./components";

export function GroupHierarchy({
  groups,
  t,
  administrator,
  edit,
  remove,
}: {
  groups: DataRecord[];
  t: (key: Word) => string;
  administrator: boolean;
  edit: (group: DataRecord) => void;
  remove: (group: DataRecord) => void;
}) {
  const years = [...new Set(groups.map((g) => g.year ?? 0))].sort(
    (a, b) => (a || 99) - (b || 99),
  );
  return (
    <div className="group-hierarchy">
      {years.map((year) => {
        const rows = groups.filter((g) => (g.year ?? 0) === year);
        const majors = [...new Set(rows.map((g) => g.major ?? ""))].sort(
          (a, b) => a.localeCompare(b),
        );
        return (
          <section className="year-section" key={year}>
            <div className="year-heading">
              <span className="year-marker">
                <Icon name="book" size={20} />
              </span>
              <div>
                <h3>
                  {year ? `${t("studyYear")} ${year}` : t("unassignedYear")}
                </h3>
                <p>
                  {rows.length} {t("groups")} ·{" "}
                  {rows.reduce((sum, g) => sum + (g.size ?? 0), 0)}{" "}
                  {t("people")}
                </p>
              </div>
            </div>
            <div className="year-majors">
              {majors.map((major) => (
                <section className="major-section" key={major}>
                  <h4>
                    <Icon name="leaf" size={16} />
                    {major || t("unassignedMajor")}
                  </h4>
                  <div className="record-grid">
                    {rows
                      .filter((g) => (g.major ?? "") === major)
                      .sort((a, b) => a.name.localeCompare(b.name))
                      .map((g) => (
                        <article className="record-card" key={g.id}>
                          <div className="record-top">
                            <span className="record-icon groups">
                              <Icon name="people" size={23} />
                            </span>
                            <span className="record-code">{g.code}</span>
                          </div>
                          <h3>{g.name}</h3>
                          <p>
                            {g.size} {t("people")}
                          </p>
                          {administrator && (
                            <div className="record-actions">
                              <button
                                className="icon-btn"
                                aria-label={t("edit")}
                                onClick={() => edit(g)}
                              >
                                <Icon name="edit" size={14} />
                              </button>
                              <button
                                className="icon-btn danger"
                                aria-label={t("remove")}
                                onClick={() => remove(g)}
                              >
                                <Icon name="trash" size={14} />
                              </button>
                            </div>
                          )}
                        </article>
                      ))}
                  </div>
                </section>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}
