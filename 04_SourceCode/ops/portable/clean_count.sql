-- Chon database CleanDemo cua ban cai trong SSMS truoc khi chay.
SET NOCOUNT ON;
IF DB_NAME() NOT LIKE N'IronPulse[_]Clean%QA'
    THROW 52840, N'Chon database CleanDemo cua ban cai truoc khi kiem dem.', 1;
IF NOT EXISTS (SELECT 1 FROM sys.extended_properties WHERE class=0
    AND name=N'IronPulseSyntheticDataset' AND CONVERT(nvarchar(100),value)=N'local05d-c.synthetic.v1')
    THROW 52841, N'Database chưa có định danh dữ liệu tổng hợp LOCAL-05D-C.', 1;

WITH counts AS (
    SELECT N'person' AS bang, N'Hồ sơ cá nhân' AS nghia, COUNT_BIG(*) AS so_dong FROM dbo.person
    UNION ALL SELECT N'member', N'Hồ sơ hội viên', COUNT_BIG(*) FROM dbo.member
    UNION ALL SELECT N'staff', N'Nhân sự và quản lý', COUNT_BIG(*) FROM dbo.staff
    UNION ALL SELECT N'trainer', N'Huấn luyện viên', COUNT_BIG(*) FROM dbo.trainer
    UNION ALL SELECT N'trainer_certification', N'Chứng chỉ HLV tổng hợp', COUNT_BIG(*) FROM dbo.trainer_certification
    UNION ALL SELECT N'room', N'Phòng và khu tập', COUNT_BIG(*) FROM dbo.room
    UNION ALL SELECT N'equipment', N'Thiết bị phòng tập', COUNT_BIG(*) FROM dbo.equipment
    UNION ALL SELECT N'equipment_maintenance_log', N'Phiếu bảo trì thiết bị', COUNT_BIG(*) FROM dbo.equipment_maintenance_log
    UNION ALL SELECT N'membership_plan', N'Danh mục mẫu gói', COUNT_BIG(*) FROM dbo.membership_plan
    UNION ALL SELECT N'service_type', N'Loại dịch vụ', COUNT_BIG(*) FROM dbo.service_type
    UNION ALL SELECT N'plan_inclusion', N'Quyền lợi theo gói và bộ môn', COUNT_BIG(*) FROM dbo.plan_inclusion
    UNION ALL SELECT N'membership', N'Hợp đồng và chu kỳ tập', COUNT_BIG(*) FROM dbo.membership
    UNION ALL SELECT N'payment', N'Giao dịch thanh toán tổng hợp', COUNT_BIG(*) FROM dbo.payment
    UNION ALL SELECT N'session', N'Khung giờ và phân công', COUNT_BIG(*) FROM dbo.[session]
    UNION ALL SELECT N'pt_session', N'Chi tiết buổi PT', COUNT_BIG(*) FROM dbo.pt_session
    UNION ALL SELECT N'group_class_session', N'Chi tiết lớp nhóm', COUNT_BIG(*) FROM dbo.group_class_session
    UNION ALL SELECT N'booking', N'Lượt đặt và hủy lớp', COUNT_BIG(*) FROM dbo.booking
    UNION ALL SELECT N'member_service_usage', N'Sổ trừ và hoàn quyền lợi', COUNT_BIG(*) FROM dbo.member_service_usage
)
SELECT COALESCE(bang,N'TỔNG') AS bang_nghiep_vu,
       COALESCE(nghia,N'Dữ liệu tổng hợp, giới hạn đúng 18 bảng') AS y_nghia, SUM(so_dong) AS so_dong,
       CASE WHEN GROUPING(bang)=1 THEN COUNT(*) END AS so_bang_duoc_tinh,
       CASE WHEN GROUPING(bang)=1 THEN CASE WHEN SUM(so_dong)>10000 THEN N'ĐẠT' ELSE N'CHƯA ĐẠT' END END AS moc_hon_10000
FROM counts
GROUP BY GROUPING SETS ((bang,nghia), ())
ORDER BY GROUPING(bang),bang;
