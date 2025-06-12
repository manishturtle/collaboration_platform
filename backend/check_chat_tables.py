"""Script to check the structure of chat tables in the turtlesoftware schema."""
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'collaboration_backend.settings')
django.setup()

# Now we can import Django models and database connection
from django.db import connection

def print_table_structure(table_name):
    """Print the structure of a table."""
    with connection.cursor() as cursor:
        # Set the search path to the turtlesoftware schema
        cursor.execute("SET search_path TO turtlesoftware")
        
        # Check if the table exists
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'turtlesoftware' 
                AND table_name = %s
            )
        """, [table_name])
        
        if not cursor.fetchone()[0]:
            print(f"Table {table_name} does not exist in the turtlesoftware schema.")
            return
        
        # Get table columns
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_schema = 'turtlesoftware' 
            AND table_name = %s
            ORDER BY ordinal_position
        """, [table_name])
        
        print(f"\nStructure of {table_name}:")
        print("-" * 80)
        print(f"{'Column Name':<30} {'Data Type':<20} {'Nullable':<10} {'Default'}")
        print("-" * 80)
        
        for col_name, data_type, is_nullable, column_default in cursor.fetchall():
            print(f"{col_name:<30} {data_type:<20} {is_nullable:<10} {column_default or ''}")

# Check the structure of chat-related tables
print("Checking chat tables in turtlesoftware schema...")
print("=" * 80)

# Check the main chat tables
for table in ['chat_chatchannel', 'chat_channelparticipant', 'chat_message', 'chat_messagereadstatus', 'chat_device', 'chat_userchannelstate']:
    print_table_structure(table)

# Also check for the old message table name
print("\nChecking for old message table name...")
print("-" * 80)
print_table_structure('chat_message')

print("\nDone checking chat tables.")
