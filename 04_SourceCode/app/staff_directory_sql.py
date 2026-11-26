"""Add only staff read scopes to the versioned schedule procedure."""
from .class_eligibility_sql import MARKER, deploy as deploy_r2c, target_definition as r2c_definition


PROC_ARGS = '@actor int,@scope varchar(20),@id int=NULL'
DIRECTORY_ARGS = PROC_ARGS + """,
 @r2d_q nvarchar(100)=NULL,@r2d_status varchar(20)=NULL,@r2d_from date=NULL,@r2d_to date=NULL,
 @r2d_trainer int=NULL,@r2d_offset int=0"""
PAGE_SIZE = 10
GROUP_STATE = """CASE WHEN s.end_time<=@r2d_now THEN 'ended' WHEN s.start_time<=@r2d_now THEN 'in_progress'
           WHEN t.employment_status<>'ACTIVE' OR r.status<>'AVAILABLE' THEN 'closed'
           WHEN n.enrolled>=g.max_capacity THEN 'full' ELSE 'open' END"""
GROUP_ENROLLMENT = """CROSS APPLY(SELECT COUNT(*) AS enrolled FROM dbo.booking b
       WHERE b.session_id=s.session_id AND b.booking_status='SUCCESS') n"""
READ_SCOPE = f""" IF @scope IN ('desk_trainers','desk_trainer','desk_trainer_slots','desk_classes','desk_classes_one','desk_coaches')
 BEGIN
  IF @staff<>1 THROW 52201,'Front desk staff required',1;
  DECLARE @r2d_now datetime2(7)=SYSDATETIME(),@page_size int=10;

  IF @scope='desk_coaches'
  BEGIN
   SELECT t.person_id,p.full_name FROM dbo.trainer t JOIN dbo.person p ON p.person_id=t.person_id
    ORDER BY p.full_name,t.person_id;
   RETURN;
  END;

  IF @scope IN ('desk_trainers','desk_trainer')
  BEGIN
   WITH filtered AS (
    SELECT t.person_id,p.full_name,t.employment_status
     FROM dbo.trainer t JOIN dbo.person p ON p.person_id=t.person_id
     WHERE (@id IS NULL OR t.person_id=@id)
       AND (@r2d_q IS NULL OR CHARINDEX(@r2d_q,p.full_name)>0
            OR t.person_id=TRY_CONVERT(int,CASE WHEN LEFT(@r2d_q,1)='#' THEN SUBSTRING(@r2d_q,2,100) ELSE @r2d_q END))
       AND (@r2d_status IS NULL OR t.employment_status=@r2d_status)
   ), numbered AS (
    SELECT *,ROW_NUMBER() OVER(ORDER BY full_name,person_id) AS row_number FROM filtered
   )
   SELECT totals.total,f.person_id,f.full_name,f.employment_status,certs.certificates,
      upcoming.session_id,upcoming.start_time,upcoming.session_type,upcoming.class_name
   FROM (SELECT COUNT(*) AS total FROM filtered) totals
   OUTER APPLY (SELECT * FROM numbered WHERE row_number BETWEEN CAST(@r2d_offset AS bigint)+1 AND CAST(@r2d_offset AS bigint)+@page_size) f
   OUTER APPLY (SELECT STRING_AGG(CONVERT(nvarchar(max),x.certification),NCHAR(10))
                       WITHIN GROUP (ORDER BY x.certification) AS certificates
     FROM dbo.trainer_certification x WHERE x.person_id=f.person_id) certs
   OUTER APPLY (SELECT TOP (1) s.session_id,s.start_time,s.session_type,g.class_name
     FROM dbo.[session] s LEFT JOIN dbo.group_class_session g ON g.session_id=s.session_id
     WHERE s.trainer_id=f.person_id AND s.start_time>=@r2d_now ORDER BY s.start_time,s.session_id) upcoming
   ORDER BY f.row_number;
   RETURN;
  END;

  IF @scope='desk_trainer_slots'
  BEGIN
   WITH filtered AS (
    SELECT s.session_id,s.session_type,s.start_time,s.end_time,r.room_name,g.class_name
    FROM dbo.[session] s JOIN dbo.room r ON r.room_id=s.room_id LEFT JOIN dbo.group_class_session g ON g.session_id=s.session_id
    WHERE s.trainer_id=@id AND (@r2d_status IS NULL OR s.session_type=@r2d_status)
      AND (@r2d_from IS NULL OR s.start_time>=@r2d_from)
      AND (@r2d_to IS NULL OR s.start_time<DATEADD(day,1,@r2d_to))
   ), numbered AS (
    SELECT *,ROW_NUMBER() OVER(ORDER BY start_time,session_id) AS row_number FROM filtered
   )
   SELECT totals.total,f.session_id,f.session_type,f.start_time,f.end_time,f.room_name,f.class_name
   FROM (SELECT COUNT(*) AS total FROM filtered) totals
   OUTER APPLY (SELECT * FROM numbered WHERE row_number BETWEEN CAST(@r2d_offset AS bigint)+1 AND CAST(@r2d_offset AS bigint)+@page_size) f
   ORDER BY f.row_number;
   RETURN;
  END;

  WITH available AS (
   SELECT s.session_id,g.class_name,g.category,s.trainer_id,p.full_name,r.room_name,s.start_time,s.end_time,
      g.max_capacity,n.enrolled,g.max_capacity-n.enrolled AS remaining,
      {GROUP_STATE} AS class_state
   FROM dbo.group_class_session g JOIN dbo.[session] s ON s.session_id=g.session_id AND s.session_type='GROUP'
   JOIN dbo.room r ON r.room_id=s.room_id JOIN dbo.trainer t ON t.person_id=s.trainer_id JOIN dbo.person p ON p.person_id=t.person_id
   {GROUP_ENROLLMENT}
   WHERE (@id IS NULL OR s.session_id=@id) AND (@r2d_trainer IS NULL OR s.trainer_id=@r2d_trainer)
     AND (@r2d_q IS NULL OR CHARINDEX(@r2d_q,g.class_name)>0)
     AND (@r2d_from IS NULL OR s.start_time>=@r2d_from)
     AND (@r2d_to IS NULL OR s.start_time<DATEADD(day,1,@r2d_to))
  ), filtered AS (
   SELECT * FROM available WHERE @r2d_status IS NULL OR class_state=@r2d_status
  ), numbered AS (
   SELECT *,ROW_NUMBER() OVER(ORDER BY CASE WHEN class_state='in_progress' THEN 0
            WHEN start_time>@r2d_now THEN 1 ELSE 2 END,
        CASE WHEN start_time>@r2d_now THEN start_time END,start_time DESC,session_id) AS row_number FROM filtered
  )
  SELECT totals.total,f.session_id,f.class_name,f.category,f.trainer_id,f.full_name,f.room_name,
       f.start_time,f.end_time,f.max_capacity,f.enrolled,f.remaining,f.class_state
  FROM (SELECT COUNT(*) AS total FROM filtered) totals
  OUTER APPLY (SELECT * FROM numbered WHERE row_number BETWEEN CAST(@r2d_offset AS bigint)+1 AND CAST(@r2d_offset AS bigint)+@page_size) f
  ORDER BY f.row_number;
  RETURN;
 END;
"""


def target_definition(current, *, undo=False):
    if not current:
        raise ValueError('Thiếu thủ tục đọc lịch đã nghiệm thu.')
    current = current.replace('\r\n', '\n').strip()
    deployed = READ_SCOPE in current and DIRECTORY_ARGS in current
    legacy = current.replace(READ_SCOPE, '', 1).replace(DIRECTORY_ARGS, PROC_ARGS, 1)
    if r2c_definition(legacy) is not None or legacy.count(PROC_ARGS) != 1 or legacy.count(MARKER) != 1:
        raise ValueError('Cần đúng định nghĩa lịch R2C trước khi bổ sung tra cứu tại quầy.')
    if deployed == (not undo):
        return None
    selected = legacy if undo else legacy.replace(PROC_ARGS, DIRECTORY_ARGS, 1).replace(MARKER, READ_SCOPE + MARKER, 1)
    return selected.replace('CREATE PROCEDURE dbo.local03_schedule', 'ALTER PROCEDURE dbo.local03_schedule', 1)


def deploy(cursor, *, undo=False):
    definition = "SELECT OBJECT_DEFINITION(OBJECT_ID(N'dbo.local03_schedule'))"
    current = cursor.execute(definition).fetchval()
    if not undo:
        # Allow existing 06A installations to skip directly to the combined read upgrade.
        base = current.replace('\r\n', '\n') if current else ''
        if READ_SCOPE not in base:
            deploy_r2c(cursor)
            current = cursor.execute(definition).fetchval()
    sql = target_definition(current, undo=undo)
    if sql is None:
        return False
    cursor.execute(sql)
    if target_definition(cursor.execute(definition).fetchval(), undo=undo) is not None:
        raise RuntimeError('Không xác minh được định nghĩa tra cứu tại quầy.')
    return True
