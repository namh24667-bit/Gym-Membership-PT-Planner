-- Năm chỉ mục nghiệp vụ. PK và UNIQUE sinh chỉ mục ở bước 02.
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

CREATE UNIQUE INDEX ux_membership_one_active
ON membership(person_id)
WHERE status = 'ACTIVE';

CREATE UNIQUE INDEX ux_booking_active_member_session
ON booking(person_id, session_id)
WHERE booking_status = 'SUCCESS';

CREATE INDEX ix_booking_session_status
ON booking(session_id, booking_status);

CREATE UNIQUE INDEX ux_membership_local02_request ON dbo.membership(local02_request_id)
 WHERE local02_request_id IS NOT NULL;

CREATE UNIQUE INDEX ux_usage_one_per_booking ON dbo.member_service_usage(booking_id)
 WHERE booking_id IS NOT NULL;
COMMIT TRANSACTION;
