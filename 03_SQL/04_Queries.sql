-- 16 truy vấn đọc dữ liệu cho phần bảo vệ đồ án.
SET NOCOUNT ON;
IF DB_NAME() <> N'IronPulse_SubmissionQA' OR NOT EXISTS (
    SELECT 1 FROM sys.extended_properties WHERE class=0 AND name=N'IronPulseAcademicPackage'
      AND CONVERT(nvarchar(30),value)=N'1.0.1'
)
    THROW 53101, N'Chọn database học thuật IronPulse_SubmissionQA.', 1;

DECLARE @NgayDuLieu date = (
    SELECT CONVERT(date, CONVERT(nvarchar(30), value))
    FROM sys.extended_properties WHERE class=0 AND name=N'IronPulseSyntheticReference'
);

-- Q01. person: 20 hồ sơ đầu theo tên với ID làm cột phá hòa.
SELECT TOP (20) person_id, full_name FROM dbo.person ORDER BY full_name, person_id;
-- Q02. person + member: tên và ngày tham gia của hội viên.
SELECT TOP (20) p.person_id, p.full_name, m.join_date FROM dbo.person p
JOIN dbo.member m ON m.person_id=p.person_id ORDER BY m.join_date DESC, p.person_id;
-- Q03. member + person + membership: số hợp đồng, kể cả hội viên chưa có hợp đồng.
SELECT TOP (20) m.person_id, p.full_name, COUNT(h.membership_id) AS so_hop_dong
FROM dbo.member m JOIN dbo.person p ON p.person_id=m.person_id
LEFT JOIN dbo.membership h ON h.person_id=m.person_id
GROUP BY m.person_id,p.full_name ORDER BY so_hop_dong DESC, m.person_id;
-- Q04. membership + membership_plan + person: hợp đồng ACTIVE còn hạn tại mốc dữ liệu.
SELECT TOP (20) p.full_name, g.plan_name, h.start_date,h.end_date
FROM dbo.membership h JOIN dbo.person p ON p.person_id=h.person_id
JOIN dbo.membership_plan g ON g.plan_id=h.plan_id
WHERE h.status='ACTIVE' AND @NgayDuLieu BETWEEN h.start_date AND h.end_date
ORDER BY h.end_date,h.membership_id;
-- Q05. membership_plan: danh mục gói đang bán.
SELECT plan_id,plan_name,duration_months,base_price FROM dbo.membership_plan
WHERE is_for_sale=1 ORDER BY base_price,plan_id;
-- Q06. plan_inclusion + membership_plan + service_type: quota từng quyền lợi, -1 là không giới hạn.
SELECT p.plan_name,s.service_name,i.quota_per_cycle FROM dbo.plan_inclusion i
JOIN dbo.membership_plan p ON p.plan_id=i.plan_id JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
ORDER BY p.plan_id,s.service_type_id;
-- Q07. membership + payment: hợp đồng chờ thu tiền và chưa có biên lai.
SELECT TOP (20) m.membership_id,m.person_id,m.created_at FROM dbo.membership m
WHERE m.status='PENDING_PAYMENT' AND NOT EXISTS (
    SELECT 1 FROM dbo.payment p WHERE p.membership_id=m.membership_id
) ORDER BY m.created_at,m.membership_id;
-- Q08. payment qua view: doanh thu và số khoản thu theo tháng ghi nhận thanh toán.
SELECT nam,thang,so_giao_dich,tong_doanh_thu FROM dbo.vw_monthly_revenue ORDER BY nam,thang;
-- Q09. payment: tổng, trung bình và số khoản thu theo hình thức thanh toán.
SELECT payment_method,COUNT_BIG(*) AS so_luot,SUM(amount) AS tong_thu,AVG(amount) AS muc_thu_trung_binh
FROM dbo.payment GROUP BY payment_method ORDER BY tong_thu DESC,payment_method;
-- Q10. session + pt_session + person: chỉ các HLV có ít nhất năm buổi PT ghi nhận.
SELECT s.trainer_id,p.full_name,COUNT(*) AS so_buoi_pt FROM dbo.session s
JOIN dbo.pt_session pt ON pt.session_id=s.session_id JOIN dbo.person p ON p.person_id=s.trainer_id
GROUP BY s.trainer_id,p.full_name HAVING COUNT(*)>=5 ORDER BY so_buoi_pt DESC,s.trainer_id;
-- Q11. group_class_session + session + booking qua view: sĩ số SUCCESS và số chỗ trống.
SELECT TOP (20) session_id,class_name,start_time,max_capacity,current_enrollment,available_slots
FROM dbo.vw_group_class_enrollment ORDER BY start_time DESC,session_id;
-- Q12. membership + plan_inclusion + service_type + member_service_usage: quota theo bộ môn.
-- NULL ở so_luot_con biểu thị quyền tập không giới hạn (quota = -1).
SELECT TOP (30) m.membership_id,s.service_name,i.quota_per_cycle,u.so_luot_da_dung,
       CASE WHEN i.quota_per_cycle>=0 THEN i.quota_per_cycle-u.so_luot_da_dung END AS so_luot_con
FROM dbo.membership m JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id
JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
CROSS APPLY (SELECT COUNT_BIG(*) AS so_luot_da_dung FROM dbo.member_service_usage u
             WHERE u.membership_id=m.membership_id AND u.service_type_id=i.service_type_id
               AND u.usage_status='USED') u
WHERE m.status='ACTIVE' AND @NgayDuLieu BETWEEN m.start_date AND m.end_date
ORDER BY m.membership_id,s.service_type_id;
-- Q13. equipment + equipment_maintenance_log: phiếu đang mở của thiết bị bảo trì.
SELECT e.equipment_id,e.equipment_name,l.start_date FROM dbo.equipment e
JOIN dbo.equipment_maintenance_log l ON l.equipment_id=e.equipment_id AND l.end_date IS NULL
WHERE e.status='MAINTENANCE' ORDER BY l.start_date,e.equipment_id;
-- Q14. booking + session: doanh số chỗ đã đặt hoặc hủy theo trạng thái.
SELECT b.booking_status,COUNT_BIG(*) AS so_luot FROM dbo.booking b
JOIN dbo.session s ON s.session_id=b.session_id WHERE s.session_type='GROUP'
GROUP BY b.booking_status ORDER BY b.booking_status;
-- Q15. membership + membership_plan: gói ngừng bán có hợp đồng tham chiếu.
SELECT p.plan_id,p.plan_name,COUNT_BIG(*) AS so_hop_dong FROM dbo.membership_plan p
JOIN dbo.membership m ON m.plan_id=p.plan_id WHERE p.is_for_sale=0
GROUP BY p.plan_id,p.plan_name ORDER BY p.plan_id;
-- Q16. 18 bảng nghiệp vụ: tổng dòng thực tế, gồm cả bảng liên kết.
SELECT SUM(n) AS tong_so_dong FROM (
    SELECT COUNT_BIG(*) n FROM dbo.person
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.member
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.staff
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.trainer
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.trainer_certification
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.room
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.equipment
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.equipment_maintenance_log
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.membership_plan
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.service_type
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.plan_inclusion
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.membership
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.payment
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.session
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.pt_session
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.group_class_session
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.booking
    UNION ALL SELECT COUNT_BIG(*) FROM dbo.member_service_usage
) AS counts;
