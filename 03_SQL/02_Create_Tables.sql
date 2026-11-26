-- Schema khóa và ràng buộc v1.0.1, gồm các cột bổ sung.
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

ALTER TABLE dbo.membership ADD local02_request_id uniqueidentifier NULL;

ALTER TABLE dbo.member_service_usage ADD booking_id int NULL;

ALTER TABLE dbo.member_service_usage WITH CHECK ADD CONSTRAINT fk_usage_booking
 FOREIGN KEY (booking_id) REFERENCES dbo.booking(booking_id);

ALTER TABLE dbo.membership_plan ADD is_for_sale bit NOT NULL CONSTRAINT df_plan_for_sale DEFAULT(1);

ALTER TABLE dbo.payment ADD recorded_by int NULL;

ALTER TABLE dbo.payment WITH CHECK ADD CONSTRAINT fk_payment_recorded_by FOREIGN KEY(recorded_by)
 REFERENCES dbo.staff(person_id);
COMMIT TRANSACTION;
