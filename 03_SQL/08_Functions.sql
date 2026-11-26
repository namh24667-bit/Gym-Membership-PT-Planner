-- Hai hàm ánh xạ bộ môn và đối soát quota.
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
BEGIN TRANSACTION;

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
EXEC sys.sp_executesql N'CREATE FUNCTION dbo.demo_class_service(@category nvarchar(50))
RETURNS int WITH SCHEMABINDING
AS
BEGIN
    RETURN CASE UPPER(TRIM(@category))
        WHEN N''CARDIO'' THEN 2 WHEN N''RECOVERY'' THEN 2 WHEN N''STRENGTH'' THEN 2
        WHEN N''YOGA'' THEN 4 WHEN N''CYCLING'' THEN 5 WHEN N''ZUMBA'' THEN 6 WHEN N''BOXING'' THEN 7 END;
END;';

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
EXEC sys.sp_executesql N'CREATE FUNCTION dbo.demo_unreconciled_quota(@membership int,@service int)
RETURNS bit
AS
BEGIN
    IF @service=3 AND EXISTS (
        SELECT 1 FROM dbo.membership m
        JOIN dbo.pt_session p ON p.person_id=m.person_id
        JOIN dbo.[session] s ON s.session_id=p.session_id
        WHERE m.membership_id=@membership AND CONVERT(date,s.start_time)>=m.start_date
          AND CONVERT(date,s.end_time)<=m.end_date
          AND NOT EXISTS(SELECT 1 FROM dbo.member_service_usage u
              WHERE u.session_id=p.session_id AND u.membership_id=m.membership_id
                AND u.service_type_id=@service AND u.usage_status=''USED'')
    ) RETURN 1;
    IF @service<>3 AND EXISTS (
        SELECT 1 FROM dbo.membership m
        JOIN dbo.booking b ON b.person_id=m.person_id
        JOIN dbo.group_class_session g ON g.session_id=b.session_id
        JOIN dbo.[session] s ON s.session_id=g.session_id
        WHERE m.membership_id=@membership AND dbo.demo_class_service(g.category)=@service
          AND CONVERT(date,s.start_time)>=m.start_date AND CONVERT(date,s.end_time)<=m.end_date
          AND (b.booking_status=''SUCCESS'' OR b.cancelled_at>DATEADD(hour,-5,s.start_time))
          AND NOT EXISTS(SELECT 1 FROM dbo.member_service_usage u
              WHERE u.booking_id=b.booking_id AND u.membership_id=m.membership_id
                AND u.service_type_id=@service AND u.usage_status=''USED'')
    ) RETURN 1;
    RETURN 0;
END;';
COMMIT TRANSACTION;
