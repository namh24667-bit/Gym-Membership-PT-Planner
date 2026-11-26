"""Read a trainer's assignments without granting direct access to member data."""
import re

from .class_eligibility_sql import MARKER
from .staff_directory_sql import GROUP_ENROLLMENT, GROUP_STATE, PAGE_SIZE, deploy as deploy_r2d, target_definition as r2d_definition


TIME_STATE = """CASE WHEN s.end_time<=@r2e_now THEN 'ended'
               WHEN s.start_time<=@r2e_now THEN 'in_progress' ELSE 'upcoming' END"""
CLASS_STATE = GROUP_STATE.replace('@r2d_now', '@r2e_now')
READ_SCOPE = f""" IF @scope IN ('teach_agenda','teach_detail','teach_roster')
 BEGIN
  IF @trainer<>1 THROW 52201,'Assigned trainer required',1;
  DECLARE @r2e_now datetime2(7)=SYSDATETIME(),@r2e_limit int={PAGE_SIZE};
  IF @scope='teach_detail'
  BEGIN
   SELECT s.session_id,s.session_type,s.start_time,s.end_time,r.room_name,g.class_name,p.full_name,x.person_id,
      x.training_focus,g.max_capacity,CASE WHEN g.session_id IS NOT NULL THEN n.enrolled END,
      g.max_capacity-n.enrolled,{TIME_STATE},
      CASE WHEN g.session_id IS NOT NULL THEN {CLASS_STATE} END,t.employment_status,
      CASE WHEN s.session_type='PERSONAL' AND s.end_time>@r2e_now AND t.employment_status='ACTIVE'
                 AND r.status='AVAILABLE' THEN NULLIF(LTRIM(RTRIM(p.phone)),'') END AS contact_phone
   FROM dbo.[session] s JOIN dbo.room r ON r.room_id=s.room_id JOIN dbo.trainer t ON t.person_id=s.trainer_id
   LEFT JOIN dbo.pt_session x ON x.session_id=s.session_id AND s.session_type='PERSONAL'
   LEFT JOIN dbo.person p ON p.person_id=x.person_id
   LEFT JOIN dbo.group_class_session g ON g.session_id=s.session_id AND s.session_type='GROUP'
   {GROUP_ENROLLMENT}
   WHERE s.session_id=@id AND s.trainer_id=@actor AND t.employment_status IN ('ACTIVE','ON_LEAVE')
        AND (x.session_id IS NOT NULL OR g.session_id IS NOT NULL);
   RETURN;
  END;

  IF @scope='teach_roster'
  BEGIN
   WITH assigned AS (
    SELECT g.session_id,g.class_name FROM dbo.group_class_session g JOIN dbo.[session] s ON s.session_id=g.session_id
    JOIN dbo.trainer t ON t.person_id=s.trainer_id WHERE s.session_id=@id AND s.session_type='GROUP'
      AND s.trainer_id=@actor AND t.employment_status IN ('ACTIVE','ON_LEAVE')
   ), registered AS (
    SELECT b.person_id,p.full_name,b.booking_status
      FROM assigned a JOIN dbo.booking b ON b.session_id=a.session_id AND b.booking_status='SUCCESS'
      JOIN dbo.person p ON p.person_id=b.person_id
   ), numbered AS (
    SELECT person_id,full_name,booking_status,ROW_NUMBER() OVER(ORDER BY full_name,person_id) AS row_number FROM registered
   )
   SELECT totals.total,a.class_name,f.person_id,f.full_name,f.booking_status FROM assigned a
   CROSS JOIN (SELECT COUNT(*) AS total FROM registered) totals
   OUTER APPLY (SELECT person_id,full_name,booking_status,row_number FROM numbered
      WHERE row_number BETWEEN CAST(@r2d_offset AS bigint)+1 AND CAST(@r2d_offset AS bigint)+@r2e_limit) f
   ORDER BY f.row_number;
   RETURN;
  END;

  IF @r2d_from IS NULL OR @r2d_to IS NULL OR @r2d_to='9999-12-31'
     OR DATEDIFF(day,@r2d_from,@r2d_to) NOT BETWEEN 0 AND 6 THROW 52205,'Invalid agenda range',1;
  -- The existing optional query and status arguments carry the session kind and time state here.
  WITH agenda AS (
   SELECT s.session_id,s.session_type,s.start_time,s.end_time,r.room_name,g.class_name,p.full_name,
       g.max_capacity,CASE WHEN g.session_id IS NOT NULL THEN n.enrolled END AS enrolled,
       g.max_capacity-n.enrolled AS remaining,{TIME_STATE} AS time_state
   FROM dbo.[session] s JOIN dbo.room r ON r.room_id=s.room_id JOIN dbo.trainer t ON t.person_id=s.trainer_id
   LEFT JOIN dbo.pt_session x ON x.session_id=s.session_id AND s.session_type='PERSONAL'
   LEFT JOIN dbo.person p ON p.person_id=x.person_id
   LEFT JOIN dbo.group_class_session g ON g.session_id=s.session_id AND s.session_type='GROUP'
   {GROUP_ENROLLMENT}
   WHERE s.trainer_id=@actor AND t.employment_status IN ('ACTIVE','ON_LEAVE')
     AND s.start_time>=@r2d_from AND s.start_time<DATEADD(day,1,@r2d_to)
     AND (x.session_id IS NOT NULL OR g.session_id IS NOT NULL)
  ), filtered AS (
   SELECT session_id,session_type,start_time,end_time,room_name,class_name,full_name,
       max_capacity,enrolled,remaining,time_state,
       ROW_NUMBER() OVER(ORDER BY CASE time_state WHEN 'in_progress' THEN 0 WHEN 'upcoming' THEN 1 ELSE 2 END,
           CASE WHEN time_state<>'ended' THEN start_time END,start_time DESC,session_id) AS row_number
     FROM agenda WHERE (@r2d_q IS NULL OR session_type=@r2d_q)
       AND (@r2d_status IS NULL OR time_state=@r2d_status)
  ), summary AS (
   SELECT COUNT(CASE WHEN session_type='PERSONAL' THEN 1 END) AS pt,
      COUNT(CASE WHEN session_type='GROUP' THEN 1 END) AS groups,
      COUNT(CASE WHEN time_state='upcoming' THEN 1 END) AS upcoming,
      COUNT(CASE WHEN time_state='ended' THEN 1 END) AS ended,
      COUNT(CASE WHEN time_state='in_progress' THEN 1 END) AS in_progress FROM agenda
  )
  SELECT totals.total,a.pt,a.groups,a.upcoming,a.ended,a.in_progress,t.hire_date,t.employment_status,
       f.session_id,f.session_type,f.start_time,f.end_time,f.room_name,f.class_name,f.full_name,
       f.max_capacity,f.enrolled,f.remaining,f.time_state
  FROM dbo.trainer t CROSS JOIN summary a CROSS JOIN (SELECT COUNT(*) AS total FROM filtered) totals
  OUTER APPLY (SELECT session_id,session_type,start_time,end_time,room_name,class_name,full_name,
       max_capacity,enrolled,remaining,time_state,row_number FROM filtered
       WHERE row_number BETWEEN CAST(@r2d_offset AS bigint)+1 AND CAST(@r2d_offset AS bigint)+@r2e_limit) f
  WHERE t.person_id=@actor AND t.employment_status IN ('ACTIVE','ON_LEAVE')
  ORDER BY f.row_number;
  RETURN;
 END;
"""


def target_definition(current, *, undo=False):
    if not current:
        raise ValueError('Thiếu thủ tục đọc lịch đã nghiệm thu.')
    current = current.replace('\r\n', '\n').strip()
    deployed = READ_SCOPE in current
    baseline = current.replace(READ_SCOPE, '', 1)
    if baseline.count(MARKER) != 1 or r2d_definition(baseline) is not None:
        raise ValueError('Cần đúng thủ tục lịch R2D trước khi cập nhật lịch HLV.')
    if deployed == (not undo):
        return None
    revised = baseline if undo else baseline.replace(MARKER, READ_SCOPE + MARKER, 1)
    return re.sub(r'^(?:CREATE|ALTER)(?:\s+OR\s+ALTER)?(?=\s+PROCEDURE\b)', 'ALTER', revised, count=1, flags=re.I)


def deploy(cursor, *, undo=False):
    definition = "SELECT OBJECT_DEFINITION(OBJECT_ID(N'dbo.local03_schedule'))"
    current = cursor.execute(definition).fetchval()
    if not undo and READ_SCOPE not in (current or '').replace('\r\n', '\n'):
        deploy_r2d(cursor)
        current = cursor.execute(definition).fetchval()
    updated = target_definition(current, undo=undo)
    if updated is None:
        return False
    cursor.execute(updated)
    if target_definition(cursor.execute(definition).fetchval(), undo=undo) is not None:
        raise RuntimeError('Không xác minh được định nghĩa lịch HLV.')
    return True
