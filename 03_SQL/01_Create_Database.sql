-- Tạo riêng database học thuật trên SQL Server.
SET NOCOUNT ON;
SET XACT_ABORT ON;
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON;
SET NUMERIC_ROUNDABORT OFF;


IF DB_NAME() <> N'master' THROW 53102, N'Chạy bước 01 trong master.', 1;
IF DB_ID(N'IronPulse_SubmissionQA') IS NOT NULL THROW 53103, N'Database học thuật đã tồn tại. Giữ nguyên dữ liệu.', 1;
IF HAS_PERMS_BY_NAME(NULL,NULL,N'CREATE ANY DATABASE') <> 1
   AND ISNULL(HAS_PERMS_BY_NAME(N'master',N'DATABASE',N'CREATE DATABASE'),0) <> 1
    THROW 53104, N'Tài khoản cài cần quyền tạo database.', 1;
IF EXISTS (SELECT 1 FROM model.sys.objects WHERE is_ms_shipped=0)
    THROW 53105, N'Database model có object riêng, cần môi trường model sạch.', 1;
EXEC(N'CREATE DATABASE [IronPulse_SubmissionQA];');
EXEC(N'ALTER DATABASE [IronPulse_SubmissionQA] SET AUTO_CLOSE OFF;');
EXEC(N'ALTER DATABASE [IronPulse_SubmissionQA] SET RECOVERY SIMPLE;');
EXEC(N'USE [IronPulse_SubmissionQA]; EXEC sys.sp_addextendedproperty @name=N''IronPulseAcademicPackage'', @value=N''1.0.1'';');
