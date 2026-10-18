# Palm Logistics — SQL Server Handover

## Purpose and current status

This guide records the procedure used to create and test the Palm Logistics read-only SQL Server account.

> **Completed already:** the SQL login **`palm-logistics-reader`** was created and tested successfully against the **`PalmLogistics`** database. 

The procedure deliberately avoids destructive write tests. It verifies permissions with SQL Server metadata functions and performs only `SELECT` queries against data.

## Known environment details

| Item | Value |
|---|---|
| AWS CLI profile | `palm-developer-keys` |
| AWS region | `eu-north-1` |
| EC2 instance | `i-0f40d0e804c8e423b` |
| SSM-managed SQL container | `legacy-mssql` |
| SQL Server remote port | `1433` |
| Local tunnel port | `1433` |
| Database | `PalmLogistics` |
| Reader login/user | `palm-logistics-reader` |

## Security rules

- Generate the reader password in an approved password manager. In the creation query, replace `PASTE_NEW_PASSWORD_HERE` only in an **unsaved** SQL editor, execute it once, and close the editor without saving.
- Do not test read-only access with `INSERT`, `UPDATE`, `DELETE`, `MERGE`, schema changes, or stored procedures. Use `HAS_PERMS_BY_NAME` as shown below.

## Prerequisites

Install or confirm:

1. AWS CLI v2.
2. Session Manager plugin for the AWS CLI.
3. VS Code.
4. Microsoft's **SQL Server (mssql)** VS Code extension.
5. A temporary AWS identity that can inspect/start the instance and open SSM sessions.
6. A temporary SQL Server `sa` password supplied by IT.

Open a new PowerShell window. Do not paste any passwords into it.

## 1. Set the non-secret connection values

```powershell
$AwsProfile = 'palm-developer-keys'
$AwsRegion = 'eu-north-1'
$InstanceId = 'i-0f40d0e804c8e423b'
$LocalSqlPort = 1433
```

These values last only for the current PowerShell session.

## 2. Verify AWS access

```powershell
aws sts get-caller-identity --profile $AwsProfile
```

Expected: JSON containing the temporary AWS `Account`, `Arn`, and `UserId`. Confirm the account and role/user with IT. Do not copy those values into this guide.

Also confirm which profile source is being used:

```powershell
aws configure list --profile $AwsProfile
```

Expected: the profile resolves a credential source and region. Secret values should be masked by the CLI.

If the first command reports an expired token, invalid key, or access denied, stop and ask IT to renew or correct the temporary access. Do not work around the client's access controls.

## 3. Check the EC2 instance and start it only if stopped

```powershell
$InstanceState = aws ec2 describe-instances `
  --instance-ids $InstanceId `
  --region $AwsRegion `
  --profile $AwsProfile `
  --query 'Reservations[0].Instances[0].State.Name' `
  --output text

$InstanceState
```

Expected: `running` or `stopped`.

If the output is exactly `stopped`, start the existing instance and wait until AWS reports it healthy:

```powershell
if ($InstanceState -eq 'stopped') {
  aws ec2 start-instances `
    --instance-ids $InstanceId `
    --region $AwsRegion `
    --profile $AwsProfile

  aws ec2 wait instance-running `
    --instance-ids $InstanceId `
    --region $AwsRegion `
    --profile $AwsProfile

  aws ec2 wait instance-status-ok `
    --instance-ids $InstanceId `
    --region $AwsRegion `
    --profile $AwsProfile
}
```

Expected: `start-instances` shows a transition such as `stopped` → `pending`. The two `wait` commands normally return no text when successful.

If the original state is `pending`, wait for it instead of issuing another start request:

```powershell
aws ec2 wait instance-running --instance-ids $InstanceId --region $AwsRegion --profile $AwsProfile
aws ec2 wait instance-status-ok --instance-ids $InstanceId --region $AwsRegion --profile $AwsProfile
```

## 4. Confirm that SSM is online

```powershell
aws ssm describe-instance-information `
  --filters "Key=InstanceIds,Values=$InstanceId" `
  --region $AwsRegion `
  --profile $AwsProfile `
  --query 'InstanceInformationList[0].[InstanceId,PingStatus,AgentVersion]' `
  --output table
```

Expected: a table containing the correct instance ID and `Online`. After EC2 starts, SSM may take a few minutes to become online.

Do not continue until `PingStatus` is `Online`.

## 5. Confirm that the existing SQL Server container is running

Start an interactive SSM shell:

```powershell
aws ssm start-session `
  --target $InstanceId `
  --region $AwsRegion `
  --profile $AwsProfile
```

Inside the EC2 session, inspect the existing container:

```bash
sudo docker ps -a --filter 'name=legacy-mssql'
```

Expected: one existing container named `legacy-mssql`.

If that container exists but its status is stopped/exited, start that same container:

```bash
sudo docker start legacy-mssql
sudo docker ps --filter 'name=legacy-mssql'
```

Expected: `legacy-mssql` is shown with a status beginning with `Up`.

Leave the SSM shell:

```bash
exit
```

If the container is missing, unhealthy, or repeatedly exits, stop and escalate to IT. Do not create, rebuild, delete, or replace it during this procedure.

## 6. Establish the SSM port-forwarding tunnel

First confirm that local port 1433 is free:

```powershell
Get-NetTCPConnection -LocalPort $LocalSqlPort -State Listen -ErrorAction SilentlyContinue
```

Expected: no output. If another process is listening, use the alternate-port instructions in Troubleshooting rather than stopping an unknown process.

Open a **separate PowerShell window**, set the same variables, and start the tunnel:

```powershell
$AwsProfile = 'palm-developer-keys'
$AwsRegion = 'eu-north-1'
$InstanceId = 'i-0f40d0e804c8e423b'

aws ssm start-session `
  --target $InstanceId `
  --document-name AWS-StartPortForwardingSession `
  --parameters '{"portNumber":["1433"],"localPortNumber":["1433"]}' `
  --region $AwsRegion `
  --profile $AwsProfile
```

Expected output includes a session ID and text similar to:

```text
Port 1433 opened for sessionId ...
Waiting for connections...
```

Keep this PowerShell window open for the entire SQL session. When VS Code connects, it may also show `Connection accepted for session ...`.

In another PowerShell window, confirm that the local tunnel is listening:

```powershell
Test-NetConnection 127.0.0.1 -Port 1433
```

Expected: `TcpTestSucceeded : True`.

## 7. Connect in VS Code as the temporary `sa` administrator

In VS Code:

1. Open the Command Palette and run **MS SQL: Add Connection** (wording can vary slightly by extension version).
2. Create a temporary connection profile named `Palm Logistics - TEMP sa`.
3. Use these values:
   - Server: `127.0.0.1,1433`
   - Authentication type: **SQL Login**
   - User name: `sa`
   - Password: enter the temporary password supplied by IT
   - Database: `PalmLogistics`
   - Encrypt: enabled
   - Trust server certificate: enabled for this local SSM tunnel
   - Save password: **No**
4. Connect, then use **MS SQL: New Query** to open a new editor bound to `Palm Logistics - TEMP sa`.

Run this identity and authorization check:

```sql
SELECT
    ORIGINAL_LOGIN() AS original_login,
    SUSER_SNAME() AS server_login,
    DB_NAME() AS database_name,
    IS_SRVROLEMEMBER(N'sysadmin') AS is_sysadmin;
GO
```

Expected:

| Column | Expected value |
|---|---|
| `original_login` | `sa` |
| `server_login` | `sa` |
| `database_name` | `PalmLogistics` |
| `is_sysadmin` | `1` |

If `is_sysadmin` is `0` or `NULL`, do not try to create the login; ask IT for the correct authorized administrator account.

## 8. Verify that the reader login and database user are absent

This is the pre-creation check used on a new engagement. Run it while still connected as `sa`:

```sql
USE [master];
GO

SELECT
    SUSER_ID(N'palm-logistics-reader') AS server_principal_id;
GO

USE [PalmLogistics];
GO

SELECT
    USER_ID(N'palm-logistics-reader') AS database_principal_id;
GO
```

Expected before first creation: both values are `NULL`.

If either value is not `NULL`, do not overwrite or recreate anything. Inspect the existing mapping and roles first:

```sql
USE [master];
GO

SELECT name, type_desc, is_disabled, default_database_name
FROM sys.server_principals
WHERE name = N'palm-logistics-reader';
GO

USE [PalmLogistics];
GO

SELECT name, type_desc, authentication_type_desc
FROM sys.database_principals
WHERE name = N'palm-logistics-reader';
GO
```

For this Palm Logistics engagement, the account now exists because it was already created and tested on Day 1. On a repeat run, the next creation script is intentionally idempotent and will not recreate existing principals.

## 9. Create the login, database user, and read-only role membership

Generate a unique strong password in the approved password manager. In the **unsaved `sa` query editor only**, replace `PASTE_NEW_PASSWORD_HERE`, execute the script, and close that password-bearing editor without saving.

```sql
USE [master];
GO

IF SUSER_ID(N'palm-logistics-reader') IS NULL
BEGIN
    CREATE LOGIN [palm-logistics-reader]
    WITH PASSWORD = N'PASTE_NEW_PASSWORD_HERE',
         DEFAULT_DATABASE = [PalmLogistics],
         CHECK_POLICY = ON;
END;
GO

USE [PalmLogistics];
GO

IF USER_ID(N'palm-logistics-reader') IS NULL
BEGIN
    CREATE USER [palm-logistics-reader]
    FOR LOGIN [palm-logistics-reader];
END;
GO

IF IS_ROLEMEMBER(N'db_datareader', N'palm-logistics-reader') <> 1
BEGIN
    ALTER ROLE [db_datareader] ADD MEMBER [palm-logistics-reader];
END;
GO

IF IS_ROLEMEMBER(N'db_denydatawriter', N'palm-logistics-reader') <> 1
BEGIN
    ALTER ROLE [db_denydatawriter] ADD MEMBER [palm-logistics-reader];
END;
GO

DENY EXECUTE TO [palm-logistics-reader];
GO
```

`db_datareader` grants read access to user tables and views. `db_denydatawriter` explicitly blocks ordinary inserts, updates, and deletes. `DENY EXECUTE` blocks stored-procedure execution unless a separately approved exception is granted later.

Expected: each batch completes successfully. VS Code may show `Commands completed successfully`; statements inside already-satisfied `IF` blocks produce no change.

Immediately close the query editor that contained the password and choose **Don't Save**. If the password was copied, clear the Windows clipboard:

```powershell
Set-Clipboard -Value ''
```

## 10. Verify the database user and role membership as `sa`

Open a new clean admin query editor—one that never contained the password—and run:

```sql
USE [PalmLogistics];
GO

SELECT
    users.name AS user_name,
    roles.name AS role_name
FROM sys.database_role_members AS members
JOIN sys.database_principals AS roles
  ON roles.principal_id = members.role_principal_id
JOIN sys.database_principals AS users
  ON users.principal_id = members.member_principal_id
WHERE users.name = N'palm-logistics-reader'
ORDER BY roles.name;
GO
```

Expected rows:

```text
palm-logistics-reader    db_datareader
palm-logistics-reader    db_denydatawriter
```

Confirm the server login is enabled and points to the correct default database:

```sql
USE [master];
GO

SELECT name, type_desc, is_disabled, default_database_name
FROM sys.server_principals
WHERE name = N'palm-logistics-reader';
GO
```

Expected: one `SQL_LOGIN` row, `is_disabled = 0`, and `default_database_name = PalmLogistics`.

## 11. Disconnect `sa` completely

Before testing the reader:

1. Close every query editor that is connected as `sa`.
2. In the SQL Server extension's Connections view, right-click `Palm Logistics - TEMP sa` and choose **Disconnect**.
3. Remove that temporary connection profile after testing is complete. Never save its password.

This matters because a SQL editor keeps the connection it was originally bound to. Selecting the reader profile in the Connections view does **not** automatically change an already-open `sa` editor.

## 12. Create a fresh reader-bound SQL editor

This is the safeguard that fixed the Day 1 issue where the extension showed the reader connection but the old query editor was still running as `sa`.

1. In the SQL Server extension, add/select a connection profile named `Palm Logistics - Reader`.
2. Use:
   - Server: `127.0.0.1,1433`
   - Authentication type: **SQL Login**
   - User name: `palm-logistics-reader`
   - Password: enter it from the password manager
   - Database: `PalmLogistics`
   - Encrypt: enabled
   - Trust server certificate: enabled for this local SSM tunnel
   - Save password: **No**
3. Connect the reader profile.
4. With the reader connection selected, explicitly run **MS SQL: New Query**.
5. Do not reuse, reconnect, or paste into an editor that was previously opened for `sa`.
6. Check the connection shown in that new editor's status bar before executing anything.

## 13. Verify the reader identity and effective permissions

In the newly created reader-bound editor, run:

```sql
USE [PalmLogistics];
GO

SELECT
    ORIGINAL_LOGIN() AS original_login,
    SUSER_SNAME() AS server_login,
    USER_NAME() AS database_user,
    DB_NAME() AS database_name;
GO

SELECT
    HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'SELECT') AS can_select,
    HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'INSERT') AS can_insert,
    HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'UPDATE') AS can_update,
    HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'DELETE') AS can_delete,
    HAS_PERMS_BY_NAME(DB_NAME(), 'DATABASE', 'EXECUTE') AS can_execute;
GO
```

Expected identity:

| Column | Expected value |
|---|---|
| `original_login` | `palm-logistics-reader` |
| `server_login` | `palm-logistics-reader` |
| `database_user` | `palm-logistics-reader` |
| `database_name` | `PalmLogistics` |

Expected effective permissions:

| Column | Expected value |
|---|---|
| `can_select` | `1` |
| `can_insert` | `0` |
| `can_update` | `0` |
| `can_delete` | `0` |
| `can_execute` | `0` |

If `ORIGINAL_LOGIN()` returns `sa`, stop. The editor is stale and is still bound to the administrator connection. Close it, disconnect `sa`, select the reader connection, and create another brand-new query editor as described in Step 12.

## 14. Run a safe sample `SELECT`

First list available application tables without modifying anything:

```sql
USE [PalmLogistics];
GO

SELECT TOP (20)
    SCHEMA_NAME(t.schema_id) AS schema_name,
    t.name AS table_name
FROM sys.tables AS t
ORDER BY schema_name, table_name;
GO
```

Expected: up to 20 table names. Choose a non-sensitive table approved for validation, then run a bounded read:

```sql
SELECT TOP (10) *
FROM [replace_schema].[replace_table];
GO
```

Expected: zero to ten rows, depending on the selected table. The successful query confirms the reader can retrieve data. Do not add or run any write statement merely to prove it fails.

## 15. Securely retire temporary administrator access

Complete all of the following:

1. Confirm all `sa` editors and the `Palm Logistics - TEMP sa` connection are closed/disconnected.
2. Remove the temporary `sa` connection profile from the VS Code SQL Server extension. If VS Code or Windows Credential Manager saved it accidentally, delete that saved credential.
3. Close any unsaved query that ever contained a password and choose **Don't Save**.
4. Clear the clipboard:

   ```powershell
   Set-Clipboard -Value ''
   ```

5. Tell IT that the Day 1 administration task is complete and ask IT to revoke/expire both the temporary AWS administrator identity and the temporary `sa` credential according to its policy. Do not disable or change the shared `sa` account yourself unless IT explicitly directs you to do so.
6. If `palm-developer-keys` was created only for this one-day engagement, remove its local entries after IT confirms revocation. Open these files and delete only the exact named sections—never paste or display their contents in a terminal or chat:
   - `%USERPROFILE%\.aws\credentials`: section `[palm-developer-keys]`
   - `%USERPROFILE%\.aws\config`: section `[profile palm-developer-keys]`
7. Verify the revoked identity can no longer be used:

   ```powershell
   aws sts get-caller-identity --profile $AwsProfile
   ```

   Expected after revocation/removal: an error such as missing credentials, invalid access key, or expired token. Do not expect a successful identity response.

## 16. Close the tunnel

Return to the dedicated PowerShell window running the SSM port-forwarding session and press:

```text
Ctrl+C
```

Expected: the SSM session ends and the PowerShell prompt returns.

Confirm the local SQL endpoint is no longer reachable:

```powershell
Test-NetConnection 127.0.0.1 -Port 1433
```

Expected: `TcpTestSucceeded : False`.

If this engagement started the EC2 instance, ask IT whether it should be stopped. Do not stop it automatically; other services or users may depend on it.

## Troubleshooting

### The SSM tunnel drops or VS Code suddenly disconnects

Symptoms include a closed SSM window, `TcpTestSucceeded : False`, or SQL connection errors after a period of successful use.

1. Confirm EC2 is still running:

   ```powershell
   aws ec2 describe-instances `
     --instance-ids $InstanceId `
     --region $AwsRegion `
     --profile $AwsProfile `
     --query 'Reservations[0].Instances[0].State.Name' `
     --output text
   ```

2. Confirm SSM is online:

   ```powershell
   aws ssm describe-instance-information `
     --filters "Key=InstanceIds,Values=$InstanceId" `
     --region $AwsRegion `
     --profile $AwsProfile `
     --query 'InstanceInformationList[0].PingStatus' `
     --output text
   ```

3. Restart the tunnel with the exact command from Step 6.
4. In VS Code, disconnect and reconnect the intended SQL profile.
5. Open a **new query editor** from that profile; do not trust an editor created before the tunnel dropped.
6. Run the identity query again before continuing.

### Local port 1433 is already in use

Identify the owning process without stopping it:

```powershell
Get-NetTCPConnection -LocalPort 1433 -State Listen |
  Select-Object LocalAddress, LocalPort, OwningProcess
```

Use local port `11433` for the tunnel instead:

```powershell
aws ssm start-session `
  --target $InstanceId `
  --document-name AWS-StartPortForwardingSession `
  --parameters '{"portNumber":["1433"],"localPortNumber":["11433"]}' `
  --region $AwsRegion `
  --profile $AwsProfile
```

Then use `127.0.0.1,11433` as the VS Code server and test with:

```powershell
Test-NetConnection 127.0.0.1 -Port 11433
```

### SSM shows no managed instance or `Offline`

- Wait a few minutes after EC2 reaches `running`.
- Recheck the instance ID and region.
- Confirm with IT that the instance profile, SSM agent, and outbound network access are healthy.
- Do not modify the instance role, agent, or network rules under this database-account procedure.

### VS Code says the certificate is not trusted

Confirm the server is the local tunnel (`127.0.0.1,1433` or the approved alternate local port), keep encryption enabled, and enable **Trust server certificate** for this SSM-tunneled connection. Do not expose SQL Server directly to the internet to avoid the warning.

### The reader login cannot connect

Using the authorized admin connection, check only metadata:

```sql
USE [master];
GO

SELECT name, is_disabled, default_database_name
FROM sys.sql_logins
WHERE name = N'palm-logistics-reader';
GO

USE [PalmLogistics];
GO

SELECT name, type_desc, authentication_type_desc
FROM sys.database_principals
WHERE name = N'palm-logistics-reader';
GO
```

Expected: the server login exists and is enabled, and the mapped database user exists. If authentication still fails, verify the password through the approved password manager and escalate rather than exposing or guessing it.

### The reader connects, but the query still reports `sa`

This is the stale query-editor issue encountered on Day 1. The connection shown in the extension's sidebar does not rebind an already-open editor.

1. Close the affected editor.
2. Disconnect the `sa` connection completely.
3. Select/connect `Palm Logistics - Reader`.
4. Invoke **MS SQL: New Query** from the reader connection.
5. Run the `ORIGINAL_LOGIN()` identity query before any other SQL.

## Completion checklist

- [ ] AWS identity verified with IT.
- [ ] EC2 running and healthy.
- [ ] SSM online.
- [ ] Existing `legacy-mssql` container running.
- [ ] SSM tunnel established without exposing SQL Server publicly.
- [ ] `sa` identity and `sysadmin = 1` verified.
- [ ] Existing login/user state checked before creation.
- [ ] `palm-logistics-reader` login and `PalmLogistics` user present.
- [ ] Membership in `db_datareader` and `db_denydatawriter` verified.
- [ ] `DENY EXECUTE` applied.
- [ ] `sa` disconnected before reader testing.
- [ ] Brand-new editor explicitly bound to reader connection.
- [ ] `ORIGINAL_LOGIN()` reports `palm-logistics-reader`.
- [ ] Effective permissions report `SELECT = 1`; `INSERT/UPDATE/DELETE/EXECUTE = 0`.
- [ ] Bounded sample `SELECT` succeeds.
- [ ] Password-bearing editor closed without saving and clipboard cleared.
- [ ] Temporary admin access handed back to IT for revocation.
- [ ] SSM tunnel closed.

