/*
    PALM LOGISTICS AGENT AUDIT LOG SETUP

    Run this file once as an authorized SQL Server administrator.

    1. Confirm that the EC2 instance is running:

       aws ec2 describe-instances --instance-ids i-0f40d0e804c8e423b --region eu-north-1 --profile palm-developer-keys --query "Reservations[0].Instances[0].State.Name" --output text

    2. Start the SSM tunnel in PowerShell and leave it open:

       aws ssm start-session --target i-0f40d0e804c8e423b --document-name AWS-StartPortForwardingSession --parameters "portNumber=1433,localPortNumber=1433" --region eu-north-1 --profile palm-developer-keys

    3. In VS Code, connect as the authorized SQL administrator:

       Server:   127.0.0.1,1433
       Login:    sa
       Database: PalmLogistics
       Password: Use the temporary administrator password from IT. Do not save it.

    4. Open a new SQL query and run this complete file.

    5. After successful verification, disconnect the administrator account and
       close the SSM tunnel when it is no longer required.
*/

USE [PalmLogistics];
GO

CREATE TABLE [dbo].[AgentAuditLog]
(
    [LogID] BIGINT IDENTITY(1,1) NOT NULL
        CONSTRAINT [PK_AgentAuditLog] PRIMARY KEY,

    [EventTimestampUtc] DATETIME2(3) NOT NULL
        CONSTRAINT [DF_AgentAuditLog_EventTimestampUtc]
        DEFAULT SYSUTCDATETIME(),

    [SessionID] NVARCHAR(128) NOT NULL,
    [NodeExecuted] NVARCHAR(100) NULL,
    [ToolName] NVARCHAR(100) NULL,
    [Content] NVARCHAR(MAX) NULL
);
GO

-- The database-wide deny would override the table-specific INSERT grant.
-- Removing the reader from this role does not grant writes to other tables.
ALTER ROLE [db_denydatawriter]
DROP MEMBER [palm-logistics-reader];
GO

GRANT INSERT
ON OBJECT::[dbo].[AgentAuditLog]
TO [palm-logistics-reader];
GO

DENY SELECT, UPDATE, DELETE
ON OBJECT::[dbo].[AgentAuditLog]
TO [palm-logistics-reader];
GO

-- Verify the reader's effective permissions without inserting a test record.
EXECUTE AS USER = N'palm-logistics-reader';

SELECT
    HAS_PERMS_BY_NAME(
        N'dbo.AgentAuditLog', N'OBJECT', N'INSERT'
    ) AS [can_insert_audit_log],
    HAS_PERMS_BY_NAME(
        N'dbo.AgentAuditLog', N'OBJECT', N'SELECT'
    ) AS [can_select_audit_log],
    HAS_PERMS_BY_NAME(
        N'dbo.AgentAuditLog', N'OBJECT', N'UPDATE'
    ) AS [can_update_audit_log],
    HAS_PERMS_BY_NAME(
        N'dbo.AgentAuditLog', N'OBJECT', N'DELETE'
    ) AS [can_delete_audit_log];

REVERT;
GO

/*
    Expected verification result:

    can_insert_audit_log = 1
    can_select_audit_log = 0
    can_update_audit_log = 0
    can_delete_audit_log = 0
*/
