import datetime
import logging
from typing import Dict, Any, Optional

import jwt
import psycopg2
import psycopg2.errors
from psycopg2.extras import RealDictCursor

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import serializers


# Configure logger
logger = logging.getLogger(__name__)

class AuthenticateUserView(APIView):
    """
    API endpoint that authenticates a user against the tenant_user table
    and returns a JWT token on successful authentication.
    
    This view bypasses Django's ORM and directly uses SQL queries for authentication.
    """
    permission_classes = [AllowAny]
    
    def get_db_connection(self) -> psycopg2.extensions.connection:
        """
        Establish a connection to the PostgreSQL database.
        
        Returns:
            A connection object to the PostgreSQL database
        """
        return psycopg2.connect(
            dbname=settings.DATABASES['default']['NAME'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a password against a Django hashed password.
        
        Args:
            plain_password: Plain text password to verify
            hashed_password: Django hashed password from the database
            
        Returns:
            True if the password matches, False otherwise
        """
        return check_password(plain_password, hashed_password)
    
    def authenticate_user(self, identifier: str, password: str, tenant_slug: str = None) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user using raw SQL queries against the tenant_user table.
        
        Args:
            identifier: The username or email to check
            password: The password to verify
            tenant_slug: Optional tenant slug to determine schema
            
        Returns:
            User data dictionary if authentication is successful, None otherwise
        """
        connection = self.get_db_connection()
        if not connection:
            return None
            
        # Use tenant_slug if provided, otherwise default to turtlesoftware
        schema_name = tenant_slug if tenant_slug else 'turtlesoftware'
            
        try:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                # First check if the schema exists
                schema_check_query = """
                SELECT EXISTS(
                    SELECT 1 FROM information_schema.schemata 
                    WHERE schema_name = %s
                )
                """
                cursor.execute(schema_check_query, (schema_name,))
                schema_exists = cursor.fetchone().get('exists', False)
                
                if not schema_exists:
                    # Fall back to turtlesoftware if schema doesn't exist
                    schema_name = 'turtlesoftware'
                    
                # Check for various possible user table names in the schema
                possible_table_names = [
                    'ecomm_tenant_admins_tenantuser',  # Current format
                    'tenantuser',                     # Simple format
                    'auth_user',                      # Django default
                    'users',                          # Common format
                    'tenant_users',                   # Another format
                    'user'                            # Basic format
                ]
                
                user_table = None
                for table_name in possible_table_names:
                    table_check_query = """
                    SELECT EXISTS(
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = %s AND table_name = %s
                    )
                    """
                    cursor.execute(table_check_query, (schema_name, table_name))
                    table_exists = cursor.fetchone().get('exists', False)
                    
                    if table_exists:
                        user_table = table_name
                        break
                
                if not user_table:
                    # Let's check what tables do exist in this schema for debugging
                    tables_query = """
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = %s
                    LIMIT 10
                    """
                    cursor.execute(tables_query, (schema_name,))
                    print("KK:")
                    existing_tables = [row.get('table_name') for row in cursor.fetchall()]
                    raise Exception(f"User table not found in schema '{schema_name}'. Available tables: {', '.join(existing_tables) if existing_tables else 'none'}")
                
                # Now we have confirmed the user table name
                
                # Determine if the identifier is an email or username
                if '@' in identifier:
                    where_clause = "email = %s"
                else:
                    where_clause = "username = %s"
                
                # Query the tenant_user table with dynamic schema and table name
                query = f"""
                SELECT 
                    id as user_id, 
                    username, 
                    email,
                    password
                FROM 
                    {schema_name}.{user_table}
                WHERE 
                    {where_clause}
                """
                
                cursor.execute(query, (identifier,))
                user_record = cursor.fetchone()
                
                if not user_record:
                    return None
                
                # The password in the database is Django's pbkdf2_sha256 format
                # Use Django's check_password function for verification
                stored_password = user_record['password']
                
                # Verify the password using Django's check_password
                if not self.verify_password(password, stored_password):
                    return None
                    
                # Return user data without the password
                return {
                    'user_id': user_record['user_id'],
                    'username': user_record['username'],
                    'email': user_record['email'],
                }
        except psycopg2.errors.UndefinedTable as e:
            logger.error(f"Table not found error: {str(e)}")
            logger.error("The table 'turtlesoftware.ecomm_tenant_admins_tenantuser' does not exist")
            return None
        except psycopg2.errors.UndefinedColumn as e:
            logger.error(f"Column not found error: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Database authentication error: {str(e)}")
            return None
        finally:
            if 'conn' in locals():
                conn.close()
    
    def generate_jwt_token(self, user_data: Dict[str, Any]) -> str:
        """
        Generate a JWT token for the authenticated user using settings from SIMPLE_JWT.
        
        Args:
            user_data: Dictionary containing user information
            
        Returns:
            JWT token string
        """
        # Use token lifetime from settings, with fallback to 24 hours
        token_lifetime = settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME', datetime.timedelta(days=1))
        now = timezone.now()
        expiry = now + token_lifetime
        
        # Build the JWT payload
        payload = {
            'user_id': str(user_data['user_id']),  # Subject (user identifier)
            'username': user_data['username'],
            'email': user_data['email'],
            'exp': expiry,  # Expiration time
            'iat': now,  # Issued at
            'iss': 'collaboration_platform',  # Issuer
        }
        
        # Use algorithm and signing key from settings, with fallbacks
        algorithm = settings.SIMPLE_JWT.get('ALGORITHM', 'HS256')
        signing_key = settings.SIMPLE_JWT.get('SIGNING_KEY', settings.SECRET_KEY)
        
        # Generate the token
        token = jwt.encode(
            payload,
            signing_key,
            algorithm=algorithm
        )
        
        return token
    
    class AuthenticationSerializer(serializers.Serializer):
        username = serializers.CharField(max_length=255, required=False)
        email = serializers.CharField(max_length=255, required=False)
        password = serializers.CharField(max_length=255, required=True)
        
        def validate(self, data):
            if not data.get('username') and not data.get('email'):
                raise serializers.ValidationError('Username or email is required')
            return data
    
    def post(self, request: Request):
        """
        Handle POST requests for user authentication.
        
        Args:
            request: The HTTP request object
            
        Returns:
            Response with JWT token or error message
        """
        serializer = self.AuthenticationSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            
        # Extract credentials from serializer
        identifier = serializer.validated_data.get('username') or serializer.validated_data.get('email')
        password = serializer.validated_data.get('password')
        
        # Extract tenant_slug from URL path if available
        tenant_slug = None
        url_path = request.path
        
        # URL format: /api/v1/{tenant_slug}/auth/login/
        path_parts = url_path.strip('/').split('/')
        if len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'v1':
            tenant_slug = path_parts[2]
            
        # Authenticate user with tenant context
        try:
            user_data = self.authenticate_user(identifier, password, tenant_slug=tenant_slug)
            
            if user_data:
                # Generate JWT token
                token = self.generate_jwt_token(user_data)
                
                # Include tenant info in response
                return Response({
                    'token': token,
                    'user': {
                        'id': user_data['user_id'],
                        'username': user_data['username'],
                        'email': user_data['email'],
                        'tenant': tenant_slug or 'turtlesoftware'
                    }
                }, status=status.HTTP_200_OK)
            else:
                # Return error for invalid credentials
                return Response(
                    {'detail': 'Invalid credentials'}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
        except Exception as e:
            # Log the error and expose better messages for tenant issues
            logger = logging.getLogger(__name__)
            logger.error(f"Authentication error: {str(e)}")
            
            error_message = 'Authentication failed'
            if 'User table not found' in str(e):
                error_message = str(e)
            
            # Return error response with more specific message for schema issues
            return Response(
                {'detail': error_message}, 
                status=status.HTTP_401_UNAUTHORIZED
            )
        # Log successful authentication (without revealing token)
        logger.info(f"Successful authentication for user ID: {user_data['user_id']}")
        
        # Get token lifetime in seconds for response
        token_lifetime_seconds = int(settings.SIMPLE_JWT.get('ACCESS_TOKEN_LIFETIME', datetime.timedelta(days=1)).total_seconds())
        
        # Return token and minimal user data
        return Response({
            'token': token,
            'user': {
                'id': user_data['user_id'],
                'username': user_data['username'], 
                'email': user_data['email']
            },
            'expires_in': token_lifetime_seconds
        })
