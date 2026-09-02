"""Repository for client and address data."""
from backend.v1.db.connection import get_db_connection


def get_client_by_phone(phone: str):
    """Fetch a client by their primary phone number."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.last_name, c.phone, c.additional_phone, c.email,
                   (SELECT TOP 1 a.address_text FROM dbo.Addresses a 
                    JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID 
                    WHERE ca.CLIENT_ID = c.id ORDER BY a.IS_MAIN_ADDRESS DESC, a.ID ASC) as address
            FROM dbo.Clients c 
            WHERE c.phone = ?
        """, (phone,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return {
                "id": row.id,
                "name": row.name,
                "last_name": row.last_name,
                "phone": row.phone,
                "additional_phone": row.additional_phone,
                "email": row.email,
                "address": row.address
            }
        return None
    except Exception as e:
        print(f"Error fetching client by phone: {e}")
        return None


def get_client_by_id(client_id: int):
    """Fetch a client by their ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.id, c.name, c.last_name, c.phone, c.additional_phone, c.email,
                   (SELECT TOP 1 a.address_text FROM dbo.Addresses a 
                    JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID 
                    WHERE ca.CLIENT_ID = c.id ORDER BY a.IS_MAIN_ADDRESS DESC, a.ID ASC) as address
            FROM dbo.Clients c 
            WHERE c.id = ?
        """, (client_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if row:
            return {
                "id": row.id,
                "name": row.name,
                "last_name": row.last_name,
                "phone": row.phone,
                "additional_phone": row.additional_phone,
                "email": row.email,
                "address": row.address
            }
        return None
    except Exception as e:
        print(f"Error fetching client by ID: {e}")
        return None


def create_client(name: str, last_name: str, phone: str, additional_phone: str, email: str, address: str = None):
    """Create a new client and return their ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.Clients (name, last_name, phone, additional_phone, email)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?)
        """, (name, last_name, phone, additional_phone, email))
        client_id = cursor.fetchone()[0]

        if address:
            cursor.execute("""
                INSERT INTO dbo.Addresses (address_text, IS_MAIN_ADDRESS)
                OUTPUT INSERTED.ID
                VALUES (?, 1)
            """, (address,))
            address_id = cursor.fetchone()[0]

            cursor.execute("""
                INSERT INTO dbo.Client_Address (CLIENT_ID, ADDRESS_ID)
                VALUES (?, ?)
            """, (client_id, address_id))

        conn.commit()
        cursor.close()
        conn.close()
        return client_id
    except Exception as e:
        print(f"Error creating client: {e}")
        return None


def update_client(client_id: int, name: str, last_name: str, additional_phone: str, email: str, address: str = None):
    """Update an existing client's details."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.Clients
            SET name = ?, last_name = ?, additional_phone = ?, email = ?
            WHERE id = ?
        """, (name, last_name, additional_phone, email, client_id))

        if address:
            cursor.execute("""
                SELECT a.ID FROM dbo.Addresses a
                JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID
                WHERE ca.CLIENT_ID = ? AND a.address_text = ?
            """, (client_id, address))
            existing_address = cursor.fetchone()

            if not existing_address:
                cursor.execute("""
                    INSERT INTO dbo.Addresses (address_text, IS_MAIN_ADDRESS)
                    OUTPUT INSERTED.ID
                    VALUES (?, 0)
                """, (address,))
                address_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO dbo.Client_Address (CLIENT_ID, ADDRESS_ID)
                    VALUES (?, ?)
                """, (client_id, address_id))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Error updating client: {e}")
        return False


def get_main_address_by_client_id(client_id: int):
    """Fetch the main address for a given client ID."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT TOP 1 a.address_text 
            FROM dbo.Addresses a 
            JOIN dbo.Client_Address ca ON a.ID = ca.ADDRESS_ID 
            WHERE ca.CLIENT_ID = ? 
            ORDER BY a.IS_MAIN_ADDRESS DESC, a.ID ASC
        """, (client_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
        return row[0] if row else None
    except Exception as e:
        print(f"Error fetching main address for client: {e}")
        return None
