from datetime import date
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
    model_serializer,
)
from typing_extensions import Annotated

Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
Code = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Strict):
    email: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=200)
    ]
    password: str = Field(min_length=1, max_length=200)


class Instructor(Strict):
    day_off: Literal["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"] | None = None
    position: Literal["doctor", "ta"] | None = None
    max_weekly_hours: float | None = Field(default=None, ge=0, le=168, multiple_of=0.5, allow_inf_nan=False, strict=True)
    name: Name
    code: Code
    department: Name


class Course(Strict):
    course_id: str | None = None
    name: Name
    code: Code
    activity_type: Literal["lecture", "tutorial", "lab"]
    sessions: int = Field(ge=1, le=10)
    duration: int = Field(ge=30, le=240, multiple_of=30)
    eligible_instructors: list[str] = Field(min_length=1, max_length=30)
    group_ids: list[str] = Field(min_length=1, max_length=30)
    required_equipment: list[
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
        ]
    ] = Field(default_factory=list, max_length=30)

    @field_validator("eligible_instructors", "group_ids")
    @classmethod
    def unique_ids(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("duplicate references")
        return values


class Room(Strict):
    name: Name
    code: Code
    source_info: dict = Field(default_factory=dict)
    capacity: int | None = Field(default=None, ge=1, le=2000)
    room_type: Literal["lecture", "lab", "flexible", "exam_hall"] | None = None
    room_types: list[Literal["lecture", "lab", "flexible", "exam_hall"]] = Field(default_factory=list, max_length=4)

    @model_validator(mode="after")
    def normalize_room_types(self):
        if self.capacity is None and not self.source_info.get("source_document"):
            raise ValueError("Room capacity is required")
        if not self.room_types:
            if self.room_type is None:
                if self.capacity is None and self.source_info.get("source_document"):
                    return self
                raise ValueError("Select at least one room type")
            self.room_types = [self.room_type]
        if len(set(self.room_types)) != len(self.room_types):
            raise ValueError("Duplicate room types")
        self.room_type = self.room_types[0]
        return self
    equipment: list[
        Annotated[
            str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)
        ]
    ] = Field(default_factory=list, max_length=30)
    # Who may use the room: programmes and/or catalogue courses. Empty = everyone.
    reserved_majors: list[Name] = Field(default_factory=list, max_length=50)
    reserved_course_ids: list[str] = Field(default_factory=list, max_length=200)


class Group(Strict):
    name: Name
    code: Code
    size: int = Field(ge=1, le=2000)
    year: int | None = Field(default=None, ge=1, le=12, strict=True)
    major: Name | None = None


class RuleParams(Strict):
    activity_types: list[Literal['lecture', 'tutorial', 'lab']] | None = Field(default=None, min_length=1, max_length=3)

    @model_serializer(mode='wrap')
    def serialize(self, handler):
        values = handler(self)
        if values.get('activity_types') is None:
            values.pop('activity_types', None)
        return values

    room_ids: list[str] | None = Field(default=None, min_length=1, max_length=20)
    activity_ids: list[str] | None = Field(default=None, min_length=2, max_length=10)
    hours: float | None = Field(default=None, gt=0, le=24, multiple_of=0.5, allow_inf_nan=False)
    days: int | None = Field(default=None, ge=1, le=7)


class RuleInput(Strict):
    activity_id: str | None = None
    title: Name
    instructor_id: str | None = None
    room_id: str | None = None
    group_id: str | None = None
    type: Literal["teaching_allowed", "teaching_preferred", "unavailable", "preferred_period", "room_unavailable", "group_unavailable", "group_allowed", "activity_allowed",
                  "lecture_before_tutorial", "activity_room", "activities_not_same_day", "instructor_max_daily_hours", "group_max_daily_hours", "instructor_max_days"]
    # None means every teaching day; limit rules have no day or hours.
    day: Literal[
        "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"
    ] | None = None
    start_hour: float | None = Field(default=None, ge=0, le=23.5, multiple_of=0.5, allow_inf_nan=False)
    end_hour: float | None = Field(default=None, ge=0.5, le=24, multiple_of=0.5, allow_inf_nan=False)
    strength: Literal["mandatory", "preferred"]
    params: RuleParams = Field(default_factory=RuleParams)


SCHEMAS = {"instructors": Instructor, "courses": Course, "rooms": Room, "groups": Group}


class NewUser(Strict):
    group_id: str | None = None
    advising_student_id: str | None = None
    instructor_id: str | None = None
    name: Name
    email: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=3,
            max_length=200,
            pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$",
        ),
    ]
    role: Literal["administrator", "viewer", "student", "instructor"] = "viewer"


class UserUpdate(Strict):
    group_id: str | None = None
    advising_student_id: str | None = None
    instructor_id: str | None = None
    name: Name
    role: Literal["administrator", "viewer", "student", "instructor"]
    active: bool


class PasswordChange(Strict):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=15, max_length=200)


class ResetPassword(Strict):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=15, max_length=200)


class TeachingPeriod(Strict):
    start: int = Field(ge=0, lt=1440, strict=True)
    end: int = Field(gt=0, le=1440, strict=True)


class RealismPolicy(Strict):
    student_daily_hours: float | None = Field(default=None, ge=0, le=24, multiple_of=0.5, allow_inf_nan=False, strict=True)
    instructor_daily_hours: float | None = Field(default=None, ge=0, le=24, multiple_of=0.5, allow_inf_nan=False, strict=True)
    spread_activity_days: bool = False
    max_consecutive_periods: int | None = Field(default=None, ge=1, le=24, strict=True)
    max_idle_periods: int | None = Field(default=None, ge=0, le=24, strict=True)
    compact_days: bool = False


class CalendarInput(Strict):
    realism_policy: RealismPolicy = Field(default_factory=RealismPolicy)
    name: Name
    term: Name
    timezone: str = Field(min_length=1, max_length=100)
    days: list[
        Literal[
            "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"
        ]
    ] = Field(min_length=1, max_length=7)
    start_hour: int = Field(ge=0, le=23)
    end_hour: int = Field(ge=1, le=24)
    teaching_periods: list[TeachingPeriod] = Field(default_factory=list, max_length=24)
    period_minutes: Literal[30, 60]
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def coherent(self):
        if self.end_hour <= self.start_hour or len(set(self.days)) != len(self.days):
            raise ValueError("invalid calendar")
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("invalid dates")
        if bool(self.start_date) != bool(self.end_date):
            raise ValueError("supply both dates")
        if self.realism_policy != RealismPolicy() and not self.teaching_periods:
            raise ValueError("realism policy requires named teaching periods")
        previous = -1
        for period in self.teaching_periods:
            if period.start < self.start_hour * 60 or period.end > self.end_hour * 60 or period.start >= period.end or period.start < previous:
                raise ValueError("invalid teaching periods")
            previous = period.end
        try:
            ZoneInfo(self.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("invalid timezone")
        return self


class CSVInput(Strict):
    csv: str = Field(min_length=1, max_length=1000000)
