import pyodbc
import sys
import os
from dotenv import load_dotenv

load_dotenv()
DB_CONN_STR = os.getenv('DB_CONN_STR')
MASTER_CONN_STR = os.getenv('MASTER_CONN_STR')

def create_database():
    print("Connecting to SQL Server master database to check/create HandymanDB...")
    try:
        # Autocommit=True is required to execute CREATE DATABASE statement
        conn = pyodbc.connect(MASTER_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        # Check if HandymanDB exists
        cursor.execute("SELECT database_id FROM sys.databases WHERE name = 'HandymanDB'")
        row = cursor.fetchone()
        if row:
            print("Database 'HandymanDB' already exists.")
        else:
            print("Creating database 'HandymanDB'...")
            cursor.execute("CREATE DATABASE HandymanDB")
            print("Database 'HandymanDB' created successfully.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error checking or creating database: {e}", file=sys.stderr)
        sys.exit(1)

def build_schema_and_seed():
    print("Connecting to HandymanDB to initialize tables and seed data...")
    try:
        conn = pyodbc.connect(DB_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        # 1. Create major_category table
        print("Creating 'major_category' table...")
        cursor.execute("""
            IF OBJECT_ID('dbo.major_category', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.major_category (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    name NVARCHAR(100) NOT NULL UNIQUE,
                    description NVARCHAR(255) NULL
                );
                PRINT 'major_category table created.';
            END
            ELSE
            BEGIN
                PRINT 'major_category table already exists.';
            END
        """)
        
        # 2. Create sub_category table
        print("Creating 'sub_category' table...")
        cursor.execute("""
            IF OBJECT_ID('dbo.sub_category', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.sub_category (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    major_category_id INT NOT NULL,
                    name NVARCHAR(100) NOT NULL,
                    brand NVARCHAR(100) NULL,
                    FOREIGN KEY (major_category_id) REFERENCES dbo.major_category(id) ON DELETE CASCADE,
                    CONSTRAINT UQ_SubCategory UNIQUE (major_category_id, name, brand)
                );
                PRINT 'sub_category table created.';
            END
            ELSE
            BEGIN
                PRINT 'sub_category table already exists.';
            END
        """)
        
        # 3. Create contractor table
        print("Creating 'contractor' table...")
        cursor.execute("""
            IF OBJECT_ID('dbo.contractor', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.contractor (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    first_name NVARCHAR(50) NOT NULL,
                    last_name NVARCHAR(50) NOT NULL,
                    email NVARCHAR(100) NOT NULL UNIQUE,
                    photo NVARCHAR(500) NULL,
                    description NVARCHAR(MAX) NULL,
                    created_at DATETIME DEFAULT GETDATE()
                );
                PRINT 'contractor table created.';
            END
            ELSE
            BEGIN
                PRINT 'contractor table already exists.';
            END
        """)
        
        # 4. Seed major categories
        print("Seeding 'major_category'...")
        major_categories = [
            ("plumbing", "All kinds of plumbing work, leak detection, installation and repair of pipes and fixtures."),
            ("electrical work", "Electrical repairs, installations, panel upgrades, and smart home setups."),
            ("construction", "Drywall repair, framing, masonry, tiling, flooring, and general renovation building work."),
            ("carpentry", "Woodwork, custom cabinetry, shelving, doors, furniture assembly, and framing."),
            ("roofing", "Roof shingle repair, leak troubleshooting, gutter installations, and weatherproofing."),
            ("appliance fixing", "Troubleshooting and repairing household appliances like dishwashers, refrigerators, and washers."),
            ("appliance installing", "Professional installation and hookup of dishwashers, ovens, washers, and other appliances."),
            ("moving", "Local apartment moving, office packing, heavy item loading, transport, and unpacking.")
        ]
        
        for name, desc in major_categories:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.major_category WHERE name = ?)
                BEGIN
                    INSERT INTO dbo.major_category (name, description) VALUES (?, ?);
                END
            """, (name, name, desc))
            
        # Get category map for subcategories
        cursor.execute("SELECT id, name FROM dbo.major_category")
        category_map = {row[1]: row[0] for row in cursor.fetchall()}
        
        # 5. Seed subcategories
        print("Seeding 'sub_category'...")
        sub_categories_data = [
            # (major_category_name, sub_category_name, brand)
            ("plumbing", "Drain Cleaning", None),
            ("plumbing", "Leak Detection & Repair", None),
            ("plumbing", "Toilet Installation & Repair", None),
            ("plumbing", "Water Heater Service", None),
            
            ("electrical work", "Light Fixture Installation", None),
            ("electrical work", "Outlet & Switch Repair", None),
            ("electrical work", "Smart Home Setup", None),
            ("electrical work", "Panel Upgrades", None),
            
            ("construction", "Drywall Repair & Installation", None),
            ("construction", "Tiling & Flooring", None),
            ("construction", "Deck Building & Repair", None),
            ("construction", "Framing & Masonry", None),
            
            ("carpentry", "Custom Shelving & Cabinets", None),
            ("carpentry", "Door Repair & Installation", None),
            ("carpentry", "Trim & Molding Installation", None),
            ("carpentry", "Furniture Assembly", None),
            
            ("roofing", "Shingle Replacement", None),
            ("roofing", "Roof Leak Repair", None),
            ("roofing", "Gutter Cleaning & Installation", None),
            
            ("appliance fixing", "Dishwasher Repair", "Bosch"),
            ("appliance fixing", "Dishwasher Repair", "Whirlpool"),
            ("appliance fixing", "Dishwasher Repair", "Samsung"),
            ("appliance fixing", "Dishwasher Repair", "LG"),
            ("appliance fixing", "Dishwasher Repair", "GE"),
            ("appliance fixing", "Refrigerator Repair", "Samsung"),
            ("appliance fixing", "Refrigerator Repair", "LG"),
            ("appliance fixing", "Refrigerator Repair", "Whirlpool"),
            ("appliance fixing", "Washing Machine Repair", "LG"),
            ("appliance fixing", "Washing Machine Repair", "Whirlpool"),
            ("appliance fixing", "Dryer Repair", "Samsung"),
            ("appliance fixing", "Oven & Range Repair", "GE"),
            
            ("appliance installing", "Dishwasher Installation", "Bosch"),
            ("appliance installing", "Dishwasher Installation", "Whirlpool"),
            ("appliance installing", "Refrigerator Installation", "Samsung"),
            ("appliance installing", "Refrigerator Installation", "LG"),
            ("appliance installing", "Over-the-Range Microwave Installation", None),
            ("appliance installing", "Washer & Dryer Installation", None),
            
            ("moving", "Local Apartment Moving", None),
            ("moving", "Office Relocation", None),
            ("moving", "Single-Item Moving", None),
            ("moving", "Packing & Unpacking Services", None),
        ]
        
        for cat_name, sub_name, brand in sub_categories_data:
            cat_id = category_map.get(cat_name)
            if cat_id is not None:
                cursor.execute("""
                    IF NOT EXISTS (
                        SELECT 1 FROM dbo.sub_category 
                        WHERE major_category_id = ? AND name = ? AND (brand = ? OR (brand IS NULL AND ? IS NULL))
                    )
                    BEGIN
                        INSERT INTO dbo.sub_category (major_category_id, name, brand) VALUES (?, ?, ?);
                    END
                """, (cat_id, sub_name, brand, brand, cat_id, sub_name, brand))
                
        # 6. Seed contractors
        print("Seeding 'contractor'...")
        contractors = [
            ("John", "Doe", "john.doe@handypro.com", 
             "https://images.unsplash.com/photo-1540569014015-19a7be504e3a?w=400&fit=crop", 
             "Over 10 years of experience in professional plumbing and pipe fitting. Specialized in complex leak detection, drain cleaning, and water heater installations. Friendly and punctual service."),
            
            ("Sarah", "Sparks", "sarah.sparks@electrix.net", 
             "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=400&fit=crop", 
             "Certified master electrician specializing in residential smart home systems, panel upgrades, and custom lighting designs. Passionate about electrical safety and energy-efficient solutions."),
            
            ("Mike", "Mason", "mike.mason@constructbuilders.com", 
             "https://images.unsplash.com/photo-1566492031773-4f4e44671857?w=400&fit=crop", 
             "General contractor with expertise in home extensions, drywall repairs, tiling, and outdoor deck construction. Committed to delivering structurally sound, beautiful craftsmanship on time."),
            
            ("David", "Wood", "david.wood@carpentryconcepts.com", 
             "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=400&fit=crop", 
             "Creative carpenter specializing in custom cabinets, shelving units, door framing, and trim installations. I turn your wood design concepts into reality."),
            
            ("Helen", "Heights", "helen.heights@roofguards.com", 
             "https://images.unsplash.com/photo-1580489944761-15a19d654956?w=400&fit=crop", 
             "Expert roofer specializing in shingle replacement, gutter installations, and identifying hard-to-find roof leaks. Focused on weatherproofing homes with durable and long-lasting materials."),
            
            ("Alex", "Fixit", "alex.fixit@appliancedoctor.com", 
             "https://images.unsplash.com/photo-1628157582853-a796fa650a6a?w=400&fit=crop", 
             "Certified appliance technician with factory training for major brands including Bosch, Samsung, LG, and Whirlpool. Specializes in fixing dishwashers, refrigerators, washers, and ovens.")
        ]
        
        for first, last, email, photo, desc in contractors:
            cursor.execute("""
                IF NOT EXISTS (SELECT 1 FROM dbo.contractor WHERE email = ?)
                BEGIN
                    INSERT INTO dbo.contractor (first_name, last_name, email, photo, description) 
                    VALUES (?, ?, ?, ?, ?);
                END
            """, (email, first, last, email, photo, desc))
            
        print("Database structure created and seeded successfully!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error seeding database: {e}", file=sys.stderr)
        sys.exit(1)


def init_db():
    """Initialize the entire database schema and seed data."""
    try:
        create_database()
        build_schema_and_seed()
    except Exception as e:
        print(f"Error initializing database: {e}", file=sys.stderr)


if __name__ == "__main__":
    create_database()
    build_schema_and_seed()
