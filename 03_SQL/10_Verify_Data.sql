-- Kiểm schema, đếm dữ liệu, 26 quy tắc chất lượng và DBCC.
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON;
SET NUMERIC_ROUNDABORT OFF;
IF DB_NAME() <> N'IronPulse_SubmissionQA' OR NOT EXISTS (
    SELECT 1 FROM sys.extended_properties WHERE class = 0
      AND name = N'IronPulseAcademicPackage' AND CONVERT(nvarchar(30), value) = N'1.0.1'
)
    THROW 53101, N'Chọn database học thuật IronPulse_SubmissionQA đã được tạo bởi bước 01.', 1;


IF (SELECT COUNT(*) FROM sys.tables WHERE is_ms_shipped=0) <> 18
 OR (SELECT COUNT(*) FROM sys.columns c JOIN sys.tables t ON c.object_id=t.object_id WHERE t.is_ms_shipped=0) <> 92
 OR (SELECT COUNT(*) FROM sys.key_constraints WHERE type='PK' AND is_ms_shipped=0) <> 18
 OR (SELECT COUNT(*) FROM sys.foreign_keys) <> 23
 OR (SELECT COUNT(*) FROM sys.sql_modules m JOIN sys.objects o ON m.object_id=o.object_id
     WHERE o.is_ms_shipped=0 AND o.schema_id=SCHEMA_ID(N'dbo')) <> 35
 OR EXISTS (SELECT 1 FROM sys.foreign_keys WHERE is_disabled=1 OR is_not_trusted=1)
 OR EXISTS (SELECT 1 FROM sys.check_constraints WHERE is_disabled=1 OR is_not_trusted=1)
 OR EXISTS (SELECT 1 FROM sys.triggers WHERE is_disabled=1 AND is_ms_shipped=0)
    THROW 53107, N'Schema, khóa, constraint, trigger hoặc module sai checkpoint.', 1;
DECLARE @Counts table (bang sysname, so_dong bigint);
INSERT @Counts
SELECT N'service_type', COUNT_BIG(*) FROM dbo.[service_type]
UNION ALL
SELECT N'room', COUNT_BIG(*) FROM dbo.[room]
UNION ALL
SELECT N'membership_plan', COUNT_BIG(*) FROM dbo.[membership_plan]
UNION ALL
SELECT N'plan_inclusion', COUNT_BIG(*) FROM dbo.[plan_inclusion]
UNION ALL
SELECT N'equipment', COUNT_BIG(*) FROM dbo.[equipment]
UNION ALL
SELECT N'person', COUNT_BIG(*) FROM dbo.[person]
UNION ALL
SELECT N'staff', COUNT_BIG(*) FROM dbo.[staff]
UNION ALL
SELECT N'trainer', COUNT_BIG(*) FROM dbo.[trainer]
UNION ALL
SELECT N'trainer_certification', COUNT_BIG(*) FROM dbo.[trainer_certification]
UNION ALL
SELECT N'member', COUNT_BIG(*) FROM dbo.[member]
UNION ALL
SELECT N'membership', COUNT_BIG(*) FROM dbo.[membership]
UNION ALL
SELECT N'payment', COUNT_BIG(*) FROM dbo.[payment]
UNION ALL
SELECT N'session', COUNT_BIG(*) FROM dbo.[session]
UNION ALL
SELECT N'pt_session', COUNT_BIG(*) FROM dbo.[pt_session]
UNION ALL
SELECT N'group_class_session', COUNT_BIG(*) FROM dbo.[group_class_session]
UNION ALL
SELECT N'booking', COUNT_BIG(*) FROM dbo.[booking]
UNION ALL
SELECT N'member_service_usage', COUNT_BIG(*) FROM dbo.[member_service_usage]
UNION ALL
SELECT N'equipment_maintenance_log', COUNT_BIG(*) FROM dbo.[equipment_maintenance_log];
SELECT bang, so_dong FROM @Counts ORDER BY bang;
SELECT SUM(so_dong) AS tong_so_dong FROM @Counts;
IF (SELECT SUM(so_dong) FROM @Counts) <= 10000 THROW 53108, N'Dataset phải vượt 10.000 dòng.', 1;
DECLARE @Reference datetime2(0) = (SELECT TRY_CONVERT(datetime2(0),value)
    FROM sys.extended_properties WHERE class=0 AND name=N'IronPulseSyntheticReference');
IF @Reference IS NULL THROW 53109, N'Thiếu mốc dữ liệu mẫu.', 1;
DECLARE @Checks table (kiem_tra sysname PRIMARY KEY, loi bigint NOT NULL);
INSERT @Checks EXEC sys.sp_executesql N'WITH charges AS (
    SELECT u.membership_id,u.service_type_id,u.used_at AS event_time,u.usage_id,1 AS amount
    FROM dbo.member_service_usage u
    UNION ALL
    SELECT u.membership_id,u.service_type_id,b.cancelled_at,u.usage_id,-1
    FROM dbo.member_service_usage u JOIN dbo.booking b ON b.booking_id=u.booking_id
    WHERE u.usage_status=''REFUNDED''
), running_quota AS (
    SELECT membership_id,service_type_id,
           SUM(amount) OVER(PARTITION BY membership_id,service_type_id
             ORDER BY event_time,amount DESC,usage_id ROWS UNBOUNDED PRECEDING) AS spent
    FROM charges
), visits AS (
    SELECT booking_id,session_id,booked_at AS event_time,1 AS spaces FROM dbo.booking
    UNION ALL SELECT booking_id,session_id,cancelled_at,-1 FROM dbo.booking WHERE cancelled_at IS NOT NULL
), running_capacity AS (
    SELECT session_id,SUM(spaces) OVER(PARTITION BY session_id
       ORDER BY event_time,spaces DESC,booking_id ROWS UNBOUNDED PRECEDING) AS occupied
    FROM visits
)
SELECT ''missing_or_wrong_pt_usage'' AS check_name, COUNT_BIG(*) AS failures
FROM dbo.pt_session p JOIN dbo.[session] s ON s.session_id=p.session_id
OUTER APPLY (SELECT COUNT_BIG(*) AS used FROM dbo.member_service_usage u
    JOIN dbo.membership m ON m.membership_id=u.membership_id
    WHERE u.session_id=p.session_id AND m.person_id=p.person_id AND u.service_type_id=3
      AND u.usage_status=''USED'' AND u.booking_id IS NULL AND u.used_at=s.created_at) q
WHERE s.session_type<>''PERSONAL'' OR q.used<>1
UNION ALL SELECT ''wrong_booking_or_refund'',COUNT_BIG(*)
FROM dbo.booking b JOIN dbo.[session] s ON s.session_id=b.session_id
JOIN dbo.group_class_session g ON g.session_id=b.session_id
LEFT JOIN dbo.member_service_usage u ON u.booking_id=b.booking_id
LEFT JOIN dbo.membership m ON m.membership_id=u.membership_id
WHERE u.usage_id IS NULL OR u.session_id<>b.session_id OR m.person_id<>b.person_id
   OR u.used_at<>b.booked_at OR b.booked_at<s.created_at OR b.booked_at>=s.start_time
   OR b.booked_at>@Reference OR b.cancelled_at>=s.start_time OR b.cancelled_at>@Reference
   OR u.service_type_id<>dbo.demo_class_service(g.category)
   OR u.usage_status<>CASE WHEN b.cancelled_at<=DATEADD(hour,-5,s.start_time) THEN ''REFUNDED'' ELSE ''USED'' END
UNION ALL SELECT ''orphan_or_out_of_term_service'',COUNT_BIG(*)
FROM dbo.member_service_usage u
JOIN dbo.membership m ON m.membership_id=u.membership_id
LEFT JOIN dbo.[session] s ON s.session_id=u.session_id
LEFT JOIN dbo.payment p ON p.membership_id=m.membership_id
LEFT JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=u.service_type_id
WHERE i.plan_id IS NULL OR m.start_date IS NULL OR m.end_date IS NULL OR p.payment_id IS NULL
   OR u.used_at<p.payment_time OR u.used_at>@Reference
   OR CONVERT(date,u.used_at) NOT BETWEEN m.start_date AND m.end_date
   OR (u.session_id IS NULL AND (u.service_type_id<>1 OR u.usage_status<>''USED'' OR u.booking_id IS NOT NULL))
   OR (s.session_type=''GROUP'' AND u.booking_id IS NULL)
   OR (s.session_type=''PERSONAL'' AND (u.service_type_id<>3 OR u.booking_id IS NOT NULL OR u.usage_status<>''USED''
       OR NOT EXISTS (SELECT 1 FROM dbo.pt_session p WHERE p.session_id=s.session_id AND p.person_id=m.person_id)))
   OR u.used_at>=s.start_time OR CONVERT(date,s.end_time)>m.end_date
UNION ALL SELECT ''event_quota'',COUNT_BIG(*)
FROM running_quota q JOIN dbo.membership m ON m.membership_id=q.membership_id
JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=q.service_type_id
WHERE q.spent<0 OR (i.quota_per_cycle<>-1 AND q.spent>i.quota_per_cycle)
UNION ALL SELECT ''event_capacity'',COUNT_BIG(*)
FROM running_capacity r JOIN dbo.group_class_session g ON g.session_id=r.session_id
WHERE r.occupied<0 OR r.occupied>g.max_capacity
UNION ALL SELECT ''unknown_quota'',COUNT_BIG(*)
FROM dbo.membership m JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id
WHERE m.start_date IS NOT NULL AND i.service_type_id<>1
  AND dbo.demo_unreconciled_quota(m.membership_id,i.service_type_id)=1
UNION ALL SELECT ''payment_snapshot_or_dates'',COUNT_BIG(*)
FROM dbo.membership m JOIN dbo.member a ON m.person_id=a.person_id JOIN dbo.membership_plan l ON l.plan_id=m.plan_id
LEFT JOIN dbo.payment p ON p.membership_id=m.membership_id
LEFT JOIN dbo.staff s ON s.person_id=p.recorded_by
WHERE m.created_at>@Reference OR CONVERT(date,m.created_at)<a.join_date
   OR (m.status=''PENDING_PAYMENT'' AND (p.payment_id IS NOT NULL OR m.total_price IS NOT NULL))
   OR (m.status<>''PENDING_PAYMENT'' AND (p.payment_id IS NULL OR m.total_price IS NULL OR p.amount<>m.total_price
        OR m.total_price<>l.base_price OR s.person_id IS NULL OR s.employment_status<>''ACTIVE''
        OR s.hire_date>CONVERT(date,p.payment_time) OR p.payment_time<m.created_at OR p.payment_time>@Reference))
   OR (m.status IN (''ACTIVE'',''EXPIRED'') AND (m.start_date IS NULL OR m.end_date<>DATEADD(month,l.duration_months,m.start_date)
        OR CONVERT(date,p.payment_time)>m.start_date OR m.start_date>CONVERT(date,@Reference)))
   OR (m.status IN (''PENDING_PAYMENT'',''PENDING_ACTIVATION'') AND (m.start_date IS NOT NULL OR m.end_date IS NOT NULL))
   OR (m.status=''ACTIVE'' AND m.end_date<CONVERT(date,@Reference))
   OR (m.status=''EXPIRED'' AND m.end_date>=CONVERT(date,@Reference))
UNION ALL SELECT ''overlapping_memberships'',COUNT_BIG(*)
FROM dbo.membership a JOIN dbo.membership b ON a.person_id=b.person_id
  AND a.membership_id<b.membership_id AND a.start_date<=b.end_date AND b.start_date<=a.end_date
UNION ALL SELECT ''session_missing_subtype_or_certification'',COUNT_BIG(*)
FROM dbo.[session] s JOIN dbo.trainer t ON t.person_id=s.trainer_id JOIN dbo.room r ON r.room_id=s.room_id
LEFT JOIN dbo.pt_session p ON p.session_id=s.session_id LEFT JOIN dbo.group_class_session g ON g.session_id=s.session_id
LEFT JOIN dbo.trainer_certification c ON c.person_id=t.person_id AND c.certification=CASE g.category
    WHEN N''YOGA'' THEN N''Yoga Alliance'' WHEN N''CYCLING'' THEN N''Đạp xe trong nhà''
    WHEN N''ZUMBA'' THEN N''Hướng dẫn Zumba'' WHEN N''BOXING'' THEN N''Boxing Fitness'' ELSE N''Huấn luyện nhóm cơ bản'' END
WHERE s.created_at>s.start_time OR s.created_at>@Reference OR CONVERT(date,s.created_at)<t.hire_date
    OR r.status<>''AVAILABLE'' OR t.employment_status<>''ACTIVE''
    OR (s.session_type=''GROUP'' AND (g.session_id IS NULL OR p.session_id IS NOT NULL OR c.person_id IS NULL))
    OR (s.session_type=''PERSONAL'' AND (p.session_id IS NULL OR g.session_id IS NOT NULL))
UNION ALL SELECT ''maintenance_history_dates'',COUNT_BIG(*)
FROM dbo.equipment_maintenance_log a
WHERE a.start_date>CONVERT(date,@Reference) OR a.end_date>CONVERT(date,@Reference)
   OR EXISTS (SELECT 1 FROM dbo.equipment_maintenance_log b WHERE b.equipment_id=a.equipment_id
        AND b.maintenance_id>a.maintenance_id
        AND a.start_date<=COALESCE(b.end_date,''9999-12-31'')
        AND b.start_date<=COALESCE(a.end_date,''9999-12-31''));
', N'@Reference datetime2(0)', @Reference;
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''unmasked_people'', COUNT(*) FROM person WHERE email NOT LIKE ''%@example.invalid''
        OR phone NOT LIKE ''00041%'' OR ssn NOT LIKE ''00041%'' OR address<>N''Khu dân cư mô phỏng''
        OR (password_hash<>''!disabled-local05d'' AND password_hash NOT LIKE ''$argon2id$%'')';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''unmasked_member'', COUNT(*) FROM member WHERE emergency_contact_phone NOT LIKE ''00042%'' OR health_notes IS NOT NULL';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''invalid_role_count'', COUNT(*) FROM person p WHERE
        (SELECT COUNT(*) FROM member WHERE person_id=p.person_id)+
        (SELECT COUNT(*) FROM staff WHERE person_id=p.person_id)+
        (SELECT COUNT(*) FROM trainer WHERE person_id=p.person_id)<>1';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''technical_names'', COUNT(*) FROM (
          SELECT full_name AS label FROM person UNION ALL SELECT plan_name FROM membership_plan
          UNION ALL SELECT room_name FROM room UNION ALL SELECT equipment_name FROM equipment
          UNION ALL SELECT class_name FROM group_class_session
        ) n WHERE UPPER(label) LIKE ''% QA %'' OR UPPER(label) LIKE ''%TEST%'' OR UPPER(label) LIKE ''%FIXTURE%''
         OR CHARINDEX(NCHAR(65533),label COLLATE Latin1_General_100_BIN2)>0
         OR DATALENGTH(label)<>DATALENGTH(TRIM(label))';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''unrecognized_category'', COUNT(*) FROM group_class_session
          WHERE dbo.demo_class_service(category) IS NULL';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''invalid_used_scope'', COUNT(*) FROM member_service_usage u
         JOIN membership m ON m.membership_id=u.membership_id LEFT JOIN [session] s ON s.session_id=u.session_id
         LEFT JOIN group_class_session g ON g.session_id=u.session_id
         LEFT JOIN plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=u.service_type_id
         WHERE i.plan_id IS NULL OR CONVERT(date,COALESCE(s.start_time,u.used_at))<m.start_date
         OR CONVERT(date,COALESCE(s.end_time,u.used_at))>m.end_date
         OR (s.session_type=''GROUP'' AND u.service_type_id<>dbo.demo_class_service(g.category))
         OR (s.session_type=''PERSONAL'' AND u.service_type_id<>3)';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''recorded_over_quota'', COUNT(*) FROM (SELECT u.membership_id,u.service_type_id
        FROM member_service_usage u JOIN membership m ON m.membership_id=u.membership_id
        JOIN plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=u.service_type_id
        WHERE u.usage_status=''USED'' AND i.quota_per_cycle>=0
        GROUP BY u.membership_id,u.service_type_id,i.quota_per_cycle HAVING COUNT(*)>i.quota_per_cycle) q';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''bad_rooms'', COUNT(*) FROM [session] s JOIN room r ON r.room_id=s.room_id
         WHERE (s.session_type=''PERSONAL'' AND r.room_type<>''PT'')
         OR (s.session_type=''GROUP'' AND r.room_type<>''STUDIO'')';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''future_staff_or_room_unavailable'', COUNT(*) FROM [session] s JOIN room r ON r.room_id=s.room_id
         JOIN trainer t ON t.person_id=s.trainer_id
         WHERE s.start_time>SYSDATETIME() AND (t.employment_status<>''ACTIVE'' OR r.status<>''AVAILABLE'')';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''overlap_trainer_or_room'', COUNT(*) FROM [session] a JOIN [session] b ON a.session_id<b.session_id
          AND a.start_time<b.end_time AND b.start_time<a.end_time AND (a.trainer_id=b.trainer_id OR a.room_id=b.room_id)';
INSERT @Checks EXEC sys.sp_executesql N'WITH history AS (SELECT person_id,session_id FROM pt_session
         UNION ALL SELECT person_id,session_id FROM booking WHERE booking_status=''SUCCESS'')
         SELECT ''overlap_member'', COUNT(*) FROM history x JOIN history y ON y.person_id=x.person_id AND y.session_id>x.session_id
         JOIN [session] a ON a.session_id=x.session_id JOIN [session] b ON b.session_id=y.session_id
         WHERE a.start_time<b.end_time AND b.start_time<a.end_time';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''over_capacity'', COUNT(*) FROM vw_group_class_enrollment WHERE available_slots<0';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''pending_or_expired_finance'', COUNT(*) FROM membership m LEFT JOIN payment p ON p.membership_id=m.membership_id
         WHERE (m.status=''PENDING_PAYMENT'' AND p.payment_id IS NOT NULL)
         OR (m.status<>''PENDING_PAYMENT'' AND (p.payment_id IS NULL OR m.total_price IS NULL OR m.total_price<>p.amount))';
INSERT @Checks EXEC sys.sp_executesql N'SELECT ''maintenance_mismatch'', COUNT(*) FROM equipment e OUTER APPLY(
         SELECT COUNT(*) AS opened FROM equipment_maintenance_log l WHERE l.equipment_id=e.equipment_id AND l.end_date IS NULL
         ) n WHERE (e.status=''MAINTENANCE'' AND n.opened<>1) OR (e.status<>''MAINTENANCE'' AND n.opened<>0)';
INSERT @Checks SELECT N'credentials', ABS(COUNT_BIG(*) - 8)
FROM dbo.person WHERE password_hash LIKE '$argon2id$%';
INSERT @Checks SELECT N'equipment_room', SUM(so_loi) FROM (
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Máy chạy bộ số %' AND room_id NOT IN (1,2)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Xe đạp tập số %' AND room_id NOT IN (1,2)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Máy elliptical số %' AND room_id NOT IN (1,2)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Máy kéo cáp số %' AND room_id NOT IN (3,5)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Máy đạp chân số %' AND room_id NOT IN (3,5,7)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Ghế đẩy ngực số %' AND room_id NOT IN (4,5)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Giàn squat số %' AND room_id NOT IN (4,7)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Bộ kettlebell số %' AND room_id NOT IN (6,8,9,10,11,12)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Bộ tạ tay số %' AND room_id NOT IN (4,8,9,10,11,12)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Bộ thảm tập số %' AND room_id NOT IN (13,14,15,19,20)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Bục aerobic số %' AND room_id NOT IN (13,14,17,20)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Xe đạp lớp nhóm số %' AND room_id NOT IN (16)
UNION ALL
SELECT COUNT_BIG(*) AS so_loi FROM dbo.equipment WHERE equipment_name LIKE N'Bao đấm số %' AND room_id NOT IN (18)
) AS loi;
SELECT kiem_tra, loi FROM @Checks ORDER BY kiem_tra;
IF (SELECT COUNT(*) FROM @Checks) <> 26 OR EXISTS (SELECT 1 FROM @Checks WHERE loi<>0)
    THROW 53110, N'Không đạt các phép kiểm chất lượng.', 1;
CREATE TABLE #ConstraintErrors ([Table] nvarchar(776), [Constraint] nvarchar(776), [Where] nvarchar(max));
INSERT #ConstraintErrors EXEC(N'DBCC CHECKCONSTRAINTS WITH ALL_CONSTRAINTS, ALL_ERRORMSGS;');
IF EXISTS (SELECT 1 FROM #ConstraintErrors) THROW 53111, N'DBCC CHECKCONSTRAINTS phát hiện lỗi.', 1;
DROP TABLE #ConstraintErrors;
DBCC CHECKDB WITH NO_INFOMSGS, ALL_ERRORMSGS, MAXDOP = 1;
