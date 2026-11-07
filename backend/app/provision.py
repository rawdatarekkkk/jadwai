"""Create least-privilege local runtime roles using the separate migration owner."""

import os
import secrets
from pathlib import Path

from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url


def provision():
    envfile = Path(__file__).resolve().parents[2] / ".env"
    owner = os.environ.get("DATABASE_ADMIN_URL") or os.environ["DATABASE_URL"]
    values = dict(
        line.split("=", 1)
        for line in envfile.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    engine = create_engine(owner)
    with engine.begin() as conn:
        driver = conn.connection.driver_connection
        for role, key in [
            ("jadwai_app", "DATABASE_URL"),
            ("jadwai_worker", "WORKER_DATABASE_URL"),
        ]:
            existing = values.get(key, "")
            old = make_url(existing) if existing else None
            password = (
                old.password
                if old and old.username == role
                else secrets.token_urlsafe(32)
            )
            with driver.cursor() as cursor:
                cursor.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,))
                verb = "ALTER" if cursor.fetchone() else "CREATE"
                cursor.execute(
                    sql.SQL(
                        "{} ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.SQL(verb), sql.Identifier(role), sql.Literal(password))
                )
                cursor.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(
                        sql.Identifier(role)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(
                        sql.Identifier(role)
                    )
                )
                cursor.execute(
                    sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(
                        sql.Identifier(role)
                    )
                )
            values[key] = (
                make_url(owner)
                .set(username=role, password=password)
                .render_as_string(hide_password=False)
            )
        app_tables = "workspace,app_user,session,record,rule,password_reset,login_bucket,instructor,room,student_group,teaching_activity,activity_instructor,activity_group,schedule_run,assignment_lock,course_catalog,exam_run,source_timetable,extraction_job,advising_student,advising_change"
        conn.exec_driver_sql(
            f"GRANT SELECT,INSERT,UPDATE,DELETE ON {app_tables} TO jadwai_app"
        )
        conn.exec_driver_sql("GRANT SELECT,INSERT ON audit,evaluation_review,evaluation_adjudication,extraction_proposal,extraction_proposal_review TO jadwai_app")
        conn.exec_driver_sql(
            "GRANT SELECT ON alembic_version,worker_heartbeat TO jadwai_app"
        )
        conn.exec_driver_sql(
            "GRANT SELECT,INSERT,UPDATE ON worker_heartbeat TO jadwai_worker"
        )
        conn.exec_driver_sql(
            "GRANT SELECT,DELETE ON session,password_reset,login_bucket TO jadwai_worker"
        )
        conn.exec_driver_sql("GRANT SELECT,UPDATE ON schedule_run TO jadwai_worker")
    engine.dispose()
    # Only record URLs for the database this .env already describes. Provisioning
    # another database (for example a demo) must not repoint the live app at it.
    current = values.get("DATABASE_ADMIN_URL") or values.get("DATABASE_URL")
    target = make_url(owner)
    if current and (lambda u: (u.host, u.port, u.database))(make_url(current)) != (target.host, target.port, target.database):
        print(f"Provisioned roles for database {target.database}; .env left unchanged (it describes another database).")
        return
    values["DATABASE_ADMIN_URL"] = owner
    envfile.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    envfile.chmod(0o600)
    print(
        "Provisioned separate API/worker roles; owner retained only for setup and migrations."
    )


if __name__ == "__main__":
    provision()
