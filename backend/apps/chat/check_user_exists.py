"""
Utility for checking if users exist in tenant schemas.
"""
from django.db import connection
import logging

logger = logging.getLogger(__name__)

def check_user_exists(user_id: int, schema_name: str = 'turtlesoftware') -> bool:
    """
    Check if a user exists in the tenant's user table.
    
    Args:
        user_id: The ID of the user to check
        schema_name: The tenant schema name to check in
        
    Returns:
        True if user exists, False otherwise
    """
    if not schema_name:
        schema_name = 'turtlesoftware'
        
    # Validate schema name (basic validation to prevent SQL injection)
    if not schema_name.isalnum() and schema_name != 'public':
        schema_name = 'turtlesoftware'
        
    try:
        with connection.cursor() as cursor:
            # First check if the schema exists
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                [schema_name]
            )
            schema_exists = cursor.fetchone()[0]
            
            if not schema_exists:
                logger.warning(f"Schema {schema_name} does not exist")
                return False
                
            # Set the search path to the tenant schema
            cursor.execute(f"SET search_path TO {schema_name}")
            
            # Find potential user tables in this schema
            cursor.execute("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = %s
                AND (
                    table_name LIKE '%user%' OR
                    table_name LIKE '%auth%'
                )
                ORDER BY 
                    CASE 
                        WHEN table_name = 'ecomm_tenant_admins_tenantuser' THEN 1
                        WHEN table_name = 'auth_user' THEN 2
                        ELSE 3
                    END
            """, [schema_name])
            
            tables = cursor.fetchall()
            
            if not tables:
                logger.error(f"No user-like tables found in schema {schema_name}")
                return False
                
            # Try each table until we find the user
            for table in tables:
                table_name = table[0]
                try:
                    # Check if the table has an id column
                    cursor.execute(f"""
                        SELECT EXISTS(
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_schema = %s 
                            AND table_name = %s 
                            AND column_name = 'id'
                        )
                    """, [schema_name, table_name])
                    
                    has_id_column = cursor.fetchone()[0]
                    
                    if has_id_column:
                        # Check if user with this ID exists
                        cursor.execute(f"SET search_path TO {schema_name}")
                        cursor.execute(f"SELECT EXISTS(SELECT 1 FROM {table_name} WHERE id = %s)", [user_id])
                        user_exists = cursor.fetchone()[0]
                        
                        if user_exists:
                            logger.info(f"User {user_id} found in {schema_name}.{table_name}")
                            return True
                except Exception as e:
                    logger.warning(f"Error checking {table_name}: {str(e)}")
                    continue
            
            # If we get here, user wasn't found in any table
            logger.warning(f"User {user_id} not found in any tables in schema {schema_name}")
            return False
            
    except Exception as e:
        logger.error(f"Error checking user existence: {str(e)}")
        return False
