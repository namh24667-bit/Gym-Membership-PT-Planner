-- Ba trigger kiểm lịch, đặt lớp và buổi PT.
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
EXEC sys.sp_executesql N'CREATE TRIGGER trg_booking_check
ON booking
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN group_class_session g ON i.session_id = g.session_id
        WHERE i.booking_status = ''SUCCESS''
          AND (
              SELECT COUNT(*)
              FROM booking b
              WHERE b.session_id = i.session_id
                AND b.booking_status = ''SUCCESS''
          ) > g.max_capacity
    )
        THROW 51005, N''Lop hoc da du so luong nguoi tham gia.'', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s1 ON i.session_id = s1.session_id
        JOIN booking b ON i.person_id = b.person_id
                      AND i.booking_id <> b.booking_id
                      AND b.booking_status = ''SUCCESS''
        JOIN [session] s2 ON b.session_id = s2.session_id
        WHERE i.booking_status = ''SUCCESS''
          AND s1.start_time < s2.end_time
          AND s2.start_time < s1.end_time
    )
        THROW 51006, N''Hoi vien da dat lop khac trung gio.'', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s1 ON i.session_id = s1.session_id
        JOIN pt_session p ON i.person_id = p.person_id
        JOIN [session] s2 ON p.session_id = s2.session_id
        WHERE i.booking_status = ''SUCCESS''
          AND s1.start_time < s2.end_time
          AND s2.start_time < s1.end_time
    )
        THROW 51007, N''Hoi vien co buoi PT trung gio.'', 1;
END;';

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
EXEC sys.sp_executesql N'CREATE TRIGGER trg_pt_session_check
ON pt_session
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s1 ON i.session_id = s1.session_id
        JOIN pt_session p ON i.person_id = p.person_id
                         AND i.session_id <> p.session_id
        JOIN [session] s2 ON p.session_id = s2.session_id
        WHERE s1.start_time < s2.end_time
          AND s2.start_time < s1.end_time
    )
        THROW 51008, N''Hoi vien bi trung lich PT.'', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s1 ON i.session_id = s1.session_id
        JOIN booking b ON i.person_id = b.person_id
                      AND b.booking_status = ''SUCCESS''
        JOIN [session] s2 ON b.session_id = s2.session_id
        WHERE s1.start_time < s2.end_time
          AND s2.start_time < s1.end_time
    )
        THROW 51009, N''Hoi vien co lop nhom trung gio PT.'', 1;
END;';

SET ANSI_NULLS ON;
SET QUOTED_IDENTIFIER ON;
EXEC sys.sp_executesql N'CREATE TRIGGER trg_session_check
ON [session]
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN trainer t ON i.trainer_id = t.person_id
        WHERE t.employment_status <> ''ACTIVE''
    )
        THROW 51001, N''Huan luyen vien khong o trang thai ACTIVE.'', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN room r ON i.room_id = r.room_id
        WHERE r.status = ''MAINTENANCE''
    )
        THROW 51002, N''Phong dang bao tri, khong the tao lich.'', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s ON i.trainer_id = s.trainer_id
        WHERE i.session_id <> s.session_id
          AND i.start_time < s.end_time
          AND s.start_time < i.end_time
    )
        THROW 51003, N''Huan luyen vien bi trung lich.'', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s ON i.room_id = s.room_id
        WHERE i.session_id <> s.session_id
          AND i.start_time < s.end_time
          AND s.start_time < i.end_time
    )
        THROW 51004, N''Phong tap bi trung lich.'', 1;
END;';
COMMIT TRANSACTION;
