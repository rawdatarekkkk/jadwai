import csv
import io
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as DB

from app.academic import validate_record
from app.dependencies import administrator, db_session, event, fail, lock_workspace
from app.models import Record, Workspace
from app.schemas import CSVInput

router = APIRouter()
HEADERS = {
    "instructors": ["name", "code", "department", "max_weekly_hours", "day_off"],
    "groups": ["name", "code", "size", "year", "major"],
    "rooms": ["name", "code", "capacity", "room_type", "equipment"],
    "courses": [
        "name",
        "code",
        "activity_type",
        "sessions",
        "duration",
        "eligible_instructor_codes",
        "group_codes",
        "required_equipment",
    ],
}
OPTIONAL = {"day_off", "max_weekly_hours", "equipment", "required_equipment", "year", "major"}


def preview(kind, content, db):
    if kind not in HEADERS:
        fail(404, "not_found")
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip("\ufeff")), strict=True)
        headers = reader.fieldnames or []
        if (
            len(set(headers)) != len(headers)
            or set(headers) - set(HEADERS[kind])
            or set(HEADERS[kind]) - OPTIONAL - set(headers)
        ):
            fail(422, "invalid_csv_headers")
        inputs = list(reader)
    except csv.Error:
        fail(422, "invalid_csv")
    if not inputs or len(inputs) > 500:
        fail(422, "import_row_limit")
    existing = db.scalars(select(Record)).all()
    lookups = {
        k: {r.code.casefold(): r.id for r in existing if r.kind == k}
        for k in ["instructors", "groups"]
    }
    output = []
    major_spellings = {}
    seen = set()
    for line, row in enumerate(inputs, 2):
        try:
            if None in row or any(value is None for value in row.values()):
                fail(422, "invalid_csv")
            data = {key: value.strip() for key, value in row.items()}
            code = data.get("code", "").casefold()
            if code in seen:
                fail(422, "duplicate_code")
            seen.add(code)
            if "day_off" in data and not data["day_off"]:
                data["day_off"] = None
            if "max_weekly_hours" in data:
                try:
                    data["max_weekly_hours"] = float(data["max_weekly_hours"]) if data["max_weekly_hours"] else None
                except ValueError:
                    fail(422, "invalid_input")
            for key in ["size", "capacity", "sessions", "duration", "year"]:
                if key in data:
                    if key == "year" and not data[key]:
                        data[key] = None
                        continue
                    try:
                        data[key] = int(data[key])
                    except ValueError:
                        fail(422, "invalid_input")
            for key in ["equipment", "required_equipment"]:
                if key in data:
                    data[key] = [
                        value.strip() for value in data[key].split("|") if value.strip()
                    ]
            if kind == "rooms":
                data["room_types"] = data.pop("room_type").split("|")
            if kind == "groups" and "major" in data and not data["major"]:
                data["major"] = None
            if kind == "courses":
                for key, target, lookup in [
                    (
                        "eligible_instructor_codes",
                        "eligible_instructors",
                        "instructors",
                    ),
                    ("group_codes", "group_ids", "groups"),
                ]:
                    codes = [
                        value.strip().casefold()
                        for value in data.pop(key, "").split("|")
                        if value.strip()
                    ]
                    if any(code not in lookups[lookup] for code in codes):
                        fail(422, "invalid_reference")
                    data[target] = [lookups[lookup][code] for code in codes]
            body = validate_record(kind, data, db)
            if kind == "groups" and body.get("major"):
                key = (body["year"], body["major"].casefold())
                body["major"] = major_spellings.setdefault(key, body["major"])
            output.append({"line": line, "valid": True, "data": body, "errors": []})
        except HTTPException as e:
            output.append(
                {
                    "line": line,
                    "valid": False,
                    "data": {"name": row.get("name", ""), "code": row.get("code", "")},
                    "errors": [e.detail],
                }
            )
    return {
        "version": db.get(Workspace, 1).version,
        "valid": all(row["valid"] for row in output),
        "rows": output,
        "count": len(output),
    }


@router.post("/api/imports/{kind}/preview")
def import_preview(
    kind: str, body: CSVInput, user=Depends(administrator), db: DB = Depends(db_session)
):
    return preview(kind, body.csv, db)


@router.post("/api/imports/{kind}/commit", status_code=201)
def commit(
    kind: str,
    body: CSVInput,
    request: Request,
    user=Depends(administrator),
    db: DB = Depends(db_session),
):
    ws = lock_workspace(request, db)
    result = preview(kind, body.csv, db)
    if not result["valid"]:
        fail(422, "import_invalid_rows")
    for row in result["rows"]:
        db.add(Record(id=str(uuid4()), kind=kind, data=row["data"]))
    event(
        db,
        ws,
        user,
        "import.committed",
        f"{result['count']} {kind}",
        changes_inputs=True,
    )
    db.commit()
    return {"count": result["count"], "version": ws.version}
