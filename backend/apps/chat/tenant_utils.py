"""
Utility functions for working with tenant schemas in a multi-tenant environment.
Provides functions to ensure SQL operations target the correct tenant schema.
"""
from django.db import connection, transaction
from django.db.utils import ProgrammingError
import logging

logger = logging.getLogger(__name__)

def execute_in_tenant_schema(schema_name, sql, params=None):
    """
    Execute a SQL statement in the specified tenant schema.
    
    Args:
        schema_name: The name of the schema to execute the SQL in
        sql: The SQL statement to execute
        params: Parameters for the SQL statement
    
    Returns:
        Result of the query
    """
    # Default to turtlesoftware if no schema provided
    if not schema_name:
        schema_name = 'turtlesoftware'
    
    # Validate schema name (basic validation to prevent SQL injection)
    if not schema_name.isalnum() and schema_name != 'public':
        schema_name = 'turtlesoftware'
    
    result = None
    with connection.cursor() as cursor:
        try:
            # First verify schema exists
            cursor.execute(
                "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                [schema_name]
            )
            schema_exists = cursor.fetchone()[0]
            
            if not schema_exists:
                logger.warning(f"Schema {schema_name} does not exist, falling back to turtlesoftware")
                schema_name = 'turtlesoftware'
            
            # Set search path to the tenant schema
            cursor.execute(f"SET search_path TO {schema_name}")
            
            # Verify the table exists in this schema if it's an insert/update operation
            table_name = None
            sql_lower = sql.lower().strip()
            
            if sql_lower.startswith('insert into'):
                # Extract table name from INSERT INTO statement
                table_parts = sql_lower.split('into ')[1].split('(')[0].strip().split(' ')
                table_name = table_parts[0]
            elif sql_lower.startswith('update'):
                # Extract table name from UPDATE statement
                table_parts = sql_lower.split('update ')[1].split(' ')[0].strip()
                table_name = table_parts
                
            # Remove schema prefix if present
            if table_name and '.' in table_name:
                table_name = table_name.split('.')[-1]
                
            if table_name:
                cursor.execute(
                    "SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_schema = %s AND table_name = %s)",
                    [schema_name, table_name]
                )
                table_exists = cursor.fetchone()[0]
                if not table_exists:
                    logger.warning(f"Table {table_name} does not exist in schema {schema_name}")
                    raise ProgrammingError(f"Table {table_name} does not exist in schema {schema_name}")
            
            # Execute the actual SQL
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            
            # For SELECT statements, fetch results
            if sql.lower().startswith('select'):
                result = cursor.fetchall()
                
            # For INSERT with RETURNING, fetch the returned value
            elif 'returning' in sql.lower():
                result = cursor.fetchone()
                
        except Exception as e:
            logger.error(f"Error executing SQL in schema {schema_name}: {str(e)}")
            raise
            
    return result

def create_in_tenant_schema(schema_name, table_name, data):
    """
    Create a record in a table in the specified tenant schema.
    
    Args:
        schema_name: Name of the tenant schema
        table_name: Name of the table
        data: Dictionary of column_name: value pairs
    
    Returns:
        ID of the created record, if available
    """
    columns = list(data.keys())
    placeholders = ["%s"] * len(columns)
    values = [data[col] for col in columns]
    
    sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({', '.join(placeholders)}) RETURNING id"
    
    return execute_in_tenant_schema(schema_name, sql, values)

def find_in_tenant_schema(schema_name, table_name, filters):
    """
    Find records in a table in the specified tenant schema.
    
    Args:
        schema_name: Name of the tenant schema
        table_name: Name of the table
        filters: Dictionary of column_name: value pairs to filter by
    
    Returns:
        List of matching records
    """
    where_clauses = []
    values = []
    
    for column, value in filters.items():
        where_clauses.append(f"{column} = %s")
        values.append(value)
    
    where_sql = " AND ".join(where_clauses)
    sql = f"SELECT * FROM {table_name}"
    
    if where_sql:
        sql += f" WHERE {where_sql}"
        
    return execute_in_tenant_schema(schema_name, sql, values)
