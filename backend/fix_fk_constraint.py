"""
Fix the foreign key constraint issue with a more thorough approach
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
from django_tenants.utils import schema_context

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_constraint_issues():
    """
    Find and fix foreign key constraint issues related to chat_channelparticipant.user_id
    """
    
    # List of schemas to check - include public and tenant schema
    schemas = ["public", "turtlesoftware"]
    
    # Check additional schemas if needed
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast', 'public', 'turtlesoftware')
            LIMIT 10
        """)
        additional_schemas = [row[0] for row in cursor.fetchall()]
        schemas.extend(additional_schemas)
        
    logger.info(f"Checking schemas: {schemas}")
    
    # Process each schema
    for schema in schemas:
        logger.info(f"Processing schema '{schema}'")
        
        # Set schema context
        with schema_context(schema):
            with connection.cursor() as cursor:
                # Check if chat_channelparticipant table exists in this schema
                cursor.execute(f"""
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = '{schema}' AND table_name = 'chat_channelparticipant'
                    )
                """)
                table_exists = cursor.fetchone()[0]
                
                if not table_exists:
                    logger.info(f"Table 'chat_channelparticipant' doesn't exist in schema '{schema}', skipping")
                    continue
                    
                logger.info(f"Found 'chat_channelparticipant' table in schema '{schema}'")
                
                # Check table structure
                cursor.execute(f"""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = '{schema}' AND table_name = 'chat_channelparticipant'
                """)
                columns = cursor.fetchall()
                logger.info(f"Table columns: {columns}")
                
                # Find all constraints on the table
                cursor.execute(f"""
                    SELECT con.conname, con.contype, pg_get_constraintdef(con.oid)
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    WHERE nsp.nspname = '{schema}'
                    AND rel.relname = 'chat_channelparticipant'
                """)
                constraints = cursor.fetchall()
                
                for constraint in constraints:
                    name, type_code, definition = constraint
                    logger.info(f"Constraint: {name} ({type_code}) - {definition}")
                    
                    # Check if this relates to any references to auth_user
                    if 'auth_user' in definition:
                        try:
                            logger.info(f"Dropping FK constraint '{name}' in schema '{schema}'")
                            cursor.execute(f"ALTER TABLE {schema}.chat_channelparticipant DROP CONSTRAINT IF EXISTS {name}")
                            logger.info(f"✅ Successfully dropped constraint '{name}'")
                            
                            # Create index for the source column to maintain performance
                            # Extract column name from constraint definition
                            if 'user_id' in definition:
                                col_name = 'user_id'
                            elif 'created_by_id' in definition:
                                col_name = 'created_by_id'
                            elif 'updated_by_id' in definition:
                                col_name = 'updated_by_id'
                            else:
                                col_name = None
                            
                            if col_name:
                                index_name = f"chat_channelparticipant_{col_name}_idx"
                                cursor.execute(f"""
                                    CREATE INDEX IF NOT EXISTS {index_name}
                                    ON {schema}.chat_channelparticipant ({col_name})
                                """)
                                logger.info(f"Created index {index_name} on {col_name}")
                        except Exception as e:
                            logger.error(f"Error dropping constraint: {str(e)}")
                            
                    # Also check for any constraints that might have been created through migrations
                    # but not properly detected
                    if type_code == 'f' and ('chat_channelparticipant' in definition):
                        logger.info(f"Checking additional constraint: {name}")
                        try:
                            cursor.execute(f"ALTER TABLE {schema}.chat_channelparticipant DROP CONSTRAINT IF EXISTS {name}")
                            logger.info(f"✅ Dropped additional constraint '{name}'")
                        except Exception as e:
                            logger.info(f"Info: {str(e)}")


                # As a fallback, try a more direct approach if we didn't find and drop any constraints
                try:
                    logger.info(f"Attempting direct constraint drop on chat_channelparticipant_user_id_beeb51d8_fk_auth_user_id")
                    cursor.execute(f"""
                        ALTER TABLE {schema}.chat_channelparticipant 
                        DROP CONSTRAINT IF EXISTS chat_channelparticipant_user_id_beeb51d8_fk_auth_user_id
                    """)
                except Exception as e:
                    logger.info(f"Direct drop returned: {str(e)}")
                
                # Verify constraints after our changes
                cursor.execute(f"""
                    SELECT con.conname, con.contype, pg_get_constraintdef(con.oid)
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
                    WHERE nsp.nspname = '{schema}'
                    AND rel.relname = 'chat_channelparticipant'
                    AND pg_get_constraintdef(con.oid) LIKE '%auth_user%'
                """)
                remaining = cursor.fetchall()
                if remaining:
                    logger.warning(f"⚠️ Still found {len(remaining)} constraints related to auth_user!")
                else:
                    logger.info(f"✅ No constraints related to auth_user remain in schema '{schema}'")

if __name__ == "__main__":
    logger.info("Starting constraint fixing process...")
    fix_constraint_issues()
    logger.info("Process completed.")
