"""
Diagnose potential issues with chat tables in tenant schemas
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

def diagnose_chat_tables(schema_name="turtlesoftware", test_user_id=1):
    """Diagnose issues with chat tables in the given tenant schema"""
    
    logger.info(f"Diagnosing chat tables in schema '{schema_name}'")
    
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
            
        logger.info(f"Schema '{schema_name}' found ✓")
    
    # Now work within the tenant schema context
    with schema_context(schema_name):
        with connection.cursor() as cursor:
            # Check if user exists
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = 'ecomm_tenant_admins_tenantuser'
                )
            """, [schema_name])
            user_table_exists = cursor.fetchone()[0]
            
            if not user_table_exists:
                logger.error(f"User table 'ecomm_tenant_admins_tenantuser' not found in schema '{schema_name}'")
            else:
                logger.info(f"User table 'ecomm_tenant_admins_tenantuser' found ✓")
                
                # Check test user existence
                cursor.execute(f"""
                    SELECT EXISTS(
                        SELECT 1 FROM ecomm_tenant_admins_tenantuser WHERE id = %s
                    )
                """, [test_user_id])
                user_exists = cursor.fetchone()[0]
                
                if user_exists:
                    logger.info(f"Test user with ID {test_user_id} found ✓")
                    
                    # Get username for confirmation
                    cursor.execute(f"""
                        SELECT username FROM ecomm_tenant_admins_tenantuser WHERE id = %s
                    """, [test_user_id])
                    username = cursor.fetchone()[0]
                    logger.info(f"Username: {username}")
                else:
                    logger.error(f"Test user with ID {test_user_id} not found!")
            
            # Check chat channel table
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = 'chat_chatchannel'
                )
            """, [schema_name])
            channel_table_exists = cursor.fetchone()[0]
            
            if not channel_table_exists:
                logger.error(f"Chat channel table 'chat_chatchannel' not found in schema '{schema_name}'")
            else:
                logger.info(f"Chat channel table 'chat_chatchannel' found ✓")
                
                # Examine channel table structure
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = 'chat_chatchannel'
                    ORDER BY ordinal_position
                """, [schema_name])
                columns = cursor.fetchall()
                
                logger.info(f"Chat channel table structure:")
                for col in columns:
                    logger.info(f"  - {col[0]} ({col[1]})")
            
            # Check participant table
            cursor.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = %s AND table_name = 'chat_channelparticipant'
                )
            """, [schema_name])
            participant_table_exists = cursor.fetchone()[0]
            
            if not participant_table_exists:
                logger.error(f"Channel participant table 'chat_channelparticipant' not found in schema '{schema_name}'")
            else:
                logger.info(f"Channel participant table 'chat_channelparticipant' found ✓")
                
                # Examine participant table structure
                cursor.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = %s AND table_name = 'chat_channelparticipant'
                    ORDER BY ordinal_position
                """, [schema_name])
                columns = cursor.fetchall()
                
                logger.info(f"Channel participant table structure:")
                for col in columns:
                    logger.info(f"  - {col[0]} ({col[1]})")

if __name__ == "__main__":
    # Use default values for non-interactive running
    schema = "turtlesoftware"
    user_id = 1
    
    # Option to specify schema via command line argument
    if len(sys.argv) > 1:
        schema = sys.argv[1]
        
    # Option to specify user ID via command line argument
    if len(sys.argv) > 2:
        try:
            user_id = int(sys.argv[2])
        except ValueError:
            logger.error(f"Invalid user ID: {sys.argv[2]}")
            user_id = 1
    
    logger.info(f"Diagnosing schema '{schema}' with test user ID {user_id}")
    diagnose_chat_tables(schema, user_id)
