"""Script to check the message table structure in the turtlesoftware schema."""
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'collaboration_backend.settings')
django.setup()

# Now we can import Django models and database connection
from django.db import connection

def check_message_table():
    """Check the structure of the message table."""
    with connection.cursor() as cursor:
        # Set the search path to the turtlesoftware schema
        cursor.execute("SET search_path TO turtlesoftware")
        
        # Check all tables that might be our message table
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'turtlesoftware' 
            AND table_name LIKE '%message%'
            ORDER BY table_name
        """)
        
        print("Tables with 'message' in the name:")
        print("-" * 40)
        for row in cursor.fetchall():
            print(row[0])
        
        # Check the structure of the message table
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_schema = 'turtlesoftware' 
            AND table_name = 'chat_message'
            ORDER BY ordinal_position
        """)
        
        print("\nStructure of chat_message table:")
        print("-" * 80)
        print(f"{'Column Name':<30} {'Data Type':<20} {'Nullable':<10} {'Default'}")
        print("-" * 80)
        
        for col_name, data_type, is_nullable, column_default in cursor.fetchall():
            print(f"{col_name:<30} {data_type:<20} {is_nullable:<10} {column_default or ''}")

if __name__ == "__main__":
    check_message_table()
