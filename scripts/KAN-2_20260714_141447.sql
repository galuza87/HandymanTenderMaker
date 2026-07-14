-- Description: This script creates the Addresses and Client_Address tables, and drops the address column from Clients.

-- Create Addresses table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Addresses' and xtype='U')
BEGIN
    CREATE TABLE dbo.Addresses (
        ID INT IDENTITY(1,1) PRIMARY KEY,
        address_text NVARCHAR(250),
        IS_MAIN_ADDRESS BIT DEFAULT 0,
        Project_id INT
    )
END

-- Create Client_Address junction table
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='Client_Address' and xtype='U')
BEGIN
    CREATE TABLE dbo.Client_Address (
        CLIENT_ID INT,
        ADDRESS_ID INT,
        PRIMARY KEY (CLIENT_ID, ADDRESS_ID),
        FOREIGN KEY (CLIENT_ID) REFERENCES dbo.Clients(id),
        FOREIGN KEY (ADDRESS_ID) REFERENCES dbo.Addresses(ID)
    )
END

-- Drop address column from Clients table if it exists
IF COL_LENGTH('dbo.Clients', 'address') IS NOT NULL
BEGIN
    ALTER TABLE dbo.Clients DROP COLUMN address
END
