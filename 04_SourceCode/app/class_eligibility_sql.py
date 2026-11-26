"""Version the additional read scope of dbo.local03_schedule in place."""
from hashlib import sha256
import re


SCOPE = 'class_eligibility'
ORIGINAL_HASH = 'af3512eeeb23f8d1ea89a2ff346f5643b4b31752c55f5a90b5ed0d93bcc99cb6'
MARKER = " IF @scope='classes' AND (@member=1 OR @staff=1)"
READ_SCOPE = """ IF @scope='class_eligibility' AND @member=1
 BEGIN
  -- Advisory only. local03_book_group rechecks under locks before every write.
  DECLARE @r2c_now datetime2(7)=SYSDATETIME(),@r2c_today date,
      @r2c_membership int,@r2c_plan int,@r2c_start date,@r2c_end date,
      @r2c_service int,@r2c_matches int,@r2c_quota int,@r2c_used bigint=0,@r2c_pending varchar(25);
  SET @r2c_today=CONVERT(date,@r2c_now);
  SELECT @r2c_membership=membership_id,@r2c_plan=plan_id,@r2c_start=start_date,@r2c_end=end_date
    FROM dbo.membership WHERE person_id=@actor AND status='ACTIVE'
      AND @r2c_today BETWEEN start_date AND end_date;
  IF @r2c_membership IS NULL
   SELECT TOP(1) @r2c_pending=CASE
         WHEN status='ACTIVE' AND start_date>@r2c_today THEN 'future'
         WHEN status='PENDING_ACTIVATION' THEN 'pending_activation'
         WHEN status='PENDING_PAYMENT' THEN 'pending_payment'
         WHEN status='EXPIRED' OR (status='ACTIVE' AND end_date<@r2c_today) THEN 'expired'
         ELSE 'no_contract' END
     FROM dbo.membership WHERE person_id=@actor
     ORDER BY CASE WHEN status='ACTIVE' AND start_date>@r2c_today THEN 0
           WHEN status='PENDING_ACTIVATION' THEN 1 WHEN status='PENDING_PAYMENT' THEN 2 ELSE 3 END,
           membership_id DESC;
  ELSE
  BEGIN
    -- Match local03_entitlement. Only -1 means unlimited.
    SELECT @r2c_matches=COUNT(*),@r2c_service=MAX(i.service_type_id),@r2c_quota=MAX(i.quota_per_cycle)
      FROM dbo.plan_inclusion i JOIN dbo.service_type t ON t.service_type_id=i.service_type_id
      WHERE i.plan_id=@r2c_plan AND t.service_name=N'Lớp nhóm';
    IF @r2c_matches=1 AND @r2c_quota>=0
      SELECT @r2c_used=COUNT_BIG(*) FROM dbo.member_service_usage
       WHERE membership_id=@r2c_membership AND service_type_id=@r2c_service AND usage_status='USED';
  END;
  WITH classes AS (
   SELECT TOP (150) s.session_id,g.class_name,g.category,p.full_name,r.room_name,s.start_time,s.end_time,
       g.max_capacity,t.employment_status,r.status AS room_status
   FROM dbo.group_class_session g JOIN dbo.[session] s ON s.session_id=g.session_id AND s.session_type='GROUP'
   JOIN dbo.room r ON r.room_id=s.room_id JOIN dbo.trainer t ON t.person_id=s.trainer_id
   JOIN dbo.person p ON p.person_id=t.person_id
   WHERE @id IS NULL OR s.session_id=@id
   ORDER BY CASE WHEN s.start_time>@r2c_now THEN 0 ELSE 1 END,
     CASE WHEN s.start_time>@r2c_now THEN s.start_time END,
     s.start_time DESC,s.session_id
  ), own_schedule AS (
   SELECT x.session_id,s.start_time,s.end_time
     FROM dbo.pt_session x JOIN dbo.[session] s ON s.session_id=x.session_id
     WHERE x.person_id=@actor
   UNION ALL
   SELECT b.session_id,s.start_time,s.end_time
     FROM dbo.booking b JOIN dbo.[session] s ON s.session_id=b.session_id
     WHERE b.person_id=@actor AND b.booking_status='SUCCESS'
  )
  SELECT c.session_id,c.class_name,c.category,c.full_name,c.room_name,c.start_time,c.end_time,c.max_capacity,
    n.enrolled,c.max_capacity-n.enrolled AS remaining,b.booking_status,COALESCE(b.booking_id,0) AS last_booking,
    CASE WHEN c.end_time<=@r2c_now THEN 'ended' WHEN c.start_time<=@r2c_now THEN 'in_progress'
         WHEN c.employment_status<>'ACTIVE' OR c.room_status<>'AVAILABLE' THEN 'closed'
         WHEN n.enrolled>=c.max_capacity THEN 'full' ELSE 'open' END AS class_state,
    CASE WHEN b.booking_status='SUCCESS' THEN 'booked'
         WHEN c.end_time<=@r2c_now THEN 'ended' WHEN c.start_time<=@r2c_now THEN 'in_progress'
         WHEN c.employment_status<>'ACTIVE' OR c.room_status<>'AVAILABLE' THEN 'closed'
         WHEN @r2c_membership IS NULL THEN COALESCE(@r2c_pending,'no_contract')
         WHEN CONVERT(date,c.start_time)<@r2c_start OR CONVERT(date,c.end_time)>@r2c_end THEN 'outside_dates'
         WHEN @r2c_matches=0 THEN 'no_benefit'
         WHEN @r2c_matches<>1 OR @r2c_quota IS NULL THEN 'benefit_unknown'
         WHEN @r2c_quota<>-1 AND @r2c_used>=@r2c_quota THEN 'quota'
         WHEN n.enrolled>=c.max_capacity THEN 'full'
         WHEN EXISTS (SELECT 1 FROM own_schedule mine WHERE mine.session_id<>c.session_id
                     AND c.start_time<mine.end_time AND mine.start_time<c.end_time) THEN 'conflict'
         ELSE 'eligible' END AS reason,
    CASE WHEN @r2c_matches=1 AND CONVERT(date,c.start_time)>=@r2c_start AND CONVERT(date,c.end_time)<=@r2c_end
         THEN CASE WHEN @r2c_quota=-1 THEN -1 WHEN @r2c_quota>=@r2c_used THEN @r2c_quota-@r2c_used
                   WHEN @r2c_quota>=0 THEN 0 END END AS quota_remaining
  FROM classes c
  CROSS APPLY(SELECT COUNT(*) AS enrolled FROM dbo.booking x
      WHERE x.session_id=c.session_id AND x.booking_status='SUCCESS') n
  OUTER APPLY(SELECT TOP (1) x.booking_id,x.booking_status FROM dbo.booking x
      WHERE x.session_id=c.session_id AND x.person_id=@actor ORDER BY x.booking_id DESC) b
  ORDER BY CASE WHEN c.start_time>@r2c_now THEN 0 ELSE 1 END,
      CASE WHEN c.start_time>@r2c_now THEN c.start_time END,c.start_time DESC,c.session_id;
  RETURN;
 END;
"""


def definition_hash(definition):
    normalized = re.sub(r'^\s*(?:CREATE|ALTER)(?=\s+PROCEDURE\b)', 'PROCEDURE_MARKER',
                        definition, count=1, flags=re.IGNORECASE)
    return sha256(' '.join(normalized.split()).encode()).hexdigest()


def target_definition(current, *, undo=False):
    if not current:
        raise ValueError('Thiếu thủ tục đọc lịch đã nghiệm thu.')
    current = current.replace('\r\n', '\n').strip()
    deployed = READ_SCOPE in current
    legacy = current.replace(READ_SCOPE, '', 1)
    if legacy.count(MARKER) != 1 or definition_hash(legacy) != ORIGINAL_HASH:
        raise ValueError('Định nghĩa lịch khác checkpoint. Cần đối chiếu trước khi cập nhật.')
    if deployed == (not undo):
        return None
    revised = legacy if undo else legacy.replace(MARKER, READ_SCOPE + MARKER, 1)
    return re.sub(r'^(?:CREATE|ALTER)(?=\s+PROCEDURE\b)', 'ALTER', revised, count=1, flags=re.IGNORECASE)


def deploy(cursor, *, undo=False):
    # Reject unsupported definitions before writing. ALTER preserves the existing EXECUTE grants.
    current = cursor.execute("""SELECT OBJECT_DEFINITION(OBJECT_ID(N'dbo.local03_schedule'))""").fetchval()
    sql = target_definition(current, undo=undo)
    if sql is None:
        return False
    cursor.execute(sql)
    observed = cursor.execute("""SELECT OBJECT_DEFINITION(OBJECT_ID(N'dbo.local03_schedule'))""").fetchval()
    if target_definition(observed, undo=undo) is not None:
        raise RuntimeError('Không xác minh được định nghĩa đọc lịch sau cập nhật.')
    return True
