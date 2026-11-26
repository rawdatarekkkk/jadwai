-- Applied by push.sh to a throwaway copy of the local demo database before it is uploaded.
-- Removes sign-in state and everything created by the temporary test accounts (audit.*@demo.test),
-- then restores the input version those tests bumped, so the published timetable is current again.
-- The real append-only guards are switched off only inside this copy, and switched back on.
begin;
create temporary table testers as select id from app_user where email like 'audit.%@demo.test';
alter table audit disable trigger user;
alter table extraction_proposal disable trigger user;
alter table extraction_proposal_review disable trigger user;
delete from session; delete from password_reset; delete from login_bucket;
delete from rule where approved_by in (select id from testers);
delete from extraction_proposal_review where submitted_by in (select id from testers)
   or proposal_id in (select id from extraction_proposal where submitted_by in (select id from testers));
update extraction_job set proposal_id = null where submitted_by in (select id from testers);
delete from extraction_proposal where submitted_by in (select id from testers);
delete from extraction_job where submitted_by in (select id from testers);
update extraction_job set status = 'abandoned' where status = 'running';
delete from assistant_message where chat_id in (select id from assistant_chat where user_id in (select id from testers));
delete from assistant_chat where user_id in (select id from testers);
delete from audit where actor in ('Audit Admin', 'Audit Student') or action like '%Audit Admin%' or action like '%Audit Student%';
delete from app_user where id in (select id from testers);
-- Inputs are back to what the published timetable was built from.
update workspace set version = (select max(input_version) from schedule_run where published_at is not null)
 where id = 1 and exists (select 1 from schedule_run where published_at is not null);
alter table audit enable trigger user;
alter table extraction_proposal enable trigger user;
alter table extraction_proposal_review enable trigger user;
commit;
