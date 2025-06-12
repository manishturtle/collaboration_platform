"""Script to check database tables in the turtlesoftware schema."""
import os
import django

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'collaboration_backend.settings')
django.setup()

# Now we can import Django models and database connection
from django.db import connection

# Set the schema to turtlesoftware
with connection.cursor() as cursor:
    # Set the search path to the turtlesoftware schema
    cursor.execute("SET search_path TO turtlesoftware")
    
    # Get all tables in the turtlesoftware schema
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'turtlesoftware' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    print("Tables in turtlesoftware schema:")
    print("-" * 80)
    for row in cursor.fetchall():
        print(row[0])
    
    # Get chat-related tables
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'turtlesoftware' 
        AND table_name LIKE 'chat_%'
        ORDER BY table_name
    """)
    
    print("\nChat-related tables in turtlesoftware schema:")
    print("-" * 40)
    for row in cursor.fetchall():
        print(row[0])
    
    # Check if the chat_channel table exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = 'turtlesoftware' 
            AND table_name = 'chat_channel'
        )
    """)
    
    chat_channel_exists = cursor.fetchone()[0]
    print(f"\nDoes chat_channel table exist? {'Yes' if chat_channel_exists else 'No'}")
    
    # If chat_channel exists, show its columns
    if chat_channel_exists:
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'turtlesoftware' 
            AND table_name = 'chat_channel'
            ORDER BY ordinal_position
        """)
        
        print("\nColumns in chat_channel table:")
        print("-" * 40)
        for col_name, data_type in cursor.fetchall():
            print(f"{col_name}: {data_type}")
