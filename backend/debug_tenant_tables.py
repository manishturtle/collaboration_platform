"""
Debug utility to list all tables in the tenant schemas.
Run with: python debug_tenant_tables.py
"""
import os
import sys
import django
import logging

# Initialize Django
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "collaboration_backend.settings")
django.setup()

from django.db import connection

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def list_tenant_tables():
    """List all tables in the tenant schemas."""
    with connection.cursor() as cursor:
        # Get all schemas
        cursor.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
            ORDER BY schema_name
        """)
        schemas = [row[0] for row in cursor.fetchall()]
        
        logger.info(f"Found {len(schemas)} schemas: {', '.join(schemas)}")
        
        # For each schema, get tables related to users
        for schema in schemas:
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s
                ORDER BY table_name
            """, [schema])
            all_tables = [row[0] for row in cursor.fetchall()]
            
            # Find tables that might be user tables
            user_tables = [table for table in all_tables if 'user' in table.lower()]
            auth_tables = [table for table in all_tables if 'auth' in table.lower()]
            
            # Show tables by category
            logger.info(f"Schema '{schema}' contains {len(all_tables)} tables")
            
            if user_tables:
                logger.info(f"  User-related tables: {', '.join(user_tables)}")
                
                # Check column structure of user tables
                for table in user_tables:
                    cursor.execute(f"""
                        SELECT column_name
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = %s
                    """, [schema, table])
                    columns = [row[0] for row in cursor.fetchall()]
                    logger.info(f"    Table '{table}' columns: {', '.join(columns)}")
                    
                    # Check if this is a valid user table with basic authentication fields
                    has_username = 'username' in columns
                    has_email = 'email' in columns
                    has_password = 'password' in columns
                    
                    if has_username and has_password:
                        logger.info(f"    ✅ '{schema}.{table}' appears to be a valid user table.")
                    else:
                        logger.info(f"    ❌ '{schema}.{table}' is missing key user fields.")
                    
                    # For debugging, get row count
                    try:
                        cursor.execute(f"SET search_path TO {schema}")
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        row_count = cursor.fetchone()[0]
                        logger.info(f"    Table has {row_count} rows")
                    except Exception as e:
                        logger.error(f"    Could not count rows: {str(e)}")
                
            if auth_tables:
                logger.info(f"  Auth-related tables: {', '.join(auth_tables)}")

if __name__ == "__main__":
    logger.info("Starting tenant table inspection...")
    list_tenant_tables()
    logger.info("Inspection complete.")
