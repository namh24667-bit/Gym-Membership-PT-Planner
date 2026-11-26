-- Generated from LOCAL-01 through LOCAL-05C-R1A. Apply only through the portable installer.
CREATE TABLE person (
    person_id INT IDENTITY(1,1) PRIMARY KEY,
    ssn VARCHAR(12) NOT NULL UNIQUE,
    full_name NVARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL UNIQUE,
    date_of_birth DATE NOT NULL,
    gender VARCHAR(10) NOT NULL,
    address NVARCHAR(255),
    created_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    password_hash VARCHAR(255) NOT NULL,
    CHECK (LEN(ssn) = 12 AND ssn NOT LIKE '%[^0-9]%'),
    CHECK (email LIKE '%_@_%._%'),
    CHECK (gender IN ('MALE', 'FEMALE', 'OTHER'))
);

CREATE TABLE member (
    person_id INT PRIMARY KEY,
    emergency_contact_phone VARCHAR(15) NOT NULL,
    join_date DATE NOT NULL DEFAULT CAST(SYSDATETIME() AS DATE),
    health_notes NVARCHAR(500),
    CONSTRAINT fk_member_person_id FOREIGN KEY (person_id)
        REFERENCES person(person_id)
);

CREATE TABLE trainer (
    person_id INT PRIMARY KEY,
    hire_date DATE NOT NULL,
    employment_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    CHECK (employment_status IN ('ACTIVE', 'ON_LEAVE', 'TERMINATED')),
    CONSTRAINT fk_trainer_person_id FOREIGN KEY (person_id)
        REFERENCES person(person_id)
);

CREATE TABLE trainer_certification (
    person_id INT NOT NULL,
    certification NVARCHAR(100) NOT NULL,
    PRIMARY KEY (person_id, certification),
    CONSTRAINT fk_trainer_cert_person_id FOREIGN KEY (person_id)
        REFERENCES trainer(person_id) ON DELETE CASCADE
);

CREATE TABLE staff (
    person_id INT PRIMARY KEY,
    position NVARCHAR(50) NOT NULL,
    hire_date DATE NOT NULL,
    employment_status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    CHECK (employment_status IN ('ACTIVE', 'ON_LEAVE', 'TERMINATED')),
    CONSTRAINT fk_staff_person_id FOREIGN KEY (person_id)
        REFERENCES person(person_id)
);

CREATE TABLE membership_plan (
    plan_id INT IDENTITY(1,1) PRIMARY KEY,
    plan_name NVARCHAR(100) NOT NULL UNIQUE,
    duration_months INT NOT NULL CHECK (duration_months > 0),
    base_price DECIMAL(12,2) NOT NULL CHECK (base_price >= 0),
    description NVARCHAR(500)
);

CREATE TABLE service_type (
    service_type_id INT IDENTITY(1,1) PRIMARY KEY,
    service_name NVARCHAR(100) NOT NULL UNIQUE,
    description NVARCHAR(500)
);

CREATE TABLE room (
    room_id INT IDENTITY(1,1) PRIMARY KEY,
    room_name NVARCHAR(100) NOT NULL UNIQUE,
    room_type VARCHAR(30) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'AVAILABLE',
    CHECK (status IN ('AVAILABLE', 'MAINTENANCE'))
);

CREATE TABLE membership (
    membership_id INT IDENTITY(1,1) PRIMARY KEY,
    person_id INT NOT NULL,
    plan_id INT NOT NULL,
    start_date DATE,
    end_date DATE,
    status VARCHAR(25) NOT NULL DEFAULT 'PENDING_PAYMENT',
    total_price DECIMAL(12,2) CHECK (total_price >= 0),
    created_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CHECK ((start_date IS NULL AND end_date IS NULL)
        OR (start_date IS NOT NULL AND end_date IS NOT NULL AND end_date > start_date)),
    CONSTRAINT fk_membership_person_id FOREIGN KEY (person_id)
        REFERENCES member(person_id),
    CONSTRAINT fk_membership_plan_id FOREIGN KEY (plan_id)
        REFERENCES membership_plan(plan_id),
    CHECK (status IN ('PENDING_PAYMENT', 'PENDING_ACTIVATION', 'ACTIVE', 'EXPIRED'))
);

CREATE TABLE plan_inclusion (
    plan_id INT NOT NULL,
    service_type_id INT NOT NULL,
    quota_per_cycle INT NOT NULL DEFAULT 0 CHECK (quota_per_cycle >= -1),
    PRIMARY KEY (plan_id, service_type_id),
    CONSTRAINT fk_plan_incl_plan_id FOREIGN KEY (plan_id)
        REFERENCES membership_plan(plan_id) ON DELETE CASCADE,
    CONSTRAINT fk_plan_incl_service_id FOREIGN KEY (service_type_id)
        REFERENCES service_type(service_type_id)
);

CREATE TABLE [session] (
    session_id INT IDENTITY(1,1) PRIMARY KEY,
    trainer_id INT NOT NULL,
    room_id INT NOT NULL,
    start_time DATETIME2(0) NOT NULL,
    end_time DATETIME2(0) NOT NULL,
    session_type VARCHAR(15) NOT NULL,
    created_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    CHECK (end_time > start_time),
    CHECK (session_type IN ('PERSONAL', 'GROUP')),
    CONSTRAINT fk_session_trainer_id FOREIGN KEY (trainer_id)
        REFERENCES trainer(person_id),
    CONSTRAINT fk_session_room_id FOREIGN KEY (room_id)
        REFERENCES room(room_id)
);

CREATE TABLE pt_session (
    session_id INT PRIMARY KEY,
    person_id INT NOT NULL,
    training_focus NVARCHAR(200) NOT NULL,
    CONSTRAINT fk_pt_session_id FOREIGN KEY (session_id)
        REFERENCES [session](session_id) ON DELETE CASCADE,
    CONSTRAINT fk_pt_session_person_id FOREIGN KEY (person_id)
        REFERENCES member(person_id)
);

CREATE TABLE group_class_session (
    session_id INT PRIMARY KEY,
    class_name NVARCHAR(100) NOT NULL,
    category NVARCHAR(50) NOT NULL,
    max_capacity INT NOT NULL CHECK (max_capacity > 0),
    CONSTRAINT fk_group_class_session_id FOREIGN KEY (session_id)
        REFERENCES [session](session_id) ON DELETE CASCADE
);

CREATE TABLE member_service_usage (
    usage_id INT IDENTITY(1,1) PRIMARY KEY,
    membership_id INT NOT NULL,
    service_type_id INT NOT NULL,
    session_id INT,
    used_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    usage_status VARCHAR(15) NOT NULL DEFAULT 'USED',
    CHECK (usage_status IN ('USED', 'REFUNDED')),
    CONSTRAINT fk_usage_membership_id FOREIGN KEY (membership_id)
        REFERENCES membership(membership_id),
    CONSTRAINT fk_usage_service_type_id FOREIGN KEY (service_type_id)
        REFERENCES service_type(service_type_id),
    CONSTRAINT fk_usage_session_id FOREIGN KEY (session_id)
        REFERENCES [session](session_id) ON DELETE SET NULL
);

CREATE TABLE booking (
    booking_id INT IDENTITY(1,1) PRIMARY KEY,
    person_id INT NOT NULL,
    session_id INT NOT NULL,
    booked_at DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    booking_status VARCHAR(15) NOT NULL DEFAULT 'SUCCESS',
    cancelled_at DATETIME2(0),
    CHECK (booking_status IN ('SUCCESS', 'CANCEL')),
    CHECK ((booking_status = 'SUCCESS' AND cancelled_at IS NULL)
        OR (booking_status = 'CANCEL' AND cancelled_at IS NOT NULL AND cancelled_at >= booked_at)),
    CONSTRAINT fk_booking_person_id FOREIGN KEY (person_id)
        REFERENCES member(person_id),
    CONSTRAINT fk_booking_session_id FOREIGN KEY (session_id)
        REFERENCES group_class_session(session_id)
);

CREATE TABLE equipment (
    equipment_id INT IDENTITY(1,1) PRIMARY KEY,
    equipment_name NVARCHAR(100) NOT NULL,
    serial_number VARCHAR(50) NOT NULL UNIQUE,
    room_id INT,
    status VARCHAR(20) NOT NULL DEFAULT 'ACTIVE',
    CHECK (status IN ('ACTIVE', 'MAINTENANCE', 'RETIRED')),
    CONSTRAINT fk_equipment_room_id FOREIGN KEY (room_id)
        REFERENCES room(room_id) ON DELETE SET NULL
);

CREATE TABLE payment (
    payment_id INT IDENTITY(1,1) PRIMARY KEY,
    membership_id INT NOT NULL UNIQUE,
    amount DECIMAL(12,2) NOT NULL CHECK (amount >= 0),
    payment_time DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    payment_method VARCHAR(20) NOT NULL,
    CHECK (payment_method IN ('CASH', 'BANK_TRANSFER')),
    CONSTRAINT fk_payment_membership_id FOREIGN KEY (membership_id)
        REFERENCES membership(membership_id)
);

CREATE TABLE equipment_maintenance_log (
    maintenance_id INT IDENTITY(1,1) PRIMARY KEY,
    equipment_id INT NOT NULL,
    start_date DATE NOT NULL DEFAULT CAST(SYSDATETIME() AS DATE),
    cost DECIMAL(12,2) CHECK (cost >= 0),
    end_date DATE,
    description NVARCHAR(500),
    CHECK (end_date IS NULL OR end_date >= start_date),
    CONSTRAINT fk_maint_log_equip_id FOREIGN KEY (equipment_id)
        REFERENCES equipment(equipment_id)
);

CREATE UNIQUE INDEX ux_membership_one_active
ON membership(person_id)
WHERE status = 'ACTIVE';

CREATE UNIQUE INDEX ux_booking_active_member_session
ON booking(person_id, session_id)
WHERE booking_status = 'SUCCESS';

CREATE INDEX ix_booking_session_status
ON booking(session_id, booking_status);
GO

CREATE VIEW vw_group_class_enrollment AS
SELECT g.session_id, g.class_name, g.category, s.start_time, g.max_capacity,
       COUNT(b.booking_id) AS current_enrollment,
       g.max_capacity - COUNT(b.booking_id) AS available_slots
FROM group_class_session g
JOIN [session] s ON g.session_id = s.session_id
LEFT JOIN booking b ON g.session_id = b.session_id
                   AND b.booking_status = 'SUCCESS'
GROUP BY g.session_id, g.class_name, g.category, s.start_time, g.max_capacity;
GO

CREATE VIEW vw_monthly_revenue AS
SELECT YEAR(payment_time) AS nam, MONTH(payment_time) AS thang,
       COUNT(*) AS so_giao_dich, SUM(amount) AS tong_doanh_thu
FROM payment
GROUP BY YEAR(payment_time), MONTH(payment_time);
GO

CREATE TRIGGER trg_session_check
ON [session]
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN trainer t ON i.trainer_id = t.person_id
        WHERE t.employment_status <> 'ACTIVE'
    )
        THROW 51001, N'Huan luyen vien khong o trang thai ACTIVE.', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN room r ON i.room_id = r.room_id
        WHERE r.status = 'MAINTENANCE'
    )
        THROW 51002, N'Phong dang bao tri, khong the tao lich.', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s ON i.trainer_id = s.trainer_id
        WHERE i.session_id <> s.session_id
          AND i.start_time < s.end_time
          AND s.start_time < i.end_time
    )
        THROW 51003, N'Huan luyen vien bi trung lich.', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s ON i.room_id = s.room_id
        WHERE i.session_id <> s.session_id
          AND i.start_time < s.end_time
          AND s.start_time < i.end_time
    )
        THROW 51004, N'Phong tap bi trung lich.', 1;
END;
GO

CREATE TRIGGER trg_booking_check
ON booking
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN group_class_session g ON i.session_id = g.session_id
        WHERE i.booking_status = 'SUCCESS'
          AND (
              SELECT COUNT(*)
              FROM booking b
              WHERE b.session_id = i.session_id
                AND b.booking_status = 'SUCCESS'
          ) > g.max_capacity
    )
        THROW 51005, N'Lop hoc da du so luong nguoi tham gia.', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s1 ON i.session_id = s1.session_id
        JOIN booking b ON i.person_id = b.person_id
                      AND i.booking_id <> b.booking_id
                      AND b.booking_status = 'SUCCESS'
        JOIN [session] s2 ON b.session_id = s2.session_id
        WHERE i.booking_status = 'SUCCESS'
          AND s1.start_time < s2.end_time
          AND s2.start_time < s1.end_time
    )
        THROW 51006, N'Hoi vien da dat lop khac trung gio.', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s1 ON i.session_id = s1.session_id
        JOIN pt_session p ON i.person_id = p.person_id
        JOIN [session] s2 ON p.session_id = s2.session_id
        WHERE i.booking_status = 'SUCCESS'
          AND s1.start_time < s2.end_time
          AND s2.start_time < s1.end_time
    )
        THROW 51007, N'Hoi vien co buoi PT trung gio.', 1;
END;
GO

CREATE TRIGGER trg_pt_session_check
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
        THROW 51008, N'Hoi vien bi trung lich PT.', 1;

    IF EXISTS (
        SELECT 1
        FROM inserted i
        JOIN [session] s1 ON i.session_id = s1.session_id
        JOIN booking b ON i.person_id = b.person_id
                      AND b.booking_status = 'SUCCESS'
        JOIN [session] s2 ON b.session_id = s2.session_id
        WHERE s1.start_time < s2.end_time
          AND s2.start_time < s1.end_time
    )
        THROW 51009, N'Hoi vien co lop nhom trung gio PT.', 1;
END;
GO

ALTER TABLE dbo.membership ADD local02_request_id uniqueidentifier NULL;
GO

CREATE UNIQUE INDEX ux_membership_local02_request ON dbo.membership(local02_request_id)
 WHERE local02_request_id IS NOT NULL;
GO

CREATE PROCEDURE dbo.local02_register_member
 @full_name nvarchar(100), @ssn varchar(12), @birth date, @gender varchar(10),
 @address nvarchar(255), @email varchar(255), @phone varchar(15), @emergency varchar(15),
 @health nvarchar(500), @password_hash varchar(255)
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRY
   BEGIN TRANSACTION;
   DECLARE @today date=CONVERT(date,SYSDATETIME());
   IF @birth IS NULL OR @phone=@emergency OR DATEDIFF(year,@birth,@today)-
       CASE WHEN MONTH(@today)*100+DAY(@today)<MONTH(@birth)*100+DAY(@birth) THEN 1 ELSE 0 END<15
     THROW 52107,'Invalid member details',1;
   INSERT dbo.person(full_name,ssn,date_of_birth,gender,address,email,phone,password_hash)
     VALUES(@full_name,@ssn,@birth,@gender,@address,LOWER(TRIM(@email)),@phone,@password_hash);
   DECLARE @person_id int=CONVERT(int,SCOPE_IDENTITY());
   INSERT dbo.member(person_id,emergency_contact_phone,health_notes)
     VALUES(@person_id,@emergency,@health);
   COMMIT TRANSACTION;
 END TRY
 BEGIN CATCH
   IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
   IF ERROR_NUMBER() IN (2601,2627) THROW 52102,'Duplicate member details',1;
   THROW;
 END CATCH;
 SELECT @person_id AS person_id;
END;
GO

CREATE PROCEDURE dbo.local02_catalog @plan_id int=NULL
AS
BEGIN
 SET NOCOUNT ON;
 SELECT p.plan_id,p.plan_name,p.duration_months,p.base_price,p.description,
        s.service_name,i.quota_per_cycle
 FROM dbo.membership_plan p LEFT JOIN dbo.plan_inclusion i ON i.plan_id=p.plan_id
 LEFT JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
 WHERE @plan_id IS NULL OR p.plan_id=@plan_id
 ORDER BY p.plan_name,p.plan_id,s.service_name;
END;
GO

CREATE PROCEDURE dbo.local02_staff_members @actor int, @member_id int=NULL, @search nvarchar(100)=NULL
AS
BEGIN
 SET NOCOUNT ON;
 IF NOT EXISTS (SELECT 1 FROM dbo.staff WHERE person_id=@actor AND employment_status='ACTIVE')
    THROW 52101,'Staff required',1;
 SELECT TOP (75) p.person_id,p.full_name,p.email,p.phone,m.join_date,
     CASE WHEN EXISTS(SELECT 1 FROM dbo.membership c WHERE c.person_id=m.person_id
                 AND c.status='ACTIVE' AND CONVERT(date,SYSDATETIME()) BETWEEN c.start_date AND c.end_date)
          THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS has_active
 FROM dbo.member m JOIN dbo.person p ON p.person_id=m.person_id
 WHERE (@member_id IS NULL OR m.person_id=@member_id)
 AND (@search IS NULL OR CHARINDEX(@search,p.full_name)>0 OR CHARINDEX(@search,p.phone)>0
  OR CHARINDEX(@search,p.email)>0 OR p.ssn=@search)
 ORDER BY p.person_id DESC;
END;
GO

CREATE PROCEDURE dbo.local02_create_contract @actor int,@plan_id int,@expected_price decimal(12,2),
 @request_id uniqueidentifier
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 DECLARE @member_lock int,@contract int,@existing_actor int,@existing_plan int,@price decimal(12,2);
 SELECT @member_lock=person_id FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@actor;
 IF @member_lock IS NULL THROW 52101,'Member required',1;
 IF @request_id IS NULL THROW 52107,'Invalid request identifier',1;
 SELECT @contract=membership_id,@existing_actor=person_id,@existing_plan=plan_id
 FROM dbo.membership WHERE local02_request_id=@request_id;
 IF @contract IS NOT NULL
 BEGIN
   IF @existing_actor<>@actor OR @existing_plan<>@plan_id THROW 52107,'Request identifier conflict',1;
   COMMIT TRANSACTION;
   SELECT @contract AS membership_id;
   RETURN;
 END;
 SELECT @price=base_price FROM dbo.membership_plan WITH (HOLDLOCK) WHERE plan_id=@plan_id;
 IF @price IS NULL THROW 52103,'Plan not available',1;
 IF @expected_price IS NULL OR @expected_price<>@price THROW 52104,'Price confirmation required',1;
 BEGIN TRY
   INSERT dbo.membership(person_id,plan_id,local02_request_id)
     VALUES(@actor,@plan_id,@request_id);
   SET @contract=CONVERT(int,SCOPE_IDENTITY());
   COMMIT TRANSACTION;
 END TRY
 BEGIN CATCH
   IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
   IF ERROR_NUMBER() IN (2601,2627) THROW 52107,'Request identifier conflict',1;
   THROW;
 END CATCH;
 SELECT @contract AS membership_id;
END;
GO

CREATE PROCEDURE dbo.local02_contracts
 @actor int,@staff_scope bit,@contract_id int=NULL,@member_id int=NULL,@status varchar(25)=NULL
AS
BEGIN
 SET NOCOUNT ON;
 IF @staff_scope=1
 BEGIN
   IF NOT EXISTS (SELECT 1 FROM dbo.staff WHERE person_id=@actor AND employment_status='ACTIVE')
     THROW 52101,'Staff required',1;
 END
 ELSE
 BEGIN
   IF NOT EXISTS (SELECT 1 FROM dbo.member WHERE person_id=@actor) THROW 52101,'Member required',1;
   SET @member_id=@actor;
 END;
 SELECT TOP (100) m.membership_id,m.person_id,p.full_name,l.plan_name,m.status,m.start_date,m.end_date,
     m.total_price,l.base_price,t.payment_id,t.amount,t.payment_method,t.payment_time,m.plan_id
 FROM dbo.membership m JOIN dbo.person p ON p.person_id=m.person_id
 JOIN dbo.membership_plan l ON l.plan_id=m.plan_id
 LEFT JOIN dbo.payment t ON t.membership_id=m.membership_id
 WHERE (@contract_id IS NULL OR m.membership_id=@contract_id)
 AND (@member_id IS NULL OR m.person_id=@member_id)
 AND (@status IS NULL OR m.status=@status)
 ORDER BY m.membership_id DESC;
END;
GO

CREATE PROCEDURE dbo.local02_benefits @actor int,@contract_id int
AS
BEGIN
 SET NOCOUNT ON;
 SELECT s.service_name,i.quota_per_cycle,u.used,
    CASE WHEN m.status='ACTIVE' AND CONVERT(date,SYSDATETIME()) BETWEEN m.start_date AND m.end_date
      THEN CAST(1 AS bit) ELSE CAST(0 AS bit) END AS available
 FROM dbo.membership m JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id
 JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
 CROSS APPLY (SELECT COUNT_BIG(*) AS used FROM dbo.member_service_usage x
   WHERE x.membership_id=m.membership_id AND x.service_type_id=i.service_type_id AND x.usage_status='USED') u
 WHERE m.membership_id=@contract_id AND m.person_id=@actor
 ORDER BY s.service_name;
END;
GO

CREATE PROCEDURE dbo.local02_activate_paid @contract_id int,@member_id int
AS
BEGIN
 SET NOCOUNT ON;
 DECLARE @today date=CONVERT(date,SYSDATETIME()), @months int;
 SELECT @months=l.duration_months
 FROM dbo.membership m JOIN dbo.membership_plan l ON l.plan_id=m.plan_id
 JOIN dbo.payment p ON p.membership_id=m.membership_id AND p.amount=m.total_price
 WHERE m.membership_id=@contract_id AND m.person_id=@member_id AND m.status='PENDING_ACTIVATION'
  AND m.start_date IS NULL AND m.end_date IS NULL;
 IF @months IS NULL OR @months<=0 THROW 52105,'Paid pending contract required',1;
 UPDATE dbo.membership SET status='EXPIRED'
 WHERE person_id=@member_id AND status='ACTIVE' AND end_date<@today;
 IF EXISTS (SELECT 1 FROM dbo.membership WHERE person_id=@member_id AND status='ACTIVE')
   THROW 52106,'Member already has an active membership',1;
 UPDATE dbo.membership SET status='ACTIVE',start_date=@today,end_date=DATEADD(month,@months,@today)
 WHERE membership_id=@contract_id AND person_id=@member_id AND status='PENDING_ACTIVATION';
 IF @@ROWCOUNT<>1 THROW 52105,'Contract status changed',1;
END;
GO

CREATE PROCEDURE dbo.local02_collect_payment
 @actor int,@contract_id int,@expected_price decimal(12,2),@method varchar(20),@activate_now bit
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 IF NOT EXISTS (SELECT 1 FROM dbo.staff WITH (HOLDLOCK) WHERE person_id=@actor AND employment_status='ACTIVE')
   THROW 52101,'Active staff required',1;
 IF @method IS NULL OR @method NOT IN ('CASH','BANK_TRANSFER') OR @activate_now IS NULL
   THROW 52107,'Invalid payment details',1;
 DECLARE @member_id int,@locked int,@status varchar(25),@price decimal(12,2),@payment_id int;
 SELECT @member_id=person_id FROM dbo.membership WHERE membership_id=@contract_id;
 IF @member_id IS NULL THROW 52103,'Contract does not exist',1;
 SELECT @locked=person_id FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@member_id;
 SELECT @status=m.status,@price=p.base_price FROM dbo.membership m WITH (UPDLOCK,HOLDLOCK)
 JOIN dbo.membership_plan p WITH (HOLDLOCK) ON p.plan_id=m.plan_id
 WHERE m.membership_id=@contract_id AND m.person_id=@locked;
 IF @status IS NULL OR @status<>'PENDING_PAYMENT'
    OR EXISTS (SELECT 1 FROM dbo.payment WHERE membership_id=@contract_id)
   THROW 52105,'Contract is not payable',1;
 IF @expected_price IS NULL OR @expected_price<>@price THROW 52104,'Price confirmation required',1;
 INSERT dbo.payment(membership_id,amount,payment_method) VALUES (@contract_id,@price,@method);
 SET @payment_id=CONVERT(int,SCOPE_IDENTITY());
 UPDATE dbo.membership SET total_price=@price,status='PENDING_ACTIVATION'
 WHERE membership_id=@contract_id AND status='PENDING_PAYMENT';
 IF @@ROWCOUNT<>1 THROW 52105,'Contract status changed',1;
 IF @activate_now=1 EXEC dbo.local02_activate_paid @contract_id,@locked;
 COMMIT TRANSACTION;
 SELECT @payment_id AS payment_id;
END;
GO

CREATE PROCEDURE dbo.local02_activate @actor int,@contract_id int
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 IF NOT EXISTS (SELECT 1 FROM dbo.staff WITH (HOLDLOCK) WHERE person_id=@actor AND employment_status='ACTIVE')
   THROW 52101,'Active staff required',1;
 DECLARE @member_id int,@locked int;
 SELECT @member_id=person_id FROM dbo.membership WHERE membership_id=@contract_id;
 IF @member_id IS NULL THROW 52103,'Contract does not exist',1;
 SELECT @locked=person_id FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@member_id;
 EXEC dbo.local02_activate_paid @contract_id,@locked;
 COMMIT TRANSACTION;
 SELECT @contract_id AS membership_id;
END;
GO

ALTER TABLE dbo.member_service_usage ADD booking_id int NULL;
GO

ALTER TABLE dbo.member_service_usage WITH CHECK ADD CONSTRAINT fk_usage_booking
 FOREIGN KEY (booking_id) REFERENCES dbo.booking(booking_id);
CREATE UNIQUE INDEX ux_usage_one_per_booking ON dbo.member_service_usage(booking_id)
 WHERE booking_id IS NOT NULL;
GO

CREATE PROCEDURE dbo.local03_entitlement
 @member int,@kind varchar(8),@start datetime2(0),@end datetime2(0),
 @membership int OUTPUT,@service int OUTPUT
AS
BEGIN
 SET NOCOUNT ON;
 DECLARE @today date=CONVERT(date,SYSDATETIME()),@plan int,@quota int,@matches int;
 SELECT @membership=membership_id,@plan=plan_id
 FROM dbo.membership WITH (UPDLOCK,HOLDLOCK)
 WHERE person_id=@member AND status='ACTIVE'
   AND @today BETWEEN start_date AND end_date
   AND CONVERT(date,@start)>=start_date AND CONVERT(date,@end)<=end_date;
 IF @membership IS NULL THROW 52202,'Membership outside its effective dates',1;
 SELECT @matches=COUNT(*),@service=MAX(i.service_type_id),@quota=MAX(i.quota_per_cycle)
 FROM dbo.plan_inclusion i WITH (HOLDLOCK) JOIN dbo.service_type t ON t.service_type_id=i.service_type_id
 WHERE i.plan_id=@plan AND ((@kind='PT' AND t.service_name IN (N'PT cá nhân',N'Local-02 · Buổi PT'))
    OR (@kind='GROUP' AND t.service_name=N'Lớp nhóm'));
 IF @matches<>1 THROW 52203,'No unambiguous service entitlement',1;
 IF @quota<>-1 AND (SELECT COUNT_BIG(*) FROM dbo.member_service_usage
     WHERE membership_id=@membership AND service_type_id=@service AND usage_status='USED')>=@quota
   THROW 52204,'Quota exhausted',1;
END;
GO

CREATE PROCEDURE dbo.local03_lock_slot
 @trainer int,@room int,@start datetime2(0),@end datetime2(0)
AS
BEGIN
 SET NOCOUNT ON;
 IF @start IS NULL OR @end IS NULL OR @start<=SYSDATETIME() OR @start>=@end
   THROW 52205,'Invalid or past time slot',1;
 IF NOT EXISTS(SELECT 1 FROM dbo.trainer WITH (UPDLOCK,HOLDLOCK)
     WHERE person_id=@trainer AND employment_status='ACTIVE')
   THROW 52206,'Trainer unavailable',1;
 IF NOT EXISTS(SELECT 1 FROM dbo.room WITH (UPDLOCK,HOLDLOCK)
     WHERE room_id=@room AND status='AVAILABLE')
   THROW 52206,'Room unavailable',1;
END;
GO

CREATE PROCEDURE dbo.local03_book_pt
 @actor int,@trainer int,@room int,@start datetime2(0),@end datetime2(0),@focus nvarchar(200)
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 BEGIN TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@actor)
   THROW 52201,'Member required',1;
 IF NULLIF(TRIM(@focus),N'') IS NULL THROW 52205,'Training focus required',1;
 DECLARE @session int,@membership int,@service int;
 SELECT @session=s.session_id FROM dbo.[session] s JOIN dbo.pt_session p ON p.session_id=s.session_id
 WHERE p.person_id=@actor AND s.session_type='PERSONAL' AND s.trainer_id=@trainer AND s.room_id=@room
   AND s.start_time=@start AND s.end_time=@end AND p.training_focus=@focus;
 IF @session IS NULL
 BEGIN
   EXEC dbo.local03_entitlement @actor,'PT',@start,@end,@membership OUTPUT,@service OUTPUT;
   EXEC dbo.local03_lock_slot @trainer,@room,@start,@end;
   INSERT dbo.[session](trainer_id,room_id,start_time,end_time,session_type)
      VALUES(@trainer,@room,@start,@end,'PERSONAL');
   SET @session=CONVERT(int,SCOPE_IDENTITY());
   INSERT dbo.pt_session(session_id,person_id,training_focus) VALUES(@session,@actor,@focus);
   INSERT dbo.member_service_usage(membership_id,service_type_id,session_id)
      VALUES(@membership,@service,@session);
 END;
 COMMIT TRANSACTION;
 SELECT @session AS session_id;
END;
GO

CREATE PROCEDURE dbo.local03_book_group @actor int,@session int,@expected_booking int
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 BEGIN TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@actor)
   THROW 52201,'Member required',1;
 DECLARE @capacity int,@start datetime2(0),@end datetime2(0),@booking int,@status varchar(15),
         @membership int,@service int;
 SELECT @capacity=g.max_capacity FROM dbo.group_class_session g WITH (UPDLOCK,HOLDLOCK) WHERE g.session_id=@session;
 IF @capacity IS NULL THROW 52207,'Class not found',1;
 SELECT @start=s.start_time,@end=s.end_time FROM dbo.[session] s
 JOIN dbo.trainer t WITH (HOLDLOCK) ON t.person_id=s.trainer_id AND t.employment_status='ACTIVE'
 JOIN dbo.room r WITH (HOLDLOCK) ON r.room_id=s.room_id AND r.status='AVAILABLE'
 WHERE s.session_id=@session AND s.session_type='GROUP';
 IF @start IS NULL THROW 52206,'Class trainer or room unavailable',1;
 IF @start<=SYSDATETIME() THROW 52205,'Class already started',1;
 SELECT TOP (1) @booking=booking_id,@status=booking_status FROM dbo.booking
 WHERE person_id=@actor AND session_id=@session ORDER BY booking_id DESC;
 IF @status='SUCCESS' OR @expected_booking IS NULL OR COALESCE(@booking,0)<>@expected_booking
   THROW 52208,'Booking state changed',1;
 EXEC dbo.local03_entitlement @actor,'GROUP',@start,@end,@membership OUTPUT,@service OUTPUT;
 IF (SELECT COUNT(*) FROM dbo.booking WHERE session_id=@session AND booking_status='SUCCESS')>=@capacity
   THROW 52209,'Class is full',1;
 INSERT dbo.booking(person_id,session_id) VALUES(@actor,@session);
 SET @booking=CONVERT(int,SCOPE_IDENTITY());
 INSERT dbo.member_service_usage(membership_id,service_type_id,session_id,booking_id)
   VALUES(@membership,@service,@session,@booking);
 COMMIT TRANSACTION;
 SELECT @booking AS booking_id;
END;
GO

CREATE PROCEDURE dbo.local03_cancel_group @actor int,@booking int
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 BEGIN TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@actor)
   THROW 52201,'Member required',1;
 DECLARE @session int,@class int,@start datetime2(0),@now datetime2(7),@refunded int=0;
 SELECT @session=session_id FROM dbo.booking WHERE booking_id=@booking AND person_id=@actor;
 IF @session IS NULL THROW 52207,'Booking not found',1;
 SELECT @class=session_id FROM dbo.group_class_session WITH (UPDLOCK,HOLDLOCK) WHERE session_id=@session;
 SELECT @start=start_time FROM dbo.[session] WHERE session_id=@class AND session_type='GROUP';
 SET @now=SYSDATETIME();
 IF @start IS NULL OR @now>=@start THROW 52205,'Class already started',1;
 UPDATE dbo.booking SET booking_status='CANCEL',cancelled_at=@now
 WHERE booking_id=@booking AND person_id=@actor AND booking_status='SUCCESS';
 IF @@ROWCOUNT<>1 THROW 52208,'Booking was already cancelled',1;
 IF @now<=DATEADD(hour,-5,@start)
 BEGIN
   UPDATE u SET usage_status='REFUNDED' FROM dbo.member_service_usage u
   JOIN dbo.membership m ON m.membership_id=u.membership_id AND m.person_id=@actor
   WHERE u.booking_id=@booking AND u.session_id=@session AND u.usage_status='USED';
   SET @refunded=@@ROWCOUNT;
 END;
 COMMIT TRANSACTION;
 SELECT @refunded AS refunded;
END;
GO

CREATE PROCEDURE dbo.local03_create_group
 @actor int,@trainer int,@room int,@start datetime2(0),@end datetime2(0),
 @name nvarchar(100),@category nvarchar(50),@capacity int
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 BEGIN TRANSACTION;
 IF NOT EXISTS(SELECT 1 FROM dbo.staff WITH (HOLDLOCK) WHERE person_id=@actor
     AND employment_status='ACTIVE' AND position COLLATE Latin1_General_100_BIN2=N'Quản lý')
   THROW 52201,'Management required',1;
 IF @capacity IS NULL OR @capacity<1 OR NULLIF(TRIM(@name),N'') IS NULL OR NULLIF(TRIM(@category),N'') IS NULL
   THROW 52205,'Invalid class details',1;
 EXEC dbo.local03_lock_slot @trainer,@room,@start,@end;
 INSERT dbo.[session](trainer_id,room_id,start_time,end_time,session_type) VALUES(@trainer,@room,@start,@end,'GROUP');
 DECLARE @session int=CONVERT(int,SCOPE_IDENTITY());
 INSERT dbo.group_class_session(session_id,class_name,category,max_capacity) VALUES(@session,@name,@category,@capacity);
 COMMIT TRANSACTION;
 SELECT @session AS session_id;
END;
GO

CREATE PROCEDURE dbo.local03_expire @actor int,@all bit=0
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 DECLARE @today date=CONVERT(date,SYSDATETIME());
 IF @all=1
 BEGIN
  IF NOT EXISTS(SELECT 1 FROM dbo.staff WHERE person_id=@actor AND employment_status='ACTIVE'
      AND position COLLATE Latin1_General_100_BIN2=N'Quản lý') THROW 52201,'Management required',1;
  UPDATE dbo.membership SET status='EXPIRED' WHERE status='ACTIVE' AND end_date<@today;
 END
 ELSE
 BEGIN
  IF NOT EXISTS(SELECT 1 FROM dbo.member WHERE person_id=@actor) THROW 52201,'Member required',1;
  UPDATE dbo.membership SET status='EXPIRED' WHERE person_id=@actor AND status='ACTIVE' AND end_date<@today;
 END;
 SELECT @@ROWCOUNT AS expired;
END;
GO

CREATE PROCEDURE dbo.local03_focus @actor int,@session int,@focus nvarchar(200)
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 IF NULLIF(TRIM(@focus),N'') IS NULL THROW 52205,'Training focus required',1;
 UPDATE p SET training_focus=@focus
 FROM dbo.pt_session p JOIN dbo.[session] s ON s.session_id=p.session_id
 JOIN dbo.trainer t ON t.person_id=s.trainer_id
 WHERE p.session_id=@session AND s.trainer_id=@actor AND t.employment_status='ACTIVE';
 IF @@ROWCOUNT<>1 THROW 52207,'Training session unavailable',1;
 SELECT @session AS session_id;
END;
GO

CREATE PROCEDURE dbo.local03_schedule @actor int,@scope varchar(20),@id int=NULL
AS
BEGIN
 SET NOCOUNT ON;
 DECLARE @member bit=0,@staff bit=0,@trainer bit=0;
 IF EXISTS(SELECT 1 FROM dbo.member WHERE person_id=@actor) SET @member=1;
 IF EXISTS(SELECT 1 FROM dbo.staff WHERE person_id=@actor AND employment_status='ACTIVE') SET @staff=1;
 IF EXISTS(SELECT 1 FROM dbo.trainer WHERE person_id=@actor AND employment_status IN ('ACTIVE','ON_LEAVE')) SET @trainer=1;
 IF @scope IN ('rooms','trainers','busy') AND (@member=1 OR @staff=1)
 BEGIN
  IF @scope='rooms' SELECT room_id,room_name FROM dbo.room WHERE status='AVAILABLE' ORDER BY room_name;
  IF @scope='trainers'
    SELECT t.person_id,p.full_name,p.gender,t.employment_status,
      (SELECT STRING_AGG(CONVERT(nvarchar(max),c.certification),N', ') FROM dbo.trainer_certification c WHERE c.person_id=t.person_id)
    FROM dbo.trainer t JOIN dbo.person p ON p.person_id=t.person_id WHERE t.employment_status='ACTIVE' ORDER BY p.full_name;
  IF @scope='busy'
    SELECT TOP (100) s.start_time,s.end_time,r.room_name FROM dbo.[session] s JOIN dbo.room r ON r.room_id=s.room_id
    WHERE s.trainer_id=@id AND s.end_time>SYSDATETIME() ORDER BY s.start_time;
  RETURN;
 END;
 IF @scope='classes' AND (@member=1 OR @staff=1)
 BEGIN
  SELECT TOP (150) e.session_id,e.class_name,e.category,p.full_name,r.room_name,s.start_time,s.end_time,
   e.max_capacity,e.current_enrollment,e.available_slots,b.booking_status,COALESCE(b.booking_id,0),
   CAST(CASE WHEN t.employment_status='ACTIVE' AND r.status='AVAILABLE' AND s.start_time>SYSDATETIME()
       THEN 1 ELSE 0 END AS bit)
  FROM dbo.vw_group_class_enrollment e JOIN dbo.[session] s ON s.session_id=e.session_id AND s.session_type='GROUP'
  JOIN dbo.room r ON r.room_id=s.room_id JOIN dbo.trainer t ON t.person_id=s.trainer_id JOIN dbo.person p ON p.person_id=t.person_id
  OUTER APPLY(SELECT TOP (1) x.booking_id,x.booking_status FROM dbo.booking x
      WHERE x.session_id=s.session_id AND x.person_id=@actor AND @member=1 ORDER BY x.booking_id DESC) b
  WHERE @id IS NULL OR s.session_id=@id ORDER BY s.start_time DESC;
  RETURN;
 END;
 IF @scope='member_pt' AND @member=1
 BEGIN
  SELECT TOP (150) s.session_id,p.full_name,r.room_name,s.start_time,s.end_time,x.training_focus
  FROM dbo.pt_session x JOIN dbo.[session] s ON s.session_id=x.session_id AND s.session_type='PERSONAL'
  JOIN dbo.person p ON p.person_id=s.trainer_id JOIN dbo.room r ON r.room_id=s.room_id
  WHERE x.person_id=@actor AND (@id IS NULL OR s.session_id=@id) ORDER BY s.start_time DESC;
  RETURN;
 END;
 IF @scope='member_group' AND @member=1
 BEGIN
  SELECT TOP (150) b.booking_id,g.class_name,s.start_time,s.end_time,b.booking_status,b.cancelled_at,s.session_id,
    CAST(CASE WHEN b.booking_status='SUCCESS' AND s.start_time>SYSDATETIME() THEN 1 ELSE 0 END AS bit),
    u.usage_status
  FROM dbo.booking b JOIN dbo.[session] s ON s.session_id=b.session_id
  JOIN dbo.group_class_session g ON g.session_id=s.session_id
  LEFT JOIN dbo.member_service_usage u ON u.booking_id=b.booking_id
  WHERE b.person_id=@actor ORDER BY b.booking_id DESC;
  RETURN;
 END;
 IF @scope='trainer' AND @trainer=1
 BEGIN
  SELECT TOP (150) s.session_id,s.session_type,s.start_time,s.end_time,r.room_name,g.class_name,p.full_name,
     x.training_focus,t.hire_date,t.employment_status,g.current_enrollment,g.max_capacity
  FROM dbo.[session] s JOIN dbo.room r ON r.room_id=s.room_id JOIN dbo.trainer t ON t.person_id=s.trainer_id
  LEFT JOIN dbo.pt_session x ON x.session_id=s.session_id LEFT JOIN dbo.person p ON p.person_id=x.person_id
  LEFT JOIN dbo.vw_group_class_enrollment g ON g.session_id=s.session_id
  WHERE s.trainer_id=@actor AND (@id IS NULL OR s.session_id=@id) ORDER BY s.start_time DESC;
  RETURN;
 END;
 IF @scope='participants' AND @trainer=1
 BEGIN
  SELECT p.full_name FROM dbo.booking b JOIN dbo.person p ON p.person_id=b.person_id
  JOIN dbo.[session] s ON s.session_id=b.session_id
  WHERE s.trainer_id=@actor AND s.session_type='GROUP' AND s.session_id=@id AND b.booking_status='SUCCESS'
  ORDER BY p.full_name;
  RETURN;
 END;
 IF @scope='staff' AND @staff=1
 BEGIN
  SELECT TOP (150) s.session_id,s.session_type,s.start_time,s.end_time,r.room_name,t.full_name,g.class_name,
     p.full_name,g.current_enrollment,g.max_capacity
  FROM dbo.[session] s JOIN dbo.room r ON r.room_id=s.room_id JOIN dbo.person t ON t.person_id=s.trainer_id
  LEFT JOIN dbo.pt_session x ON x.session_id=s.session_id LEFT JOIN dbo.person p ON p.person_id=x.person_id
  LEFT JOIN dbo.vw_group_class_enrollment g ON g.session_id=s.session_id
  ORDER BY s.start_time DESC;
  RETURN;
 END;
 THROW 52201,'Schedule scope not permitted',1;
END;
GO

ALTER TABLE dbo.membership_plan ADD is_for_sale bit NOT NULL CONSTRAINT df_plan_for_sale DEFAULT(1);
ALTER TABLE dbo.payment ADD recorded_by int NULL;
GO

ALTER TABLE dbo.payment WITH CHECK ADD CONSTRAINT fk_payment_recorded_by FOREIGN KEY(recorded_by)
 REFERENCES dbo.staff(person_id);
GO

CREATE PROCEDURE dbo.local04_staff_guard @actor int,@manager bit=0
AS
BEGIN
 SET NOCOUNT ON;
 IF NOT EXISTS(SELECT 1 FROM dbo.staff WITH (HOLDLOCK) WHERE person_id=@actor AND employment_status='ACTIVE'
   AND (@manager=0 OR position COLLATE Latin1_General_100_BIN2=N'Quản lý'))
   THROW 52301,'Active staff role required',1;
END;
GO

CREATE PROCEDURE dbo.local04_members
 @actor int,@action varchar(20),@id int=NULL,@search nvarchar(100)=NULL,@status varchar(25)=NULL,@offset int=0,
 @name nvarchar(100)=NULL,@email varchar(255)=NULL,@phone varchar(15)=NULL,@address nvarchar(255)=NULL,
 @emergency varchar(15)=NULL,@revision varchar(64)=NULL
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 IF @action='save' BEGIN TRANSACTION;
 EXEC dbo.local04_staff_guard @actor;
 DECLARE @today date=CONVERT(date,SYSDATETIME());
 IF @action='list'
 BEGIN
   SELECT p.person_id,p.full_name,p.email,p.phone,m.join_date,a.has_active
   FROM dbo.member m JOIN dbo.person p ON p.person_id=m.person_id
   CROSS APPLY (SELECT CONVERT(bit,CASE WHEN EXISTS(SELECT 1 FROM dbo.membership c
       WHERE c.person_id=m.person_id AND c.status='ACTIVE' AND @today BETWEEN c.start_date AND c.end_date)
      THEN 1 ELSE 0 END) AS has_active) a
   WHERE (@status IS NULL OR a.has_active=CASE @status WHEN 'ACTIVE' THEN 1 WHEN 'INACTIVE' THEN 0 END)
     AND (@search IS NULL OR CHARINDEX(@search,p.full_name)>0 OR CHARINDEX(@search,p.phone)>0
       OR CHARINDEX(@search,p.email)>0 OR p.ssn=@search)
   ORDER BY p.person_id DESC OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
   RETURN;
 END;
 IF NOT EXISTS(SELECT 1 FROM dbo.member WHERE person_id=@id) THROW 52303,'Member not found',1;
 IF @action='profile'
   SELECT p.person_id,p.full_name,p.email,p.phone,p.address,m.emergency_contact_phone,m.join_date,
     CONVERT(varchar(64),HASHBYTES('SHA2_256',(SELECT p.full_name,p.email,p.phone,p.address,m.emergency_contact_phone
       FOR JSON PATH,WITHOUT_ARRAY_WRAPPER,INCLUDE_NULL_VALUES)),2) AS revision
   FROM dbo.person p JOIN dbo.member m ON m.person_id=p.person_id WHERE p.person_id=@id;
 ELSE IF @action='history'
 BEGIN
   SELECT 'PT' AS kind,s.session_id,N'Buổi PT' AS label,s.start_time,CAST(NULL AS varchar(15)) AS booking_status
   FROM dbo.pt_session t JOIN dbo.[session] s ON s.session_id=t.session_id WHERE t.person_id=@id
   UNION ALL
   SELECT 'GROUP',g.session_id,g.class_name,s.start_time,b.booking_status
   FROM dbo.booking b JOIN dbo.group_class_session g ON g.session_id=b.session_id
   JOIN dbo.[session] s ON s.session_id=g.session_id WHERE b.person_id=@id
   ORDER BY start_time DESC,session_id DESC OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
 END
 ELSE IF @action='benefits'
   SELECT m.membership_id,s.service_name,i.quota_per_cycle,u.used
   FROM dbo.membership m JOIN dbo.plan_inclusion i ON i.plan_id=m.plan_id
   JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
   CROSS APPLY (SELECT COUNT_BIG(*) AS used FROM dbo.member_service_usage x WHERE x.membership_id=m.membership_id
      AND x.service_type_id=i.service_type_id AND x.usage_status='USED') u
   WHERE m.person_id=@id AND (@search IS NULL AND m.status='ACTIVE' AND @today BETWEEN m.start_date AND m.end_date
     OR m.membership_id=TRY_CONVERT(int,@search)) ORDER BY s.service_name;
 ELSE IF @action='save'
 BEGIN
   IF EXISTS(SELECT 1 FROM dbo.staff WITH (HOLDLOCK) WHERE person_id=@id)
      OR EXISTS(SELECT 1 FROM dbo.trainer WITH (HOLDLOCK) WHERE person_id=@id)
     EXEC dbo.local04_staff_guard @actor,1;
   IF NULLIF(TRIM(@name),N'') IS NULL OR @email IS NULL OR @email NOT LIKE '%_@_%._%'
     OR @phone IS NULL OR @emergency IS NULL OR REPLACE(@phone,'+','')=REPLACE(@emergency,'+','')
     OR LEN(REPLACE(@phone,'+','')) NOT BETWEEN 9 AND 14 OR LEN(REPLACE(@emergency,'+','')) NOT BETWEEN 9 AND 14
     OR REPLACE(@phone,'+','') LIKE '%[^0-9]%' OR REPLACE(@emergency,'+','') LIKE '%[^0-9]%'
     THROW 52302,'Invalid member contact',1;
   -- Take the member lock first, as in the contract and scheduling procedures.
   DECLARE @locked int,@current varchar(64);
   SELECT @locked=person_id FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@id;
   SELECT @current=CONVERT(varchar(64),HASHBYTES('SHA2_256',(SELECT p.full_name,p.email,p.phone,p.address,
      m.emergency_contact_phone FOR JSON PATH,WITHOUT_ARRAY_WRAPPER,INCLUDE_NULL_VALUES)),2)
   FROM dbo.person p WITH (UPDLOCK,HOLDLOCK) JOIN dbo.member m ON m.person_id=p.person_id WHERE p.person_id=@locked;
   IF @revision IS NULL OR @revision<>@current THROW 52304,'Member profile changed',1;
   BEGIN TRY
     UPDATE dbo.person SET full_name=TRIM(@name),email=LOWER(TRIM(@email)),phone=@phone,address=@address WHERE person_id=@id;
     UPDATE dbo.member SET emergency_contact_phone=@emergency WHERE person_id=@id;
     COMMIT TRANSACTION;
   END TRY
   BEGIN CATCH
     IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
     IF ERROR_NUMBER() IN (2601,2627) THROW 52305,'Duplicate contact',1;
     THROW;
   END CATCH;
   SELECT @id AS person_id;
 END
 ELSE THROW 52302,'Unknown member operation',1;
END;
GO

CREATE PROCEDURE dbo.local04_catalog
 @actor int,@action varchar(20),@id int=NULL,@service int=NULL,@name nvarchar(100)=NULL,
 @months int=NULL,@price decimal(12,2)=NULL,@description nvarchar(500)=NULL,@quota int=NULL,
 @for_sale bit=NULL,@offset int=0
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 IF @action IN ('save','sale','service','quota') BEGIN TRANSACTION;
 EXEC dbo.local04_staff_guard @actor,1;
 IF @action='list'
 BEGIN
   SELECT p.plan_id,p.plan_name,p.duration_months,p.base_price,p.description,p.is_for_sale
   FROM dbo.membership_plan p WHERE @name IS NULL OR CHARINDEX(@name,p.plan_name)>0
   ORDER BY p.plan_name,p.plan_id OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
   RETURN;
 END;
 IF @action='detail'
 BEGIN
   SELECT p.plan_id,p.plan_name,p.duration_months,p.base_price,p.description,p.is_for_sale,
     CONVERT(bit,CASE WHEN EXISTS(SELECT 1 FROM dbo.membership m WHERE m.plan_id=p.plan_id) THEN 1 ELSE 0 END) AS referenced
   FROM dbo.membership_plan p WHERE p.plan_id=@id;
   RETURN;
 END;
 IF @action='services'
 BEGIN
   SELECT service_type_id,service_name,description FROM dbo.service_type ORDER BY service_name,service_type_id;
   RETURN;
 END;
 IF @action='inclusions'
 BEGIN
   SELECT s.service_type_id,s.service_name,i.quota_per_cycle FROM dbo.plan_inclusion i
   JOIN dbo.service_type s ON s.service_type_id=i.service_type_id WHERE i.plan_id=@id ORDER BY s.service_name;
   RETURN;
 END;
 IF @action IS NULL OR @action NOT IN ('save','sale','service','quota') THROW 52302,'Unknown catalog operation',1;
 BEGIN TRY
   DECLARE @old_months int,@old_name nvarchar(100);
   IF @id IS NOT NULL AND @action<>'service'
   BEGIN
     -- The purchase procedure holds a shared lock on this same plan until its INSERT commits.
     SELECT @old_months=duration_months,@old_name=plan_name FROM dbo.membership_plan WITH (XLOCK,HOLDLOCK) WHERE plan_id=@id;
     IF @old_months IS NULL THROW 52303,'Plan not found',1;
   END;
   IF @action='service'
   BEGIN
     IF NULLIF(TRIM(@name),N'') IS NULL THROW 52302,'Invalid service name',1;
     INSERT dbo.service_type(service_name,description) VALUES(TRIM(@name),@description);
     SET @id=CONVERT(int,SCOPE_IDENTITY());
   END
   ELSE IF @action='sale'
   BEGIN
     IF @id IS NULL OR @for_sale IS NULL THROW 52302,'Invalid availability',1;
     UPDATE dbo.membership_plan SET is_for_sale=@for_sale WHERE plan_id=@id;
   END
   ELSE IF @action='save'
   BEGIN
     IF NULLIF(TRIM(@name),N'') IS NULL OR @months IS NULL OR @months NOT BETWEEN 1 AND 1200
        OR @price IS NULL OR @price<0 THROW 52302,'Invalid plan details',1;
     IF @id IS NULL
     BEGIN
       INSERT dbo.membership_plan(plan_name,duration_months,base_price,description,is_for_sale)
       VALUES(TRIM(@name),@months,@price,@description,0);
       SET @id=CONVERT(int,SCOPE_IDENTITY());
     END
     ELSE
     BEGIN
       IF (@months<>@old_months OR TRIM(@name) COLLATE Latin1_General_100_BIN2<>@old_name COLLATE Latin1_General_100_BIN2)
          AND EXISTS(SELECT 1 FROM dbo.membership WHERE plan_id=@id)
         THROW 52307,'Referenced plan identity and term are immutable',1;
       UPDATE dbo.membership_plan SET plan_name=TRIM(@name),duration_months=@months,base_price=@price,
         description=@description WHERE plan_id=@id;
     END;
   END
   ELSE
   BEGIN
     IF @id IS NULL OR @quota IS NULL OR @quota<-1 OR NOT EXISTS(SELECT 1 FROM dbo.service_type WHERE service_type_id=@service)
       THROW 52302,'Invalid service quota',1;
     IF EXISTS(SELECT 1 FROM dbo.membership WHERE plan_id=@id) THROW 52307,'Referenced plan entitlements are immutable',1;
     UPDATE dbo.plan_inclusion SET quota_per_cycle=@quota WHERE plan_id=@id AND service_type_id=@service;
     IF @@ROWCOUNT=0 INSERT dbo.plan_inclusion(plan_id,service_type_id,quota_per_cycle) VALUES(@id,@service,@quota);
   END;
   COMMIT TRANSACTION;
 END TRY
 BEGIN CATCH
   IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
   IF ERROR_NUMBER() IN (2601,2627) THROW 52305,'Duplicate catalog name',1;
   THROW;
 END CATCH;
 SELECT @id AS record_id;
END;
GO

CREATE PROCEDURE dbo.local04_classes
 @actor int,@action varchar(15),@id int=NULL,@trainer int=NULL,@room int=NULL,
 @start datetime2(0)=NULL,@end datetime2(0)=NULL,@name nvarchar(100)=NULL,
 @category nvarchar(50)=NULL,@capacity int=NULL
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 IF @action='save' BEGIN TRANSACTION;
 EXEC dbo.local04_staff_guard @actor,1;
 IF @action='detail'
 BEGIN
   SELECT g.session_id,g.class_name,g.category,g.max_capacity,s.trainer_id,s.room_id,s.start_time,s.end_time,
     p.full_name,r.room_name,g.current_enrollment,CONVERT(bit,CASE WHEN EXISTS(SELECT 1 FROM dbo.booking b
       WHERE b.session_id=g.session_id) THEN 1 ELSE 0 END) AS has_history
   FROM dbo.vw_group_class_enrollment g JOIN dbo.[session] s ON s.session_id=g.session_id
   JOIN dbo.person p ON p.person_id=s.trainer_id JOIN dbo.room r ON r.room_id=s.room_id WHERE g.session_id=@id;
   RETURN;
 END;
 IF @action IS NULL OR @action<>'save' THROW 52302,'Unknown class operation',1;
 DECLARE @old_capacity int,@old_trainer int,@old_room int,@old_start datetime2(0),@old_end datetime2(0),
   @old_name nvarchar(100),@old_category nvarchar(50);
 SELECT @old_capacity=max_capacity,@old_name=class_name,@old_category=category
 FROM dbo.group_class_session WITH (UPDLOCK,HOLDLOCK) WHERE session_id=@id;
 IF @old_capacity IS NULL THROW 52303,'Group class not found',1;
 SELECT @old_trainer=trainer_id,@old_room=room_id,@old_start=start_time,@old_end=end_time
 FROM dbo.[session] WHERE session_id=@id;
 IF @old_start<=SYSDATETIME() THROW 52205,'Class already started',1;
 IF @capacity IS NULL OR @capacity<=0 OR @trainer IS NULL OR @room IS NULL OR @start IS NULL OR @end IS NULL
    OR NULLIF(TRIM(@name),N'') IS NULL OR NULLIF(TRIM(@category),N'') IS NULL THROW 52302,'Invalid class data',1;
 IF @capacity<(SELECT COUNT(*) FROM dbo.booking WHERE session_id=@id AND booking_status='SUCCESS')
   THROW 52308,'Capacity below confirmed enrollment',1;
 IF @trainer<>@old_trainer OR @room<>@old_room OR @start<>@old_start OR @end<>@old_end
    OR @name<>@old_name OR @category<>@old_category
 BEGIN
   IF EXISTS(SELECT 1 FROM dbo.booking WHERE session_id=@id) THROW 52309,'Class has booking history',1;
   IF @trainer<>@old_trainer OR @room<>@old_room OR @start<>@old_start OR @end<>@old_end
   BEGIN
     EXEC dbo.local03_lock_slot @trainer,@room,@start,@end;
     UPDATE dbo.[session] SET trainer_id=@trainer,room_id=@room,start_time=@start,end_time=@end WHERE session_id=@id;
   END;
 END;
 UPDATE dbo.group_class_session SET max_capacity=@capacity,class_name=TRIM(@name),category=TRIM(@category)
 WHERE session_id=@id;
 COMMIT TRANSACTION;
 SELECT @id AS session_id;
END;
GO

CREATE PROCEDURE dbo.local04_assets
 @actor int,@action varchar(20),@id int=NULL,@room int=NULL,@name nvarchar(100)=NULL,
 @type varchar(30)=NULL,@serial varchar(50)=NULL,@status varchar(20)=NULL,@on_date date=NULL,
 @description nvarchar(500)=NULL,@cost decimal(12,2)=NULL,@ticket int=NULL,@offset int=0
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 DECLARE @write bit=CASE WHEN @action IN ('room_add','room_status','equipment_add','equipment_save','open','close') THEN 1 ELSE 0 END;
 DECLARE @manager bit=CASE WHEN @action IN ('room_add','equipment_add') THEN 1 ELSE 0 END;
 IF @write=1 BEGIN TRANSACTION;
 EXEC dbo.local04_staff_guard @actor,@manager;
 IF @action='rooms'
 BEGIN
   SELECT room_id,room_name,room_type,status FROM dbo.room ORDER BY room_name,room_id;
   RETURN;
 END;
 IF @action IN ('equipment','detail')
 BEGIN
   SELECT e.equipment_id,e.equipment_name,e.serial_number,e.room_id,r.room_name,e.status,
     (SELECT MIN(maintenance_id) FROM dbo.equipment_maintenance_log l WHERE l.equipment_id=e.equipment_id AND l.end_date IS NULL) AS open_ticket
   FROM dbo.equipment e LEFT JOIN dbo.room r ON r.room_id=e.room_id
   WHERE (@id IS NULL OR e.equipment_id=@id) AND (@status IS NULL OR e.status=@status)
     AND (@name IS NULL OR CHARINDEX(@name,e.equipment_name)>0 OR CHARINDEX(@name,e.serial_number)>0)
   ORDER BY e.equipment_id DESC OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
   RETURN;
 END;
 IF @action='logs'
 BEGIN
   SELECT maintenance_id,start_date,end_date,cost,description FROM dbo.equipment_maintenance_log
   WHERE equipment_id=@id ORDER BY maintenance_id DESC OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
   RETURN;
 END;
 IF @write=0 THROW 52302,'Unknown asset operation',1;
 DECLARE @old_status varchar(20),@opened int,@today date=CONVERT(date,SYSDATETIME());
 BEGIN TRY
   IF @action='room_add'
   BEGIN
     IF NULLIF(TRIM(@name),N'') IS NULL OR NULLIF(TRIM(@type),'') IS NULL THROW 52302,'Invalid room details',1;
     INSERT dbo.room(room_name,room_type) VALUES(TRIM(@name),TRIM(@type));
     SET @id=CONVERT(int,SCOPE_IDENTITY());
   END
   ELSE IF @action='room_status'
   BEGIN
     IF @status IS NULL OR @status NOT IN ('AVAILABLE','MAINTENANCE') THROW 52302,'Invalid room state',1;
     UPDATE dbo.room SET status=@status WHERE room_id=@id;
     IF @@ROWCOUNT<>1 THROW 52303,'Room not found',1;
   END
   ELSE IF @action='equipment_add'
   BEGIN
     IF NULLIF(TRIM(@name),N'') IS NULL OR NULLIF(TRIM(@serial),'') IS NULL THROW 52302,'Invalid equipment',1;
     IF @room IS NOT NULL AND NOT EXISTS(SELECT 1 FROM dbo.room WHERE room_id=@room) THROW 52303,'Room not found',1;
     INSERT dbo.equipment(equipment_name,serial_number,room_id) VALUES(TRIM(@name),TRIM(@serial),@room);
     SET @id=CONVERT(int,SCOPE_IDENTITY());
   END
   ELSE
   BEGIN
     SELECT @old_status=status FROM dbo.equipment WITH (UPDLOCK,HOLDLOCK) WHERE equipment_id=@id;
     IF @old_status IS NULL THROW 52303,'Equipment not found',1;
     SELECT @opened=MIN(maintenance_id) FROM dbo.equipment_maintenance_log
       WHERE equipment_id=@id AND end_date IS NULL;
     IF @action='equipment_save'
     BEGIN
       IF @status IS NULL OR @status NOT IN ('ACTIVE','MAINTENANCE','RETIRED')
         OR (@opened IS NOT NULL AND @status<>'MAINTENANCE') OR (@old_status='RETIRED' AND @status<>'RETIRED')
         THROW 52310,'Equipment state conflicts with maintenance',1;
       IF @room IS NOT NULL AND NOT EXISTS(SELECT 1 FROM dbo.room WHERE room_id=@room) THROW 52303,'Room not found',1;
       UPDATE dbo.equipment SET room_id=@room,status=@status WHERE equipment_id=@id;
     END
     ELSE IF @action='open'
     BEGIN
       IF @opened IS NOT NULL OR @old_status='RETIRED' THROW 52310,'Maintenance already open or equipment retired',1;
       IF @on_date IS NULL OR @on_date>@today OR NULLIF(TRIM(@description),N'') IS NULL THROW 52302,'Invalid maintenance start',1;
       INSERT dbo.equipment_maintenance_log(equipment_id,start_date,description) VALUES(@id,@on_date,@description);
       UPDATE dbo.equipment SET status='MAINTENANCE' WHERE equipment_id=@id;
     END
     ELSE
     BEGIN
       IF @ticket IS NULL OR @opened IS NULL OR @ticket<>@opened OR @old_status<>'MAINTENANCE'
          THROW 52310,'Maintenance no longer open',1;
       IF @status IS NULL OR @status NOT IN ('ACTIVE','RETIRED') OR @cost IS NULL OR @cost<0
          OR @on_date IS NULL OR @on_date>@today OR NULLIF(TRIM(@description),N'') IS NULL
          THROW 52302,'Invalid maintenance completion',1;
       UPDATE dbo.equipment_maintenance_log SET end_date=@on_date,cost=@cost,description=@description
       WHERE maintenance_id=@ticket AND equipment_id=@id AND end_date IS NULL AND start_date<=@on_date;
       IF @@ROWCOUNT<>1 THROW 52302,'Maintenance end precedes start',1;
       UPDATE dbo.equipment SET status=@status WHERE equipment_id=@id;
     END;
   END;
   COMMIT TRANSACTION;
 END TRY
 BEGIN CATCH
   IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
   IF ERROR_NUMBER() IN (2601,2627) THROW 52305,'Duplicate room or equipment serial',1;
   THROW;
 END CATCH;
 SELECT @id AS record_id;
END;
GO

CREATE PROCEDURE dbo.local04_personnel
 @actor int,@action varchar(20),@id int=NULL,@role varchar(10)=NULL,@status varchar(20)=NULL,@offset int=0,
 @name nvarchar(100)=NULL,@email varchar(255)=NULL,@phone varchar(15)=NULL,@address nvarchar(255)=NULL,
 @ssn varchar(12)=NULL,@birth date=NULL,@gender varchar(10)=NULL,@hash varchar(255)=NULL,
 @hire date=NULL,@position nvarchar(50)=NULL,@certificate nvarchar(100)=NULL
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 DECLARE @write bit=CASE WHEN @action IN ('create','assign','save','cert_add','cert_remove') THEN 1 ELSE 0 END;
 DECLARE @own_certificate bit=CASE WHEN @action IN ('certs','cert_add','cert_remove') AND @id=@actor THEN 1 ELSE 0 END;
 IF @write=1 BEGIN TRANSACTION;
 IF @write=1 AND @own_certificate=0
 BEGIN
   DECLARE @lock_result int;
   EXEC @lock_result=sys.sp_getapplock @Resource='local04-personnel',@LockMode='Exclusive',@LockTimeout=4000;
   IF @lock_result<0 THROW 52304,'Personnel management busy',1;
 END;
 IF @own_certificate=1
 BEGIN
   IF NOT EXISTS(SELECT 1 FROM dbo.trainer WITH (HOLDLOCK) WHERE person_id=@actor
      AND employment_status IN ('ACTIVE','ON_LEAVE')) THROW 52301,'Trainer required',1;
 END
 ELSE EXEC dbo.local04_staff_guard @actor,1;

 IF @action='list'
 BEGIN
   SELECT p.person_id,p.full_name,p.email,r.role_code,r.position,r.hire_date,r.employment_status
   FROM dbo.person p JOIN (
     SELECT person_id,'staff' AS role_code,position,hire_date,employment_status FROM dbo.staff
     UNION ALL SELECT person_id,'trainer',NULL,hire_date,employment_status FROM dbo.trainer
   ) r ON r.person_id=p.person_id
   WHERE (@role IS NULL OR r.role_code=@role) AND (@status IS NULL OR r.employment_status=@status)
     AND (@name IS NULL OR CHARINDEX(@name,p.full_name)>0 OR CHARINDEX(@name,p.email)>0
       OR CHARINDEX(@name,p.phone)>0)
   ORDER BY p.person_id DESC,r.role_code OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
   RETURN;
 END;
 IF @action='detail'
 BEGIN
   SELECT p.person_id,p.full_name,p.email,p.phone,p.address,r.position,r.hire_date,r.employment_status
   FROM dbo.person p JOIN (
     SELECT person_id,'staff' AS role_code,position,hire_date,employment_status FROM dbo.staff
     UNION ALL SELECT person_id,'trainer',NULL,hire_date,employment_status FROM dbo.trainer
   ) r ON r.person_id=p.person_id WHERE p.person_id=@id AND r.role_code=@role;
   RETURN;
 END;
 IF @action='certs'
 BEGIN
   SELECT t.hire_date,t.employment_status,c.certification FROM dbo.trainer t
   LEFT JOIN dbo.trainer_certification c ON c.person_id=t.person_id
   WHERE t.person_id=@id ORDER BY c.certification;
   RETURN;
 END;
 IF @action='schedule'
 BEGIN
   SELECT s.session_id,s.session_type,s.start_time,s.end_time,r.room_name,g.class_name
   FROM dbo.[session] s JOIN dbo.room r ON r.room_id=s.room_id
   LEFT JOIN dbo.group_class_session g ON g.session_id=s.session_id
   WHERE s.trainer_id=@id ORDER BY s.start_time DESC,s.session_id DESC
   OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
   RETURN;
 END;
 IF @write=0 THROW 52302,'Unknown personnel operation',1;
 IF @action NOT IN ('cert_add','cert_remove') AND @id=@actor THROW 52301,'Cannot change own role',1;
 BEGIN TRY
   IF @action IN ('cert_add','cert_remove')
   BEGIN
     IF NULLIF(TRIM(@certificate),N'') IS NULL THROW 52302,'Invalid certification',1;
     IF NOT EXISTS(SELECT 1 FROM dbo.trainer WHERE person_id=@id) THROW 52303,'Trainer not found',1;
     IF @action='cert_add' INSERT dbo.trainer_certification(person_id,certification) VALUES(@id,TRIM(@certificate));
     ELSE DELETE dbo.trainer_certification WHERE person_id=@id AND certification=@certificate;
   END
   ELSE
   BEGIN
     IF @role IS NULL OR @role NOT IN ('staff','trainer') OR (@role='staff' AND NULLIF(TRIM(@position),N'') IS NULL)
       THROW 52302,'Invalid employment role or position',1;
     IF @action IN ('create','assign')
     BEGIN
       IF @hire IS NULL THROW 52302,'Invalid hire date',1;
       IF @action='create'
       BEGIN
         IF @id IS NOT NULL OR NULLIF(TRIM(@name),N'') IS NULL OR @birth IS NULL
           OR @birth>CONVERT(date,SYSDATETIME()) OR @hire<@birth OR @hash NOT LIKE '$argon2id$%' OR @hash IS NULL
           OR @email IS NULL OR @email NOT LIKE '%_@_%._%' OR @phone IS NULL
           OR LEN(REPLACE(@phone,'+','')) NOT BETWEEN 9 AND 14 OR REPLACE(@phone,'+','') LIKE '%[^0-9]%'
           OR @ssn IS NULL OR LEN(@ssn)<>12 OR @ssn LIKE '%[^0-9]%'
           OR @gender IS NULL OR @gender NOT IN ('MALE','FEMALE','OTHER') THROW 52302,'Invalid personnel account',1;
         INSERT dbo.person(full_name,email,phone,address,ssn,date_of_birth,gender,password_hash)
         VALUES(TRIM(@name),LOWER(TRIM(@email)),@phone,@address,@ssn,@birth,@gender,@hash);
         SET @id=CONVERT(int,SCOPE_IDENTITY());
       END
       ELSE IF NOT EXISTS(SELECT 1 FROM dbo.person WHERE person_id=@id AND date_of_birth<=@hire)
         THROW 52303,'Person or valid hire date not found',1;
       IF @role='staff' INSERT dbo.staff(person_id,position,hire_date) VALUES(@id,TRIM(@position),@hire);
       ELSE INSERT dbo.trainer(person_id,hire_date) VALUES(@id,@hire);
     END
     ELSE
     BEGIN
       IF @status IS NULL OR @status NOT IN ('ACTIVE','ON_LEAVE','TERMINATED')
         OR NULLIF(TRIM(@name),N'') IS NULL OR @email IS NULL OR @email NOT LIKE '%_@_%._%' OR @phone IS NULL
         OR LEN(REPLACE(@phone,'+','')) NOT BETWEEN 9 AND 14 OR REPLACE(@phone,'+','') LIKE '%[^0-9]%'
         THROW 52302,'Invalid personnel details',1;
       IF @role='trainer'
       BEGIN
         IF NOT EXISTS(SELECT 1 FROM dbo.trainer WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@id)
           THROW 52303,'Trainer not found',1;
         IF @status<>'ACTIVE' AND EXISTS(SELECT 1 FROM dbo.[session] WHERE trainer_id=@id AND end_time>SYSDATETIME())
           THROW 52306,'Trainer has scheduled sessions',1;
         UPDATE dbo.trainer SET employment_status=@status WHERE person_id=@id;
       END
       ELSE
       BEGIN
         UPDATE dbo.staff SET position=TRIM(@position),employment_status=@status WHERE person_id=@id;
         IF @@ROWCOUNT<>1 THROW 52303,'Staff not found',1;
       END;
       IF EXISTS(SELECT 1 FROM dbo.member WHERE person_id=@id AND
         REPLACE(emergency_contact_phone,'+','')=REPLACE(@phone,'+','')) THROW 52302,'Conflicting emergency contact',1;
       UPDATE dbo.person SET full_name=TRIM(@name),email=LOWER(TRIM(@email)),phone=@phone,address=@address WHERE person_id=@id;
     END;
   END;
   COMMIT TRANSACTION;
 END TRY
 BEGIN CATCH
   IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
   IF ERROR_NUMBER() IN (2601,2627) THROW 52305,'Duplicate account, role, or certification',1;
   THROW;
 END CATCH;
 SELECT @id AS person_id;
END;
GO

CREATE PROCEDURE dbo.local04_transactions
 @actor int,@kind varchar(15),@from date=NULL,@to date=NULL,@search nvarchar(100)=NULL,
 @status varchar(25)=NULL,@method varchar(20)=NULL,@offset int=0,@id int=NULL
AS
BEGIN
 SET NOCOUNT ON;
 EXEC dbo.local04_staff_guard @actor;
 IF @to='9999-12-31' OR @from>@to THROW 52302,'Invalid date range',1;
 IF @kind IS NULL OR @kind NOT IN ('contracts','payments','receipt') THROW 52302,'Unknown transaction operation',1;
 DECLARE @upper date=DATEADD(day,1,@to);
 SELECT m.membership_id,m.person_id,p.full_name,p.email,l.plan_name,m.status,m.start_date,m.end_date,
     m.total_price,l.base_price,t.payment_id,t.amount,t.payment_method,t.payment_time,m.plan_id,
     m.created_at,employee.full_name AS recorded_by
 FROM dbo.membership m JOIN dbo.person p ON p.person_id=m.person_id
 JOIN dbo.membership_plan l ON l.plan_id=m.plan_id
 LEFT JOIN dbo.payment t ON t.membership_id=m.membership_id
 LEFT JOIN dbo.person employee ON employee.person_id=t.recorded_by
 WHERE (@kind='contracts' OR (t.payment_id IS NOT NULL AND m.status IN ('PENDING_ACTIVATION','ACTIVE','EXPIRED')
          AND m.total_price=t.amount)) AND (@id IS NULL OR m.membership_id=@id)
   AND (@status IS NULL OR m.status=@status) AND (@method IS NULL OR t.payment_method=@method)
   AND (@from IS NULL OR (@kind='contracts' AND m.created_at>=@from) OR (@kind<>'contracts' AND t.payment_time>=@from))
   AND (@upper IS NULL OR (@kind='contracts' AND m.created_at<@upper) OR (@kind<>'contracts' AND t.payment_time<@upper))
   AND (@search IS NULL OR CHARINDEX(@search,p.full_name)>0 OR CHARINDEX(@search,p.email)>0 OR CHARINDEX(@search,l.plan_name)>0
      OR p.phone=@search OR m.membership_id=TRY_CONVERT(int,@search) OR t.payment_id=TRY_CONVERT(int,@search))
 ORDER BY CASE WHEN @kind='contracts' THEN m.created_at ELSE t.payment_time END DESC,m.membership_id DESC
 OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
END;
GO

CREATE PROCEDURE dbo.local04_dashboard @actor int,@from date,@to date
AS
BEGIN
 SET NOCOUNT ON;
 EXEC dbo.local04_staff_guard @actor,1;
 IF @from IS NULL OR @to IS NULL OR @from>@to OR @to='9999-12-31' THROW 52302,'Invalid reporting dates',1;
 DECLARE @upper date=DATEADD(day,1,@to),@today date=CONVERT(date,SYSDATETIME());
 DECLARE @valid_payments TABLE (payment_time datetime2(0),payment_method varchar(20),amount decimal(12,2));
 INSERT @valid_payments
 SELECT p.payment_time,p.payment_method,p.amount FROM dbo.payment p
 JOIN dbo.membership m ON m.membership_id=p.membership_id AND m.total_price=p.amount
 WHERE p.payment_time>=@from AND p.payment_time<@upper AND m.status IN ('PENDING_ACTIVATION','ACTIVE','EXPIRED');

 SELECT 'members_all' AS metric,CAST(N'' AS nvarchar(30)) AS segment,COUNT_BIG(*) AS quantity,
    CAST(NULL AS decimal(38,2)) AS amount FROM dbo.member
 UNION ALL SELECT 'members_new',N'',COUNT_BIG(*),NULL FROM dbo.member WHERE join_date>=@from AND join_date<@upper
 UNION ALL SELECT 'members_active',N'',COUNT_BIG(*),NULL FROM dbo.member u WHERE EXISTS(
    SELECT 1 FROM dbo.membership m WHERE m.person_id=u.person_id AND m.status='ACTIVE' AND @today BETWEEN m.start_date AND m.end_date)
 UNION ALL SELECT 'members_expired',N'',COUNT_BIG(*),NULL FROM dbo.member u WHERE EXISTS(
    SELECT 1 FROM dbo.membership m WHERE m.person_id=u.person_id AND (m.status='EXPIRED' OR m.status='ACTIVE' AND m.end_date<@today))
   AND NOT EXISTS(SELECT 1 FROM dbo.membership m WHERE m.person_id=u.person_id AND m.status='ACTIVE'
       AND @today BETWEEN m.start_date AND m.end_date)
 UNION ALL SELECT 'plans_active',N'',COUNT_BIG(*),NULL FROM dbo.membership
    WHERE status='ACTIVE' AND @today BETWEEN start_date AND end_date
 UNION ALL SELECT 'plans_expired',N'',COUNT_BIG(*),NULL FROM dbo.membership WHERE status='EXPIRED' OR status='ACTIVE' AND end_date<@today
 UNION ALL SELECT 'contracts',N'',COUNT_BIG(*),SUM(total_price) FROM dbo.membership WHERE created_at>=@from AND created_at<@upper
 UNION ALL SELECT 'contract_status',status,COUNT_BIG(*),SUM(total_price) FROM dbo.membership
    WHERE created_at>=@from AND created_at<@upper GROUP BY status
 UNION ALL SELECT 'receipts',N'',COUNT_BIG(*),SUM(amount) FROM @valid_payments
 UNION ALL SELECT 'receipt_method',payment_method,COUNT_BIG(*),SUM(amount) FROM @valid_payments GROUP BY payment_method
 UNION ALL SELECT 'receipt_month',CONVERT(char(7),payment_time,120),COUNT_BIG(*),SUM(amount) FROM @valid_payments
    GROUP BY CONVERT(char(7),payment_time,120)
 UNION ALL SELECT 'pt',N'',COUNT_BIG(*),NULL FROM dbo.pt_session p JOIN dbo.[session] s ON s.session_id=p.session_id
    WHERE s.start_time>=@from AND s.start_time<@upper
 UNION ALL SELECT 'classes',N'',COUNT_BIG(*),SUM(CONVERT(bigint,max_capacity)) FROM dbo.vw_group_class_enrollment
    WHERE start_time>=@from AND start_time<@upper
 UNION ALL SELECT 'seats',N'',COALESCE(SUM(CONVERT(bigint,current_enrollment)),0),NULL FROM dbo.vw_group_class_enrollment
    WHERE start_time>=@from AND start_time<@upper
 UNION ALL SELECT 'booked',N'',COUNT_BIG(*),NULL FROM dbo.booking
    WHERE booked_at>=@from AND booked_at<@upper
 UNION ALL SELECT 'cancelled',N'',COUNT_BIG(*),NULL FROM dbo.booking
    WHERE booking_status='CANCEL' AND cancelled_at>=@from AND cancelled_at<@upper
 UNION ALL SELECT 'equipment',status,COUNT_BIG(*),NULL FROM dbo.equipment GROUP BY status
 UNION ALL SELECT 'maintenance_open',N'',COUNT_BIG(*),NULL FROM dbo.equipment_maintenance_log WHERE end_date IS NULL
 UNION ALL SELECT 'maintenance_cost',N'',COUNT_BIG(*),SUM(cost) FROM dbo.equipment_maintenance_log
    WHERE end_date>=@from AND end_date<@upper;
END;
GO

CREATE PROCEDURE dbo.local04_services
 @actor int,@action varchar(15),@member int,@service int=NULL
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 SET LOCK_TIMEOUT 5000;
 IF @action='use' BEGIN TRANSACTION;
 EXEC dbo.local04_staff_guard @actor;
 DECLARE @contract int,@plan int,@quota int,@today date=CONVERT(date,SYSDATETIME());
 IF @action='use'
 BEGIN
   IF NOT EXISTS(SELECT 1 FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@member)
     THROW 52303,'Member not found',1;
 END;
 SELECT @contract=membership_id,@plan=plan_id FROM dbo.membership
 WHERE person_id=@member AND status='ACTIVE' AND @today BETWEEN start_date AND end_date;
 IF @action='list'
 BEGIN
   SELECT s.service_type_id,s.service_name,i.quota_per_cycle,u.used
   FROM dbo.plan_inclusion i JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
   CROSS APPLY (SELECT COUNT_BIG(*) AS used FROM dbo.member_service_usage
     WHERE membership_id=@contract AND service_type_id=i.service_type_id AND usage_status='USED') u
   WHERE i.plan_id=@plan AND s.service_name NOT IN (N'PT cá nhân',N'Local-02 · Buổi PT',N'Lớp nhóm')
   ORDER BY s.service_name;
   RETURN;
 END;
 IF @action IS NULL OR @action<>'use' THROW 52302,'Unknown service operation',1;
 IF @contract IS NULL THROW 52202,'Active membership required',1;
 SELECT @quota=i.quota_per_cycle FROM dbo.plan_inclusion i JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
 WHERE i.plan_id=@plan AND i.service_type_id=@service AND s.service_name NOT IN (N'PT cá nhân',N'Local-02 · Buổi PT',N'Lớp nhóm');
 IF @quota IS NULL THROW 52203,'Invalid incidental service',1;
 IF @quota<>-1 AND (SELECT COUNT_BIG(*) FROM dbo.member_service_usage WHERE membership_id=@contract
    AND service_type_id=@service AND usage_status='USED')>=@quota THROW 52204,'Quota exhausted',1;
 INSERT dbo.member_service_usage(membership_id,service_type_id) VALUES(@contract,@service);
 DECLARE @usage int=CONVERT(int,SCOPE_IDENTITY());
 COMMIT TRANSACTION;
 SELECT @usage AS usage_id;
END;
GO

ALTER PROCEDURE dbo.local02_catalog @plan_id int=NULL
AS
BEGIN
 SET NOCOUNT ON;
 SELECT p.plan_id,p.plan_name,p.duration_months,p.base_price,p.description,
        s.service_name,i.quota_per_cycle
 FROM dbo.membership_plan p LEFT JOIN dbo.plan_inclusion i ON i.plan_id=p.plan_id
 LEFT JOIN dbo.service_type s ON s.service_type_id=i.service_type_id
 WHERE p.is_for_sale=1 AND (@plan_id IS NULL OR p.plan_id=@plan_id)
 ORDER BY p.plan_name,p.plan_id,s.service_name;
END;
GO

ALTER PROCEDURE dbo.local02_create_contract @actor int,@plan_id int,@expected_price decimal(12,2),
 @request_id uniqueidentifier
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 DECLARE @member_lock int,@contract int,@existing_actor int,@existing_plan int,@price decimal(12,2);
 SELECT @member_lock=person_id FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@actor;
 IF @member_lock IS NULL THROW 52101,'Member required',1;
 IF @request_id IS NULL THROW 52107,'Invalid request identifier',1;
 SELECT @contract=membership_id,@existing_actor=person_id,@existing_plan=plan_id
 FROM dbo.membership WHERE local02_request_id=@request_id;
 IF @contract IS NOT NULL
 BEGIN
   IF @existing_actor<>@actor OR @existing_plan<>@plan_id THROW 52107,'Request identifier conflict',1;
   COMMIT TRANSACTION;
   SELECT @contract AS membership_id;
   RETURN;
 END;
 SELECT @price=base_price FROM dbo.membership_plan WITH (HOLDLOCK) WHERE plan_id=@plan_id AND is_for_sale=1;
 IF @price IS NULL THROW 52103,'Plan not available',1;
 IF @expected_price IS NULL OR @expected_price<>@price THROW 52104,'Price confirmation required',1;
 BEGIN TRY
   INSERT dbo.membership(person_id,plan_id,local02_request_id)
     VALUES(@actor,@plan_id,@request_id);
   SET @contract=CONVERT(int,SCOPE_IDENTITY());
   COMMIT TRANSACTION;
 END TRY
 BEGIN CATCH
   IF XACT_STATE()<>0 ROLLBACK TRANSACTION;
   IF ERROR_NUMBER() IN (2601,2627) THROW 52107,'Request identifier conflict',1;
   THROW;
 END CATCH;
 SELECT @contract AS membership_id;
END;
GO

ALTER PROCEDURE dbo.local02_collect_payment
 @actor int,@contract_id int,@expected_price decimal(12,2),@method varchar(20),@activate_now bit
AS
BEGIN
 SET NOCOUNT ON;
 SET XACT_ABORT ON;
 BEGIN TRANSACTION;
 IF NOT EXISTS (SELECT 1 FROM dbo.staff WITH (HOLDLOCK) WHERE person_id=@actor AND employment_status='ACTIVE')
   THROW 52101,'Active staff required',1;
 IF @method IS NULL OR @method NOT IN ('CASH','BANK_TRANSFER') OR @activate_now IS NULL
   THROW 52107,'Invalid payment details',1;
 DECLARE @member_id int,@locked int,@status varchar(25),@price decimal(12,2),@payment_id int;
 SELECT @member_id=person_id FROM dbo.membership WHERE membership_id=@contract_id;
 IF @member_id IS NULL THROW 52103,'Contract does not exist',1;
 SELECT @locked=person_id FROM dbo.member WITH (UPDLOCK,HOLDLOCK) WHERE person_id=@member_id;
 SELECT @status=m.status,@price=p.base_price FROM dbo.membership m WITH (UPDLOCK,HOLDLOCK)
 JOIN dbo.membership_plan p WITH (HOLDLOCK) ON p.plan_id=m.plan_id
 WHERE m.membership_id=@contract_id AND m.person_id=@locked;
 IF @status IS NULL OR @status<>'PENDING_PAYMENT'
    OR EXISTS (SELECT 1 FROM dbo.payment WHERE membership_id=@contract_id)
   THROW 52105,'Contract is not payable',1;
 IF @expected_price IS NULL OR @expected_price<>@price THROW 52104,'Price confirmation required',1;
 INSERT dbo.payment(membership_id,amount,payment_method,recorded_by) VALUES (@contract_id,@price,@method,@actor);
 SET @payment_id=CONVERT(int,SCOPE_IDENTITY());
 UPDATE dbo.membership SET total_price=@price,status='PENDING_ACTIVATION'
 WHERE membership_id=@contract_id AND status='PENDING_PAYMENT';
 IF @@ROWCOUNT<>1 THROW 52105,'Contract status changed',1;
 IF @activate_now=1 EXEC dbo.local02_activate_paid @contract_id,@locked;
 COMMIT TRANSACTION;
 SELECT @payment_id AS payment_id;
END;
GO

ALTER PROCEDURE dbo.local02_contracts
 @actor int,@staff_scope bit,@contract_id int=NULL,@member_id int=NULL,@status varchar(25)=NULL
AS
BEGIN
 SET NOCOUNT ON;
 IF @staff_scope=1
 BEGIN
   IF NOT EXISTS (SELECT 1 FROM dbo.staff WHERE person_id=@actor AND employment_status='ACTIVE')
     THROW 52101,'Staff required',1;
 END
 ELSE
 BEGIN
   IF NOT EXISTS (SELECT 1 FROM dbo.member WHERE person_id=@actor) THROW 52101,'Member required',1;
   SET @member_id=@actor;
 END;
 -- Tự đồng bộ trạng thái đã quá ngày cho các hợp đồng thuộc phạm vi đã xác thực.
 DECLARE @today date=CONVERT(date,SYSDATETIME());
 UPDATE dbo.membership SET status='EXPIRED'
 WHERE status='ACTIVE' AND end_date<@today AND (@member_id IS NULL OR person_id=@member_id)
   AND (@contract_id IS NULL OR membership_id=@contract_id);
 SELECT TOP (100) m.membership_id,m.person_id,p.full_name,l.plan_name,m.status,m.start_date,m.end_date,
     m.total_price,l.base_price,t.payment_id,t.amount,t.payment_method,t.payment_time,m.plan_id
 FROM dbo.membership m JOIN dbo.person p ON p.person_id=m.person_id
 JOIN dbo.membership_plan l ON l.plan_id=m.plan_id
 LEFT JOIN dbo.payment t ON t.membership_id=m.membership_id
 WHERE (@contract_id IS NULL OR m.membership_id=@contract_id)
 AND (@member_id IS NULL OR m.person_id=@member_id)
 AND (@status IS NULL OR m.status=@status)
 ORDER BY m.membership_id DESC;
END;
GO

ALTER PROCEDURE dbo.local04_transactions
 @actor int,@kind varchar(15),@from date=NULL,@to date=NULL,@search nvarchar(100)=NULL,
 @status varchar(25)=NULL,@method varchar(20)=NULL,@offset int=0,@id int=NULL
AS
BEGIN
 SET NOCOUNT ON;
 EXEC dbo.local04_staff_guard @actor;
 IF @to='9999-12-31' OR @from>@to THROW 52302,'Invalid date range',1;
 IF @kind IS NULL OR @kind NOT IN ('contracts','payments','receipt') THROW 52302,'Unknown transaction operation',1;
 DECLARE @upper date=DATEADD(day,1,@to),@today date=CONVERT(date,SYSDATETIME());
 UPDATE dbo.membership SET status='EXPIRED'
 WHERE status='ACTIVE' AND end_date<@today AND (@id IS NULL OR membership_id=@id);
 SELECT m.membership_id,m.person_id,p.full_name,p.email,l.plan_name,m.status,m.start_date,m.end_date,
     m.total_price,l.base_price,t.payment_id,t.amount,t.payment_method,t.payment_time,m.plan_id,
     m.created_at,employee.full_name AS recorded_by
 FROM dbo.membership m JOIN dbo.person p ON p.person_id=m.person_id
 JOIN dbo.membership_plan l ON l.plan_id=m.plan_id
 LEFT JOIN dbo.payment t ON t.membership_id=m.membership_id
 LEFT JOIN dbo.person employee ON employee.person_id=t.recorded_by
 WHERE (@kind='contracts' OR (t.payment_id IS NOT NULL AND m.status IN ('PENDING_ACTIVATION','ACTIVE','EXPIRED')
          AND m.total_price=t.amount)) AND (@id IS NULL OR m.membership_id=@id)
   AND (@status IS NULL OR m.status=@status) AND (@method IS NULL OR t.payment_method=@method)
   AND (@from IS NULL OR (@kind='contracts' AND m.created_at>=@from) OR (@kind<>'contracts' AND t.payment_time>=@from))
   AND (@upper IS NULL OR (@kind='contracts' AND m.created_at<@upper) OR (@kind<>'contracts' AND t.payment_time<@upper))
   AND (@search IS NULL OR CHARINDEX(@search,p.full_name)>0 OR CHARINDEX(@search,p.email)>0 OR CHARINDEX(@search,l.plan_name)>0
      OR p.phone=@search OR m.membership_id=TRY_CONVERT(int,@search) OR t.payment_id=TRY_CONVERT(int,@search))
 ORDER BY CASE WHEN @kind='contracts' THEN m.created_at ELSE t.payment_time END DESC,m.membership_id DESC
 OFFSET @offset ROWS FETCH NEXT 51 ROWS ONLY;
END;
GO

ALTER PROCEDURE dbo.local04_dashboard @actor int,@from date,@to date
AS
BEGIN
 SET NOCOUNT ON;
 EXEC dbo.local04_staff_guard @actor,1;
 IF @from IS NULL OR @to IS NULL OR @from>@to OR @to='9999-12-31' THROW 52302,'Invalid reporting dates',1;
 DECLARE @upper date=DATEADD(day,1,@to),@today date=CONVERT(date,SYSDATETIME());
 UPDATE dbo.membership SET status='EXPIRED' WHERE status='ACTIVE' AND end_date<@today;
 DECLARE @valid_payments TABLE (payment_time datetime2(0),payment_method varchar(20),amount decimal(12,2));
 INSERT @valid_payments
 SELECT p.payment_time,p.payment_method,p.amount FROM dbo.payment p
 JOIN dbo.membership m ON m.membership_id=p.membership_id AND m.total_price=p.amount
 WHERE p.payment_time>=@from AND p.payment_time<@upper AND m.status IN ('PENDING_ACTIVATION','ACTIVE','EXPIRED');

 SELECT 'members_all' AS metric,CAST(N'' AS nvarchar(30)) AS segment,COUNT_BIG(*) AS quantity,
    CAST(NULL AS decimal(38,2)) AS amount FROM dbo.member
 UNION ALL SELECT 'members_new',N'',COUNT_BIG(*),NULL FROM dbo.member WHERE join_date>=@from AND join_date<@upper
 UNION ALL SELECT 'members_active',N'',COUNT_BIG(*),NULL FROM dbo.member u WHERE EXISTS(
    SELECT 1 FROM dbo.membership m WHERE m.person_id=u.person_id AND m.status='ACTIVE' AND @today BETWEEN m.start_date AND m.end_date)
 UNION ALL SELECT 'members_expired',N'',COUNT_BIG(*),NULL FROM dbo.member u WHERE EXISTS(
    SELECT 1 FROM dbo.membership m WHERE m.person_id=u.person_id AND (m.status='EXPIRED' OR m.status='ACTIVE' AND m.end_date<@today))
   AND NOT EXISTS(SELECT 1 FROM dbo.membership m WHERE m.person_id=u.person_id AND m.status='ACTIVE'
       AND @today BETWEEN m.start_date AND m.end_date)
 UNION ALL SELECT 'plans_active',N'',COUNT_BIG(*),NULL FROM dbo.membership
    WHERE status='ACTIVE' AND @today BETWEEN start_date AND end_date
 UNION ALL SELECT 'plans_expired',N'',COUNT_BIG(*),NULL FROM dbo.membership WHERE status='EXPIRED' OR status='ACTIVE' AND end_date<@today
 UNION ALL SELECT 'contracts',N'',COUNT_BIG(*),SUM(total_price) FROM dbo.membership WHERE created_at>=@from AND created_at<@upper
 UNION ALL SELECT 'contract_status',status,COUNT_BIG(*),SUM(total_price) FROM dbo.membership
    WHERE created_at>=@from AND created_at<@upper GROUP BY status
 UNION ALL SELECT 'receipts',N'',COUNT_BIG(*),SUM(amount) FROM @valid_payments
 UNION ALL SELECT 'receipt_method',payment_method,COUNT_BIG(*),SUM(amount) FROM @valid_payments GROUP BY payment_method
 UNION ALL SELECT 'receipt_month',CONVERT(char(7),payment_time,120),COUNT_BIG(*),SUM(amount) FROM @valid_payments
    GROUP BY CONVERT(char(7),payment_time,120)
 UNION ALL SELECT 'pt',N'',COUNT_BIG(*),NULL FROM dbo.pt_session p JOIN dbo.[session] s ON s.session_id=p.session_id
    WHERE s.start_time>=@from AND s.start_time<@upper
 UNION ALL SELECT 'classes',N'',COUNT_BIG(*),SUM(CONVERT(bigint,max_capacity)) FROM dbo.vw_group_class_enrollment
    WHERE start_time>=@from AND start_time<@upper
 UNION ALL SELECT 'seats',N'',COALESCE(SUM(CONVERT(bigint,current_enrollment)),0),NULL FROM dbo.vw_group_class_enrollment
    WHERE start_time>=@from AND start_time<@upper
 UNION ALL SELECT 'booked',N'',COUNT_BIG(*),NULL FROM dbo.booking
    WHERE booked_at>=@from AND booked_at<@upper
 UNION ALL SELECT 'cancelled',N'',COUNT_BIG(*),NULL FROM dbo.booking
    WHERE booking_status='CANCEL' AND cancelled_at>=@from AND cancelled_at<@upper
 UNION ALL SELECT 'equipment',status,COUNT_BIG(*),NULL FROM dbo.equipment GROUP BY status
 UNION ALL SELECT 'maintenance_open',N'',COUNT_BIG(*),NULL FROM dbo.equipment_maintenance_log WHERE end_date IS NULL
 UNION ALL SELECT 'maintenance_cost',N'',COUNT_BIG(*),SUM(cost) FROM dbo.equipment_maintenance_log
    WHERE end_date>=@from AND end_date<@upper;
END;
GO

CREATE PROCEDURE dbo.localr1a_profile @actor int
AS
BEGIN
 SET NOCOUNT ON;
 DECLARE @today date=CONVERT(date,SYSDATETIME());
 SELECT p.person_id,p.full_name,p.email,p.phone,p.date_of_birth,p.gender,p.address,
   m.join_date,s.position,s.hire_date AS staff_hire,s.employment_status AS staff_status,
   t.hire_date AS trainer_hire,t.employment_status AS trainer_status,
   c.membership_id,c.plan_name,c.start_date,c.end_date
 FROM dbo.person p
 LEFT JOIN dbo.member m ON m.person_id=p.person_id
 LEFT JOIN dbo.staff s ON s.person_id=p.person_id
 LEFT JOIN dbo.trainer t ON t.person_id=p.person_id
 OUTER APPLY (
   SELECT k.membership_id,g.plan_name,k.start_date,k.end_date
   FROM dbo.membership k JOIN dbo.membership_plan g ON g.plan_id=k.plan_id
   WHERE k.person_id=m.person_id AND k.status='ACTIVE' AND @today BETWEEN k.start_date AND k.end_date
 ) c
 WHERE p.person_id=@actor AND (m.person_id IS NOT NULL OR s.employment_status='ACTIVE'
                               OR t.employment_status IN ('ACTIVE','ON_LEAVE'));
END;
GO
