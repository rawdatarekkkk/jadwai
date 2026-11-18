from __future__ import annotations

import os
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    column,
    create_engine,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
)


def utcnow():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspace"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    term: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    timezone: Mapped[str] = mapped_column(String(100), default="Africa/Cairo")
    days: Mapped[list] = mapped_column(
        JSON, default=lambda: ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday"]
    )
    start_hour: Mapped[int] = mapped_column(Integer, default=8)
    end_hour: Mapped[int] = mapped_column(Integer, default=18)
    period_minutes: Mapped[int] = mapped_column(Integer, default=30)
    teaching_periods: Mapped[list] = mapped_column(JSON, default=list)
    exam_cohort_rules: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    realism_policy: Mapped[dict] = mapped_column(JSON, default=dict)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)


class User(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        CheckConstraint("role IN ('administrator', 'viewer', 'student', 'instructor')", name="valid_user_role"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    email: Mapped[str] = mapped_column(String(200), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    password: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default="administrator")
    group_id: Mapped[str | None] = mapped_column(ForeignKey("record.id"), nullable=True)
    instructor_id: Mapped[str | None] = mapped_column(ForeignKey("record.id"), nullable=True)
    advising_student_id: Mapped[str | None] = mapped_column(ForeignKey("advising_student.id", ondelete="SET NULL"), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)


class Session(Base):
    __tablename__ = "session"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Record(Base):
    __tablename__ = "record"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('courses','instructors','rooms','groups')",
            name="valid_record_kind",
        ),
        Index("record_kind_code_ci", "kind", func.lower(column("code")), unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(20))
    instructor: Mapped[InstructorDetail | None] = relationship(
        cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    room: Mapped[RoomDetail | None] = relationship(
        cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    group: Mapped[GroupDetail | None] = relationship(
        cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )
    activity: Mapped[ActivityDetail | None] = relationship(
        cascade="all, delete-orphan", uselist=False, lazy="selectin"
    )

    @property
    def data(self):
        result = {"name": self.name, "code": self.code}
        if self.kind == "instructors":
            result["department"] = self.instructor.department
            result["day_off"] = self.instructor.day_off
            result["position"] = self.instructor.position
            if self.instructor.max_weekly_minutes is not None:
                result["max_weekly_hours"] = self.instructor.max_weekly_minutes / 60
        elif self.kind == "rooms":
            result.update(
                source_info=self.room.source_info,
                capacity=self.room.capacity,
                room_type=self.room.room_type,
                room_types=self.room.room_types,
                equipment=self.room.equipment,
                reserved_majors=self.room.reserved_majors or [],
                reserved_course_ids=self.room.reserved_course_ids or [],
            )
        elif self.kind == "groups":
            result.update(size=self.group.size, year=self.group.year, major=self.group.major)
        else:
            a = self.activity
            result.update(
                course_id=a.course_id,
                activity_type=a.activity_type,
                sessions=a.sessions,
                duration=a.duration,
                eligible_instructors=[x.instructor_id for x in a.instructors],
                group_ids=[x.group_id for x in a.groups],
                required_equipment=a.required_equipment,
            )
        return result

    @data.setter
    def data(self, body):
        self.name, self.code = body["name"], body["code"]
        if self.kind == "instructors":
            if self.instructor is None:
                self.instructor = InstructorDetail()
            self.instructor.department = body["department"]
            self.instructor.day_off = body.get("day_off")
            self.instructor.position = body.get("position")
            hours = body.get("max_weekly_hours")
            self.instructor.max_weekly_minutes = None if hours is None else int(hours * 60)
        elif self.kind == "rooms":
            if self.room is None:
                self.room = RoomDetail()
            self.room.source_info = body.get("source_info") or self.room.source_info or {}
            self.room.room_types = body.get("room_types") or ([body["room_type"]] if body.get("room_type") else [])
            self.room.capacity, self.room.room_type, self.room.equipment = (
                body["capacity"],
                body["room_type"],
                body.get("equipment", []),
            )
            self.room.reserved_majors = body.get("reserved_majors") or []
            self.room.reserved_course_ids = body.get("reserved_course_ids") or []
        elif self.kind == "groups":
            if self.group is None:
                self.group = GroupDetail()
            self.group.size = body["size"]
            self.group.year = body.get("year")
            self.group.major = body.get("major")
        else:
            if self.activity is None:
                self.activity = ActivityDetail()
            a = self.activity
            a.course_id = body.get("course_id")
            a.activity_type, a.sessions, a.duration, a.required_equipment = (
                body["activity_type"],
                body["sessions"],
                body["duration"],
                body.get("required_equipment", []),
            )
            current = {link.instructor_id: link for link in a.instructors}
            a.instructors = [
                current.get(i) or ActivityInstructor(instructor_id=i)
                for i in body["eligible_instructors"]
            ]
            current = {link.group_id: link for link in a.groups}
            a.groups = [
                current.get(i) or ActivityGroup(group_id=i) for i in body["group_ids"]
            ]


class InstructorDetail(Base):
    __tablename__ = "instructor"
    __table_args__ = (CheckConstraint("day_off IS NULL OR day_off IN ('Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday')", name="instructor_day_off"), CheckConstraint("max_weekly_minutes IS NULL OR (max_weekly_minutes BETWEEN 0 AND 10080 AND max_weekly_minutes % 30 = 0)", name="weekly_limit_minutes"), CheckConstraint("position IS NULL OR position IN ('doctor','ta')", name="instructor_position"),)
    max_weekly_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    id: Mapped[str] = mapped_column(
        ForeignKey("record.id", ondelete="CASCADE"), primary_key=True
    )
    department: Mapped[str] = mapped_column(String(100))
    day_off: Mapped[str | None] = mapped_column(String(10), nullable=True)
    position: Mapped[str | None] = mapped_column(String(10), nullable=True)


class RoomDetail(Base):
    __tablename__ = "room"
    __table_args__ = (
        CheckConstraint("capacity BETWEEN 1 AND 2000", name="room_capacity"),
        CheckConstraint("cardinality(room_types) BETWEEN 0 AND 4 AND room_types <@ ARRAY['lecture','lab','flexible','exam_hall']::varchar[] AND array_position(room_types, NULL) IS NULL", name="room_types_valid"),
        CheckConstraint("room_type IN ('lecture','lab','flexible','exam_hall')", name="room_type"),
    )
    id: Mapped[str] = mapped_column(
        ForeignKey("record.id", ondelete="CASCADE"), primary_key=True
    )
    source_info: Mapped[dict] = mapped_column(JSON, default=dict)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    room_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    room_types: Mapped[list[str]] = mapped_column(ARRAY(String(20)))
    equipment: Mapped[list[str]] = mapped_column(ARRAY(String(60)), default=list)
    # Special rooms: only these programmes / catalogue courses may use the room (empty = everyone).
    reserved_majors: Mapped[list[str]] = mapped_column(ARRAY(String(100)), default=list, server_default="{}")
    reserved_course_ids: Mapped[list[str]] = mapped_column(ARRAY(String(36)), default=list, server_default="{}")


class GroupDetail(Base):
    __tablename__ = "student_group"
    __table_args__ = (CheckConstraint("size BETWEEN 1 AND 2000", name="group_size"), CheckConstraint("year IS NULL OR year BETWEEN 1 AND 12", name="group_year"), CheckConstraint("major IS NULL OR length(trim(major)) > 0", name="group_major"))
    id: Mapped[str] = mapped_column(
        ForeignKey("record.id", ondelete="CASCADE"), primary_key=True
    )
    size: Mapped[int] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    major: Mapped[str | None] = mapped_column(String(100), nullable=True)


class CourseCatalog(Base):
    __tablename__ = "course_catalog"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    code: Mapped[str] = mapped_column(String(20), unique=True)
    source_info: Mapped[dict] = mapped_column(JSON, default=dict)
    eligibility: Mapped[dict] = mapped_column(JSON)
    group_ids: Mapped[list] = mapped_column(JSON)
    expected_students: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Exam plan: quizzes in the semester, and whether a second-chance midterm is offered.
    quiz_count: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    second_chance: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class ActivityDetail(Base):
    __tablename__ = "teaching_activity"
    __table_args__ = (
        CheckConstraint(
            "activity_type IN ('lecture','tutorial','lab')", name="activity_type"
        ),
        CheckConstraint(
            "sessions BETWEEN 1 AND 10 AND duration BETWEEN 30 AND 240 AND duration % 30 = 0",
            name="activity_duration",
        ),
    )
    id: Mapped[str] = mapped_column(
        ForeignKey("record.id", ondelete="CASCADE"), primary_key=True
    )
    course_id: Mapped[str | None] = mapped_column(ForeignKey("course_catalog.id"), nullable=True)
    activity_type: Mapped[str] = mapped_column(String(20))
    sessions: Mapped[int] = mapped_column(Integer)
    duration: Mapped[int] = mapped_column(Integer)
    required_equipment: Mapped[list[str]] = mapped_column(
        ARRAY(String(60)), default=list
    )
    instructors: Mapped[list[ActivityInstructor]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )
    groups: Mapped[list[ActivityGroup]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class ActivityInstructor(Base):
    __tablename__ = "activity_instructor"
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("teaching_activity.id", ondelete="CASCADE"), primary_key=True
    )
    instructor_id: Mapped[str] = mapped_column(
        ForeignKey("instructor.id"), primary_key=True
    )
    instructor: Mapped[InstructorDetail] = relationship()


class ActivityGroup(Base):
    __tablename__ = "activity_group"
    activity_id: Mapped[str] = mapped_column(
        ForeignKey("teaching_activity.id", ondelete="CASCADE"), primary_key=True
    )
    group_id: Mapped[str] = mapped_column(
        ForeignKey("student_group.id"), primary_key=True
    )
    group: Mapped[GroupDetail] = relationship()


class Rule(Base):
    __tablename__ = "rule"
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved')", name="valid_rule_status"),
        CheckConstraint("((type IN ('unavailable','preferred_period') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type='room_unavailable' AND room_id IS NOT NULL AND instructor_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type IN ('group_unavailable','group_allowed') AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND activity_id IS NULL) OR (type='activity_allowed' AND activity_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL) OR (type='activity_room' AND activity_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL) OR (type IN ('activities_not_same_day','lecture_before_tutorial','teaching_allowed','teaching_preferred') AND instructor_id IS NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type IN ('instructor_max_daily_hours','instructor_max_days') AND instructor_id IS NOT NULL AND room_id IS NULL AND group_id IS NULL AND activity_id IS NULL) OR (type='group_max_daily_hours' AND group_id IS NOT NULL AND instructor_id IS NULL AND room_id IS NULL AND activity_id IS NULL))", name="rule_target"),
        CheckConstraint("type IN ('unavailable','preferred_period','room_unavailable','group_unavailable','group_allowed','activity_allowed','lecture_before_tutorial','activity_room','activities_not_same_day','instructor_max_daily_hours','group_max_daily_hours','instructor_max_days','teaching_allowed','teaching_preferred') AND ((type NOT IN ('preferred_period','teaching_preferred') AND strength='mandatory') OR (type IN ('preferred_period','teaching_preferred') AND strength='preferred'))", name="rule_strength"),
        CheckConstraint("(type IN ('lecture_before_tutorial','activity_room','activities_not_same_day','instructor_max_daily_hours','group_max_daily_hours','instructor_max_days') AND start_hour IS NULL AND end_hour IS NULL AND day IS NULL) OR (type IN ('teaching_allowed','teaching_preferred','unavailable','preferred_period','room_unavailable','group_unavailable','group_allowed','activity_allowed') AND start_hour IS NOT NULL AND end_hour IS NOT NULL AND start_hour >= 0 AND end_hour <= 24 AND start_hour < end_hour AND start_hour * 2 = floor(start_hour * 2) AND end_hour * 2 = floor(end_hour * 2))", name="rule_hours"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    instructor_id: Mapped[str | None] = mapped_column(ForeignKey("instructor.id"), nullable=True)
    room_id: Mapped[str | None] = mapped_column(ForeignKey("room.id"), nullable=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("student_group.id"), nullable=True)
    activity_id: Mapped[str | None] = mapped_column(ForeignKey("teaching_activity.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(30))
    day: Mapped[str | None] = mapped_column(String(12), nullable=True)
    start_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    end_hour: Mapped[float | None] = mapped_column(Float, nullable=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    strength: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    approved_by: Mapped[str | None] = mapped_column(
        ForeignKey("app_user.id"), nullable=True
    )

    @property
    def data(self):
        return {
            key: getattr(self, key)
            for key in [
                "title",
                "instructor_id",
                "room_id",
                "group_id",
                "activity_id",
                "type",
                "day",
                "start_hour",
                "end_hour",
                "strength",
                "params",
            ]
        }

    @data.setter
    def data(self, body):
        for key, value in body.items():
            setattr(self, key, value)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    action: Mapped[str] = mapped_column(String(200))
    actor: Mapped[str] = mapped_column(String(100))
    action_code: Mapped[str] = mapped_column(String(60), default="legacy")
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    input_version: Mapped[int] = mapped_column(Integer)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeat"
    id: Mapped[int] = mapped_column(primary_key=True)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PasswordReset(Base):
    __tablename__ = "password_reset"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class LoginBucket(Base):
    __tablename__ = "login_bucket"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)


engine = create_engine(
    os.environ["DATABASE_URL"],
    pool_pre_ping=True,
    pool_timeout=5,
    connect_args={"connect_timeout": 3},
)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class ExamRun(Base):
    __tablename__ = "exam_run"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("exam_run.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    input_version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScheduleRun(Base):
    __tablename__ = "schedule_run"
    __table_args__ = (
        CheckConstraint("status IN ('queued','running','completed','blocked','infeasible','unknown','failed','cancelled')", name="schedule_status"),
        Index("one_active_schedule", "workspace_id", unique=True, postgresql_where=column("status").in_(["queued", "running"])),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    workspace_id: Mapped[int] = mapped_column(ForeignKey("workspace.id"), default=1)
    created_by: Mapped[str] = mapped_column(ForeignKey("app_user.id"))
    input_version: Mapped[int] = mapped_column(Integer)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="queued")
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    parent_run_id: Mapped[str | None] = mapped_column(ForeignKey("schedule_run.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssignmentLock(Base):
    __tablename__ = 'assignment_lock'
    __table_args__ = (
        CheckConstraint("status IN ('draft','approved')", name='assignment_lock_status'),
        CheckConstraint('occurrence >= 0 AND occurrence < 10', name='assignment_lock_occurrence'),
        CheckConstraint('(day IS NULL) = (start_minute IS NULL)', name='assignment_lock_time_pair'),
        CheckConstraint('start_minute IS NULL OR (start_minute >= 0 AND start_minute < 1440)', name='assignment_lock_minute'),
        CheckConstraint('instructor_id IS NOT NULL OR room_id IS NOT NULL OR day IS NOT NULL', name='assignment_lock_nonempty'),
        Index('assignment_lock_request', 'created_by', 'request_key', unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_run_id: Mapped[str] = mapped_column(ForeignKey('schedule_run.id'))
    activity_id: Mapped[str] = mapped_column(ForeignKey('teaching_activity.id'))
    occurrence: Mapped[int] = mapped_column(Integer)
    instructor_id: Mapped[str | None] = mapped_column(ForeignKey('instructor.id'), nullable=True)
    room_id: Mapped[str | None] = mapped_column(ForeignKey('room.id'), nullable=True)
    day: Mapped[str | None] = mapped_column(String(12), nullable=True)
    start_minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='draft')
    created_by: Mapped[str] = mapped_column(ForeignKey('app_user.id'))
    approved_by: Mapped[str | None] = mapped_column(ForeignKey('app_user.id'), nullable=True)
    request_key: Mapped[str] = mapped_column(String(36))
    request_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    @property
    def data(self):
        return {k:getattr(self,k) for k in ('id','source_run_id','activity_id','occurrence','instructor_id','room_id','day','start_minute','status','approved_by')}


class SourceTimetable(Base):
    __tablename__ = 'source_timetable'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    source_sha256: Mapped[str] = mapped_column(String(64), unique=True)
    source_document: Mapped[str] = mapped_column(String(200))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationReview(Base):
    __tablename__ = 'evaluation_review'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey('app_user.id'))
    reviewer_id: Mapped[str] = mapped_column(String(100))
    input_sha256: Mapped[str] = mapped_column(String(64))
    record: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvaluationAdjudication(Base):
    __tablename__ = 'evaluation_adjudication'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey('app_user.id'))
    first_review_id: Mapped[str] = mapped_column(ForeignKey('evaluation_review.id'))
    second_review_id: Mapped[str] = mapped_column(ForeignKey('evaluation_review.id'))
    adjudicator_id: Mapped[str] = mapped_column(String(100))
    input_sha256: Mapped[str] = mapped_column(String(64))
    record: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExtractionProposal(Base):
    __tablename__ = 'extraction_proposal'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey('app_user.id'))
    input_version: Mapped[int] = mapped_column(Integer)
    input_sha256: Mapped[str] = mapped_column(String(64))
    record: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExtractionProposalReview(Base):
    __tablename__ = 'extraction_proposal_review'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    proposal_id: Mapped[str] = mapped_column(ForeignKey('extraction_proposal.id'), unique=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey('app_user.id'))
    input_sha256: Mapped[str] = mapped_column(String(64))
    record: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExtractionJob(Base):
    __tablename__ = 'extraction_job'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    request_key: Mapped[str] = mapped_column(String(36), unique=True)
    submitted_by: Mapped[str] = mapped_column(ForeignKey('app_user.id'))
    input_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30))
    proposal_id: Mapped[str | None] = mapped_column(ForeignKey('extraction_proposal.id'), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdvisingStudent(Base):
    """A student whose courses differ from their home group's (retakes, drops, other sections)."""
    __tablename__ = "advising_student"
    __table_args__ = (Index("advising_student_code_ci", func.lower(column("code")), unique=True),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(100))
    group_id: Mapped[str | None] = mapped_column(ForeignKey("student_group.id", ondelete="SET NULL"), nullable=True)
    changes: Mapped[list["AdvisingChange"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class AdvisingChange(Base):
    """drop: not taking this home-group course. add: taking this course with another group."""
    __tablename__ = "advising_change"
    __table_args__ = (CheckConstraint("(action = 'drop' AND group_id IS NULL) OR (action = 'add' AND group_id IS NOT NULL)", name="advising_change_shape"),)
    student_id: Mapped[str] = mapped_column(ForeignKey("advising_student.id", ondelete="CASCADE"), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("course_catalog.id", ondelete="CASCADE"), primary_key=True)
    action: Mapped[str] = mapped_column(String(10), primary_key=True)
    group_id: Mapped[str | None] = mapped_column(ForeignKey("student_group.id", ondelete="CASCADE"), nullable=True)


class AssistantChat(Base):
    """One Ask JAI conversation of one admin; `state` is what the chat remembers (last request, people, rooms, groups)."""
    __tablename__ = "assistant_chat"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("app_user.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(120))
    state: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AssistantMessage(Base):
    __tablename__ = "assistant_message"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chat_id: Mapped[str] = mapped_column(ForeignKey("assistant_chat.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(10))
    body: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
