"""Script to verify the MessageReadStatus table was created correctly."""
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'collaboration_backend.settings')
django.setup()

# Now we can import Django models and database connection
from django.db import connection

def check_messagereadstatus_table():
    """Check the structure of the messagereadstatus table."""
    with connection.cursor() as cursor:
        # Set the search path to the turtlesoftware schema
        cursor.execute("SET search_path TO turtlesoftware")
        
        # Check if the table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'turtlesoftware' 
                AND table_name = 'chat_messagereadstatus'
            )
        """)
        
        table_exists = cursor.fetchone()[0]
        print(f"Table chat_messagereadstatus exists: {table_exists}")
        
        if not table_exists:
            return
        
        # Get the table structure
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_schema = 'turtlesoftware' 
            AND table_name = 'chat_messagereadstatus'
            ORDER BY ordinal_position
        """)
        
        print("\nStructure of chat_messagereadstatus table:")
        print("-" * 80)
        print(f"{'Column Name':<20} {'Data Type':<30} {'Nullable'}")
        print("-" * 80)
        
        for col_name, data_type, is_nullable in cursor.fetchall():
            print(f"{col_name:<20} {data_type:<30} {is_nullable}")
        
        # Check for the unique constraint
        cursor.execute("""
            SELECT conname, conkey, pg_get_constraintdef(oid)
            FROM pg_constraint 
            WHERE conrelid = 'turtlesoftware.chat_messagereadstatus'::regclass
            AND contype = 'u'  -- u = unique constraint
        """)
        
        print("\nUnique constraints:")
        for conname, conkey, condef in cursor.fetchall():
            print(f"- {conname}: {condef}")

if __name__ == "__main__":
    check_messagereadstatus_table()
