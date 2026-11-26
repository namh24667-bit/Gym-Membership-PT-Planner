-- Hai view sĩ số lớp và doanh thu tháng.
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
EXEC sys.sp_executesql N'CREATE VIEW vw_group_class_enrollment AS
SELECT g.session_id, g.class_name, g.category, s.start_time, g.max_capacity,
       COUNT(b.booking_id) AS current_enrollment,
       g.max_capacity - COUNT(b.booking_id) AS available_slots
FROM group_class_session g
JOIN [session] s ON g.session_id = s.session_id
LEFT JOIN booking b ON g.session_id = b.session_id
                   AND b.booking_status = ''SUCCESS''
GROUP BY g.session_id, g.class_name, g.category, s.start_time, g.max_capacity;';

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
EXEC sys.sp_executesql N'CREATE VIEW vw_monthly_revenue AS
SELECT YEAR(payment_time) AS nam, MONTH(payment_time) AS thang,
       COUNT(*) AS so_giao_dich, SUM(amount) AS tong_doanh_thu
FROM payment
GROUP BY YEAR(payment_time), MONTH(payment_time);';
COMMIT TRANSACTION;
