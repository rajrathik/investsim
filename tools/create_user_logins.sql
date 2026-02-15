-- Create user_logins table in REDACTED-DB-NAME database
-- Run in SSMS or sqlcmd against your SQL Server instance
--
-- This table logs every Auth0 login event. The auth0_user_id is the
-- stable user identifier for future features (saving simulations, etc.)
--
-- Note: init_db() in database.py will also auto-create this table
-- on startup. This script is for manual/DBA-controlled creation.

USE REDACTED-DB-NAME;
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'user_logins')
BEGIN
    CREATE TABLE user_logins (
        id              INT IDENTITY(1,1) PRIMARY KEY,
        auth0_user_id   NVARCHAR(255)   NOT NULL,
        email           NVARCHAR(255)   NULL,
        name            NVARCHAR(255)   NULL,
        login_time      DATETIME2       NOT NULL DEFAULT SYSUTCDATETIME(),
        ip_address      NVARCHAR(45)    NULL,
        user_agent      NVARCHAR(500)   NULL
    );

    CREATE NONCLUSTERED INDEX ix_user_logins_auth0_user_id
        ON user_logins (auth0_user_id);

    CREATE NONCLUSTERED INDEX ix_user_logins_login_time
        ON user_logins (login_time DESC);

    PRINT 'Table user_logins created successfully.';
END
ELSE
BEGIN
    PRINT 'Table user_logins already exists.';
END
GO
