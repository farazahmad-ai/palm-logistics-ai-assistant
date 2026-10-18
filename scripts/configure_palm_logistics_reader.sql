/*
    BEFORE RUNNING THIS SQL

    1. Make sure the EC2 instance is running:

       aws ec2 describe-instances --instance-ids i-0f40d0e804c8e423b --region eu-north-1 --profile palm-developer-keys --query "Reservations[0].Instances[0].State.Name" --output text

       If it is stopped, run:

       aws ec2 start-instances --instance-ids i-0f40d0e804c8e423b --region eu-north-1 --profile palm-developer-keys
       aws ec2 wait instance-running --instance-ids i-0f40d0e804c8e423b --region eu-north-1 --profile palm-developer-keys

    2. Start the SQL Server tunnel in PowerShell and leave it open:

       aws ssm start-session --target i-0f40d0e804c8e423b --document-name AWS-StartPortForwardingSession --parameters '{"portNumber":["1433"],"localPortNumber":["1433"]}' --region eu-north-1 --profile palm-developer-keys

    3. In VS Code, connect to SQL Server as the administrator:

       Server:   127.0.0.1,1433
       Login:    sa
       Database: PalmLogistics
       Password: Use the temporary administrator password from IT. Do not save it.

    4. Open a new unsaved query, replace PASTE_NEW_PASSWORD_HERE with a new
       reader password, run the SQL below, and close the query without saving.
*/

-- Palm Logistics read-only account setup
-- Run as an authorized SQL Server administrator.
-- Replace the password only in an unsaved query editor. Do not save it here.

USE [master];
GO

CREATE LOGIN [palm-logistics-reader]
WITH PASSWORD = N'PASTE_NEW_PASSWORD_HERE',
     DEFAULT_DATABASE = [PalmLogistics],
     CHECK_POLICY = ON;
GO

USE [PalmLogistics];
GO

CREATE USER [palm-logistics-reader]
FOR LOGIN [palm-logistics-reader];
GO

ALTER ROLE [db_datareader]
ADD MEMBER [palm-logistics-reader];
GO

ALTER ROLE [db_denydatawriter]
ADD MEMBER [palm-logistics-reader];
GO

DENY EXECUTE TO [palm-logistics-reader];
GO
