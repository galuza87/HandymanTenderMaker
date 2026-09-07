import pyodbc
import sys
import os
from dotenv import load_dotenv

load_dotenv()
DB_CONN_STR = os.getenv('DB_CONN_STR')

def seed_data():
    print("Connecting to HandymanDB to seed data...")
    try:
        conn = pyodbc.connect(DB_CONN_STR, autocommit=True)
        cursor = conn.cursor()
        
        # 1. Seed major categories
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
            
        # 2. Seed contractors
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
            
        print("Database seeded successfully!")
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error seeding database: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    seed_data()
