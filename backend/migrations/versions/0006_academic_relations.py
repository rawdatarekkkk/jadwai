"""Normalize academic fields and enforce real instructor/group references."""

from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade():
    op.execute(
        "ALTER TABLE record ADD COLUMN name varchar(100),ADD COLUMN code varchar(20)"
    )
    op.execute("UPDATE record SET name=data->>'name',code=data->>'code'")
    op.execute(
        "ALTER TABLE record ALTER COLUMN name SET NOT NULL,ALTER COLUMN code SET NOT NULL"
    )
    op.execute("CREATE UNIQUE INDEX record_kind_code_ci ON record(kind,lower(code))")
    op.execute(
        "CREATE TABLE instructor(id varchar(36) PRIMARY KEY REFERENCES record(id) ON DELETE CASCADE,department varchar(100) NOT NULL)"
    )
    op.execute(
        "CREATE TABLE room(id varchar(36) PRIMARY KEY REFERENCES record(id) ON DELETE CASCADE,capacity integer NOT NULL CHECK(capacity BETWEEN 1 AND 2000),room_type varchar(20) NOT NULL CHECK(room_type IN ('lecture','lab','flexible')),equipment varchar(60)[] NOT NULL DEFAULT '{}')"
    )
    op.execute(
        "CREATE TABLE student_group(id varchar(36) PRIMARY KEY REFERENCES record(id) ON DELETE CASCADE,size integer NOT NULL CHECK(size BETWEEN 1 AND 2000))"
    )
    op.execute(
        "CREATE TABLE teaching_activity(id varchar(36) PRIMARY KEY REFERENCES record(id) ON DELETE CASCADE,activity_type varchar(20) NOT NULL CHECK(activity_type IN ('lecture','tutorial','lab')),sessions integer NOT NULL CHECK(sessions BETWEEN 1 AND 10),duration integer NOT NULL CHECK(duration BETWEEN 30 AND 240 AND duration % 30 = 0),required_equipment varchar(60)[] NOT NULL DEFAULT '{}')"
    )
    op.execute(
        "CREATE TABLE activity_instructor(activity_id varchar(36) REFERENCES teaching_activity(id) ON DELETE CASCADE,instructor_id varchar(36) REFERENCES instructor(id),PRIMARY KEY(activity_id,instructor_id))"
    )
    op.execute(
        "CREATE TABLE activity_group(activity_id varchar(36) REFERENCES teaching_activity(id) ON DELETE CASCADE,group_id varchar(36) REFERENCES student_group(id),PRIMARY KEY(activity_id,group_id))"
    )
    op.execute(
        "INSERT INTO instructor SELECT id,data->>'department' FROM record WHERE kind='instructors'"
    )
    op.execute(
        "INSERT INTO room(id,capacity,room_type) SELECT id,(data->>'capacity')::integer,data->>'room_type' FROM record WHERE kind='rooms'"
    )
    op.execute(
        "INSERT INTO student_group SELECT id,(data->>'size')::integer FROM record WHERE kind='groups'"
    )
    op.execute(
        "INSERT INTO teaching_activity(id,activity_type,sessions,duration) SELECT id,data->>'activity_type',(data->>'sessions')::integer,(data->>'duration')::integer FROM record WHERE kind='courses'"
    )
    op.execute("UPDATE room r SET equipment=ARRAY(SELECT json_array_elements_text(s.data->'equipment')) FROM record s WHERE s.id=r.id AND json_typeof(s.data->'equipment')='array'")
    op.execute("UPDATE teaching_activity r SET required_equipment=ARRAY(SELECT json_array_elements_text(s.data->'required_equipment')) FROM record s WHERE s.id=r.id AND json_typeof(s.data->'required_equipment')='array'")
    op.execute(
        "INSERT INTO activity_instructor SELECT id,json_array_elements_text(data->'eligible_instructors') FROM record WHERE kind='courses'"
    )
    op.execute(
        "INSERT INTO activity_group SELECT id,json_array_elements_text(data->'group_ids') FROM record WHERE kind='courses'"
    )
    op.execute(
        "ALTER TABLE rule ADD COLUMN title varchar(100),ADD COLUMN instructor_id varchar(36) REFERENCES instructor(id),ADD COLUMN type varchar(30),ADD COLUMN day varchar(12),ADD COLUMN start_hour integer,ADD COLUMN end_hour integer,ADD COLUMN strength varchar(20)"
    )
    op.execute(
        "UPDATE rule SET title=data->>'title',instructor_id=data->>'instructor_id',type=data->>'type',day=data->>'day',start_hour=(data->>'start_hour')::integer,end_hour=(data->>'end_hour')::integer,strength=data->>'strength'"
    )
    for column in [
        "title",
        "instructor_id",
        "type",
        "day",
        "start_hour",
        "end_hour",
        "strength",
    ]:
        op.execute(f"ALTER TABLE rule ALTER COLUMN {column} SET NOT NULL")
    op.execute(
        "ALTER TABLE rule ADD CONSTRAINT rule_strength CHECK(type IN ('unavailable','preferred_period') AND ((type='unavailable' AND strength='mandatory') OR (type='preferred_period' AND strength='preferred'))),ADD CONSTRAINT rule_hours CHECK(start_hour>=0 AND end_hour<=24 AND start_hour<end_hour)"
    )
    op.execute("ALTER TABLE rule DROP COLUMN data")
    op.execute("ALTER TABLE record DROP COLUMN data")
    # Deferred checks allow parent and detail rows to be inserted atomically while
    # rejecting orphan/wrong-kind records and activities without eligibility/groups.
    op.execute("""CREATE FUNCTION check_academic_record() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE rid text; k text; n integer;
    BEGIN
      IF TG_TABLE_NAME IN ('activity_instructor','activity_group') THEN rid=COALESCE(NEW.activity_id,OLD.activity_id); ELSE rid=COALESCE(NEW.id,OLD.id); END IF;
      SELECT kind INTO k FROM record WHERE id=rid;
      IF NOT FOUND THEN RETURN NULL; END IF;
      SELECT (EXISTS(SELECT 1 FROM instructor WHERE id=rid))::integer+(EXISTS(SELECT 1 FROM room WHERE id=rid))::integer+(EXISTS(SELECT 1 FROM student_group WHERE id=rid))::integer+(EXISTS(SELECT 1 FROM teaching_activity WHERE id=rid))::integer INTO n;
      IF n<>1 OR (k='instructors' AND NOT EXISTS(SELECT 1 FROM instructor WHERE id=rid)) OR (k='rooms' AND NOT EXISTS(SELECT 1 FROM room WHERE id=rid)) OR (k='groups' AND NOT EXISTS(SELECT 1 FROM student_group WHERE id=rid)) OR (k='courses' AND NOT EXISTS(SELECT 1 FROM teaching_activity WHERE id=rid)) THEN RAISE EXCEPTION 'academic_record_kind_mismatch' USING ERRCODE='23514'; END IF;
      IF k='courses' AND (NOT EXISTS(SELECT 1 FROM activity_instructor WHERE activity_id=rid) OR NOT EXISTS(SELECT 1 FROM activity_group WHERE activity_id=rid)) THEN RAISE EXCEPTION 'activity_requires_eligibility_and_groups' USING ERRCODE='23514'; END IF;
      RETURN NULL;
    END $$""")
    for table in [
        "record",
        "instructor",
        "room",
        "student_group",
        "teaching_activity",
        "activity_instructor",
        "activity_group",
    ]:
        op.execute(
            f"CREATE CONSTRAINT TRIGGER academic_integrity AFTER INSERT OR UPDATE OR DELETE ON {table} DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION check_academic_record()"
        )


def downgrade():
    for table in [
        "record",
        "instructor",
        "room",
        "student_group",
        "teaching_activity",
        "activity_instructor",
        "activity_group",
    ]:
        op.execute(f"DROP TRIGGER academic_integrity ON {table}")
    op.execute("DROP FUNCTION check_academic_record()")
    op.execute("ALTER TABLE record ADD COLUMN data json")
    op.execute(
        "UPDATE record r SET data=json_build_object('name',r.name,'code',r.code,'department',i.department) FROM instructor i WHERE i.id=r.id"
    )
    op.execute(
        "UPDATE record r SET data=json_build_object('name',r.name,'code',r.code,'capacity',i.capacity,'room_type',i.room_type,'equipment',i.equipment) FROM room i WHERE i.id=r.id"
    )
    op.execute(
        "UPDATE record r SET data=json_build_object('name',r.name,'code',r.code,'size',i.size) FROM student_group i WHERE i.id=r.id"
    )
    op.execute(
        "UPDATE record r SET data=json_build_object('name',r.name,'code',r.code,'activity_type',i.activity_type,'sessions',i.sessions,'duration',i.duration,'required_equipment',i.required_equipment,'eligible_instructors',(SELECT json_agg(instructor_id) FROM activity_instructor WHERE activity_id=r.id),'group_ids',(SELECT json_agg(group_id) FROM activity_group WHERE activity_id=r.id)) FROM teaching_activity i WHERE i.id=r.id"
    )
    op.execute("ALTER TABLE rule ADD COLUMN data json")
    op.execute(
        "UPDATE rule SET data=json_build_object('title',title,'instructor_id',instructor_id,'type',type,'day',day,'start_hour',start_hour,'end_hour',end_hour,'strength',strength)"
    )
    op.execute("ALTER TABLE rule ALTER COLUMN data SET NOT NULL")
    op.execute(
        "ALTER TABLE rule DROP CONSTRAINT rule_strength,DROP CONSTRAINT rule_hours"
    )
    for column in [
        "title",
        "instructor_id",
        "type",
        "day",
        "start_hour",
        "end_hour",
        "strength",
    ]:
        op.execute(f"ALTER TABLE rule DROP COLUMN {column}")
    for table in [
        "activity_instructor",
        "activity_group",
        "teaching_activity",
        "instructor",
        "room",
        "student_group",
    ]:
        op.drop_table(table)
    op.execute("DROP INDEX record_kind_code_ci")
    op.execute(
        "ALTER TABLE record ALTER COLUMN data SET NOT NULL,DROP COLUMN name,DROP COLUMN code"
    )
