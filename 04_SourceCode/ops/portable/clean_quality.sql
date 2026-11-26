-- Called inside the validated CleanDemo target. @Reference is the seed's local SQL timestamp.
DECLARE @Reference datetime2(0)=?;
WITH charges AS (
    SELECT u.membership_id,u.service_type_id,u.used_at AS event_time,u.usage_id,1 AS amount
    FROM dbo.member_service_usage u
    UNION ALL
    SELECT u.membership_id,u.service_type_id,b.cancelled_at,u.usage_id,-1
    FROM dbo.member_service_usage u JOIN dbo.booking b ON b.booking_id=u.booking_id
    WHERE u.usage_status='REFUNDED'
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
SELECT 'missing_or_wrong_pt_usage' AS check_name, COUNT_BIG(*) AS failures
FROM dbo.pt_session p JOIN dbo.[session] s ON s.session_id=p.session_id
OUTER APPLY (SELECT COUNT_BIG(*) AS used FROM dbo.member_service_usage u
    JOIN dbo.membership m ON m.membership_id=u.membership_id
    WHERE u.session_id=p.session_id AND m.person_id=p.person_id AND u.service_type_id=3
      AND u.usage_status='USED' AND u.booking_id IS NULL AND u.used_at=s.created_at) q
WHERE s.session_type<>'PERSONAL' OR q.used<>1
UNION ALL SELECT 'wrong_booking_or_refund',COUNT_BIG(*)
FROM dbo.booking b JOIN dbo.[session] s ON s.session_id=b.session_id
JOIN dbo.group_class_session g ON g.session_id=b.session_id
LEFT JOIN dbo.member_service_usage u ON u.booking_id=b.booking_id
LEFT JOIN dbo.membership m ON m.membership_id=u.membership_id
WHERE u.usage_id IS NULL OR u.session_id<>b.session_id OR m.person_id<>b.person_id
   OR u.used_at<>b.booked_at OR b.booked_at<s.created_at OR b.booked_at>=s.start_time
   OR b.booked_at>@Reference OR b.cancelled_at>=s.start_time OR b.cancelled_at>@Reference
   OR u.service_type_id<>dbo.demo_class_service(g.category)
   OR u.usage_status<>CASE WHEN b.cancelled_at<=DATEADD(hour,-5,s.start_time) THEN 'REFUNDED' ELSE 'USED' END
UNION ALL SELECT 'orphan_or_out_of_term_service',COUNT_BIG(*)
FROM dbo.member_service_usage u
JOIN dbo.membership m ON m.membership_id=u.membership_id
LEFT JOIN dbo.[session] s ON s.session_id=u.session_id
LEFT JOIN dbo.payment p ON p.membership_id=m.membership_id
LEFT JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=u.service_type_id
WHERE i.plan_id IS NULL OR m.start_date IS NULL OR m.end_date IS NULL OR p.payment_id IS NULL
   OR u.used_at<p.payment_time OR u.used_at>@Reference
   OR CONVERT(date,u.used_at) NOT BETWEEN m.start_date AND m.end_date
   OR (u.session_id IS NULL AND (u.service_type_id<>1 OR u.usage_status<>'USED' OR u.booking_id IS NOT NULL))
   OR (s.session_type='GROUP' AND u.booking_id IS NULL)
   OR (s.session_type='PERSONAL' AND (u.service_type_id<>3 OR u.booking_id IS NOT NULL OR u.usage_status<>'USED'
       OR NOT EXISTS (SELECT 1 FROM dbo.pt_session p WHERE p.session_id=s.session_id AND p.person_id=m.person_id)))
   OR u.used_at>=s.start_time OR CONVERT(date,s.end_time)>m.end_date
UNION ALL SELECT 'event_quota',COUNT_BIG(*)
FROM running_quota q JOIN dbo.membership m ON m.membership_id=q.membership_id
JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id AND i.service_type_id=q.service_type_id
WHERE q.spent<0 OR (i.quota_per_cycle<>-1 AND q.spent>i.quota_per_cycle)
UNION ALL SELECT 'event_capacity',COUNT_BIG(*)
FROM running_capacity r JOIN dbo.group_class_session g ON g.session_id=r.session_id
WHERE r.occupied<0 OR r.occupied>g.max_capacity
UNION ALL SELECT 'unknown_quota',COUNT_BIG(*)
FROM dbo.membership m JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id
WHERE m.start_date IS NOT NULL AND i.service_type_id<>1
  AND dbo.demo_unreconciled_quota(m.membership_id,i.service_type_id)=1
UNION ALL SELECT 'payment_snapshot_or_dates',COUNT_BIG(*)
FROM dbo.membership m JOIN dbo.member a ON m.person_id=a.person_id JOIN dbo.membership_plan l ON l.plan_id=m.plan_id
LEFT JOIN dbo.payment p ON p.membership_id=m.membership_id
LEFT JOIN dbo.staff s ON s.person_id=p.recorded_by
WHERE m.created_at>@Reference OR CONVERT(date,m.created_at)<a.join_date
   OR (m.status='PENDING_PAYMENT' AND (p.payment_id IS NOT NULL OR m.total_price IS NOT NULL))
   OR (m.status<>'PENDING_PAYMENT' AND (p.payment_id IS NULL OR m.total_price IS NULL OR p.amount<>m.total_price
        OR m.total_price<>l.base_price OR s.person_id IS NULL OR s.employment_status<>'ACTIVE'
        OR s.hire_date>CONVERT(date,p.payment_time) OR p.payment_time<m.created_at OR p.payment_time>@Reference))
   OR (m.status IN ('ACTIVE','EXPIRED') AND (m.start_date IS NULL OR m.end_date<>DATEADD(month,l.duration_months,m.start_date)
        OR CONVERT(date,p.payment_time)>m.start_date OR m.start_date>CONVERT(date,@Reference)))
   OR (m.status IN ('PENDING_PAYMENT','PENDING_ACTIVATION') AND (m.start_date IS NOT NULL OR m.end_date IS NOT NULL))
   OR (m.status='ACTIVE' AND m.end_date<CONVERT(date,@Reference))
   OR (m.status='EXPIRED' AND m.end_date>=CONVERT(date,@Reference))
UNION ALL SELECT 'overlapping_memberships',COUNT_BIG(*)
FROM dbo.membership a JOIN dbo.membership b ON a.person_id=b.person_id
  AND a.membership_id<b.membership_id AND a.start_date<=b.end_date AND b.start_date<=a.end_date
UNION ALL SELECT 'session_missing_subtype_or_certification',COUNT_BIG(*)
FROM dbo.[session] s JOIN dbo.trainer t ON t.person_id=s.trainer_id JOIN dbo.room r ON r.room_id=s.room_id
LEFT JOIN dbo.pt_session p ON p.session_id=s.session_id LEFT JOIN dbo.group_class_session g ON g.session_id=s.session_id
LEFT JOIN dbo.trainer_certification c ON c.person_id=t.person_id AND c.certification=CASE g.category
    WHEN N'YOGA' THEN N'Yoga Alliance' WHEN N'CYCLING' THEN N'Đạp xe trong nhà'
    WHEN N'ZUMBA' THEN N'Hướng dẫn Zumba' WHEN N'BOXING' THEN N'Boxing Fitness' ELSE N'Huấn luyện nhóm cơ bản' END
WHERE s.created_at>s.start_time OR s.created_at>@Reference OR CONVERT(date,s.created_at)<t.hire_date
    OR r.status<>'AVAILABLE' OR t.employment_status<>'ACTIVE'
    OR (s.session_type='GROUP' AND (g.session_id IS NULL OR p.session_id IS NOT NULL OR c.person_id IS NULL))
    OR (s.session_type='PERSONAL' AND (p.session_id IS NULL OR g.session_id IS NOT NULL))
UNION ALL SELECT 'maintenance_history_dates',COUNT_BIG(*)
FROM dbo.equipment_maintenance_log a
WHERE a.start_date>CONVERT(date,@Reference) OR a.end_date>CONVERT(date,@Reference)
   OR EXISTS (SELECT 1 FROM dbo.equipment_maintenance_log b WHERE b.equipment_id=a.equipment_id
        AND b.maintenance_id>a.maintenance_id
        AND a.start_date<=COALESCE(b.end_date,'9999-12-31')
        AND b.start_date<=COALESCE(a.end_date,'9999-12-31'));
