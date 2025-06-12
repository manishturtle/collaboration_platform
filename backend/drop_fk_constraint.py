"""
Drop the foreign key constraint from chat_channelparticipant to auth_user
to allow multi-tenant user references.
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

def drop_fk_constraint(schema_name="turtlesoftware"):
    """Drop the foreign key constraint from chat_channelparticipant to auth_user"""
    
    logger.info(f"Dropping FK constraint in schema '{schema_name}'")
    
    # Verify schema exists
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT EXISTS(
                SELECT 1 FROM information_schema.schemata WHERE schema_name = %s
            )
        """, [schema_name])
        schema_exists = cursor.fetchone()[0]
        
        if not schema_exists:
            logger.error(f"Schema '{schema_name}' does not exist!")
            return
            
    with schema_context(schema_name):
        with connection.cursor() as cursor:
            # First find the constraint name
            cursor.execute("""
                SELECT constraint_name
                FROM information_schema.constraint_column_usage
                WHERE table_name = 'chat_channelparticipant'
                AND column_name = 'user_id'
                AND constraint_name LIKE '%fk%'
            """)
            constraints = cursor.fetchall()
            
            if not constraints:
                logger.info(f"No FK constraints found on chat_channelparticipant.user_id in schema {schema_name}")
                return
                
            logger.info(f"Found constraints: {constraints}")
            
            # Drop each constraint
            for constraint in constraints:
                constraint_name = constraint[0]
                try:
                    logger.info(f"Dropping constraint {constraint_name}")
                    cursor.execute(f"ALTER TABLE chat_channelparticipant DROP CONSTRAINT IF EXISTS {constraint_name}")
                    logger.info(f"Successfully dropped constraint {constraint_name}")
                except Exception as e:
                    logger.error(f"Error dropping constraint {constraint_name}: {str(e)}")

if __name__ == "__main__":
    # Use default value or command line argument
    schema = "turtlesoftware"
    
    # Option to specify schema via command line argument
    if len(sys.argv) > 1:
        schema = sys.argv[1]
    
    logger.info(f"Processing schema '{schema}'")
    drop_fk_constraint(schema)
