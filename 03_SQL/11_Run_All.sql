:ON ERROR EXIT
USE [master];
GO
:r .\01_Create_Database.sql
GO
USE [IronPulse_SubmissionQA];
GO
:r .\02_Create_Tables.sql
GO
:r .\09_Indexes.sql
GO
:r .\08_Functions.sql
GO
:r .\05_Views.sql
GO
:r .\06_Triggers.sql
GO
:r .\07_Stored_Procedures.sql
GO
:r .\03_Sample_Data.sql
GO
:r .\10_Verify_Data.sql
GO
:r .\04_Queries.sql
GO
