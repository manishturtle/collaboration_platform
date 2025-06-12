
# authentication.py
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
import jwt
from django.conf import settings
from django.db import connection, connections
from django.db.utils import ConnectionDoesNotExist
from threading import local, current_thread
from functools import wraps
from django_tenants.utils import schema_context
class SimpleTenantUser:
    """A minimal user class that provides just what DRF needs"""
    
    def __init__(self, user_id, tenant_slug, tenant_id):
        self._user_id = user_id
        self._tenant_slug = tenant_slug
        self._tenant_id = tenant_id

    @property
    def id(self):
        return self._user_id

    @property
    def tenant_slug(self):
        return self._tenant_slug

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return True

    def get_username(self):
        return str(self._user_id)

    def __str__(self):
        return f"TenantUser(user_id={self._user_id}, tenant={self._tenant_slug}, tenant_id={self._tenant_id})"

from .router import _thread_locals, get_current_schema
from django.http import JsonResponse
from django.utils import timezone
from django.db import connections
from django.conf import settings

# Using get_current_schema from router.py

def validate_schema_name(schema_name):
    """Validate schema name to prevent SQL injection"""
    if not schema_name.isalnum() and not all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_' for c in schema_name):
        raise AuthenticationFailed('Invalid schema name')

def schema_exists(schema_name):
    """Check if the schema exists in the database"""
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT EXISTS(SELECT 1 FROM information_schema.schemata WHERE schema_name = %s);",
            [schema_name]
        )
        return cursor.fetchone()[0]

def set_schema_for_request(schema_name):
    """Set the schema for the current request/thread"""
    # Validate schema name
    validate_schema_name(schema_name)
    
    # Check if schema exists
    if not schema_exists(schema_name):
        raise AuthenticationFailed(f'Schema {schema_name} does not exist')
    
    _thread_locals.schema = schema_name
    with connection.cursor() as cursor:
        try:
            # First reset to public schema
            cursor.execute('SET search_path TO public;')
            # Then set to the tenant schema
            cursor.execute('SET search_path TO %s, public;', [schema_name])
            print(f'Successfully switched to schema: {schema_name}')
        except Exception as e:
            print(f'Error switching schema: {str(e)}')
            cursor.execute('SET search_path TO public;')
            raise AuthenticationFailed(f'Failed to switch to schema {schema_name}: {str(e)}')

def tenant_schema_required(view_func):
    """Decorator to ensure a view has a tenant schema set"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        schema_name = get_current_schema()
        if not schema_name:
            raise AuthenticationFailed('No tenant schema set')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


import jwt
from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from django.utils import timezone


# place this middleware into all apis
class LicenseValidationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip license validation for certain paths (e.g., health checks, static files)
        skip_paths = ['/api/health/', '/static/', '/media/', '/api/token/']
        if any(request.path.startswith(path) for path in skip_paths):
            return self.get_response(request)

        # Get tenant_id from token
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return self.get_response(request)

        try:
            # Split 'Bearer <token>'
            parts = auth_header.split()
            if len(parts) != 2 or parts[0].lower() != 'bearer':
                return self.get_response(request)

            token = parts[1]
            # Decode the JWT token
            payload = jwt.decode(
                token,
                settings.SIMPLE_JWT['SIGNING_KEY'],
                algorithms=[settings.SIMPLE_JWT['ALGORITHM']]
            )
            tenant_id = payload.get('tenant_id')

            if not tenant_id:
                return JsonResponse({'error': 'Tenant ID not found in token'}, status=403)

            # Switch to public schema to check license
            with connections['default'].cursor() as cursor:
                # Explicitly set search_path to public schema
                cursor.execute("SET search_path TO public")

                # Query the latest active license for the tenant
                cursor.execute("""
                    SELECT tsl.license_key, tsl.license_status, tsl.valid_until, t.status
                    FROM ecomm_superadmin_tenant_subscriptions_licenses tsl
                    JOIN ecomm_superadmin_tenants t ON t.id = tsl.tenant_id
                    WHERE t.id = %s
                    ORDER BY tsl.created_at DESC
                    LIMIT 1
                """, [tenant_id])

                result = cursor.fetchone()

                if not result:
                    return JsonResponse(
                        {'error': 'No valid subscription found'},
                        status=403
                    )

                license_key, license_status, valid_until, tenant_status = result
            
                # Check license status
                if license_status != 'active':
                    return JsonResponse(
                        {'error': f'Subscription license is {license_status}'},
                        status=403
                    )

                # Check tenant status
                if tenant_status not in ['active', 'trial', 'suspended']:
                    return JsonResponse(
                        {'error': f'Tenant account is {tenant_status}'},
                        status=403
                    )

                
                # Check if license is expired
                if valid_until and timezone.now() > valid_until:
                    # Update license status to expired
                    cursor.execute("""
                        UPDATE ecomm_superadmin_tenant_subscriptions_licenses
                        SET license_status = 'expired'
                        WHERE license_key = %s
                    """, [str(license_key)])

                    return JsonResponse(
                        {'error': 'Subscription license has expired'},
                        status=403
                    )
            return self.get_response(request)

        except jwt.ExpiredSignatureError:
            return JsonResponse({'error': 'Token has expired'}, status=401)
        except jwt.InvalidTokenError:
            return JsonResponse({'error': 'Invalid token'}, status=401)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class CustomJWTAuthentication(BaseAuthentication):
    def authenticate(self, request):
        """Authenticate the request and return a two-tuple of (user, token)."""
        # Get the token from the Authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None  # Allow other authentication methods to try

        try:
            # Split 'Bearer <token>'
            parts = auth_header.split()
            if parts[0].lower() != 'bearer':
                raise AuthenticationFailed('Authorization header must start with Bearer')
            if len(parts) == 1:
                raise AuthenticationFailed('Token not found')
            elif len(parts) > 2:
                raise AuthenticationFailed('Authorization header must be Bearer <token>')

            token = parts[1]
            # Decode the JWT token
            payload = jwt.decode(token, settings.SIMPLE_JWT['SIGNING_KEY'], algorithms=[settings.SIMPLE_JWT['ALGORITHM']])

            # Extract tenant_slug from the token payload
            tenant_slug = None

            # Extract tenant_slug from URL parser context
            if hasattr(request, 'parser_context') and 'kwargs' in request.parser_context:
                tenant_slug = request.parser_context['kwargs'].get('tenant_slug')

            # Fallback: Extract from URL resolver
            if not tenant_slug and hasattr(request, 'resolver_match') and request.resolver_match:
                tenant_slug = request.resolver_match.kwargs.get('tenant_slug')

            if not tenant_slug:
                raise AuthenticationFailed("[TenantSchemaMiddleware] Error switching schema: tenant_slug not found in URL")


            # Get user_id from token
            user_id = payload.get('user_id')
            tenant_id = payload.get('tenant_id')

            if not user_id:
                raise AuthenticationFailed('user_id not found in token')

            # Set schema for this request/thread
            self.switch_schema(tenant_slug)

            try:
                # Verify user exists in tenant schema
                with schema_context(tenant_slug):
                    with connection.cursor() as cursor:
                        try:
                            cursor.execute(
                                'SELECT EXISTS(SELECT 1 FROM "ecomm_tenant_admins_tenantuser" WHERE id = %s);',
                                [user_id]
                            )
                            user_exists = cursor.fetchone()[0]
                        except Exception as e:
                            if 'relation' in str(e) and 'does not exist' in str(e):
                                raise AuthenticationFailed(f'User table not found in schema {tenant_slug}')
                            raise
                        if not user_exists:
                            raise AuthenticationFailed(f'User {user_id} not found in tenant schema {tenant_slug}')
                    
                # Create tenant user
                user = SimpleTenantUser(user_id=user_id, tenant_slug=tenant_slug, tenant_id=tenant_id)
            except Exception as e:
                # Reset schema if anything goes wrong
                with connection.cursor() as cursor:
                    cursor.execute('SET search_path TO public;')
                raise
            
            return (user, token)

        except jwt.ExpiredSignatureError:
            raise AuthenticationFailed('Token is expired')
        except jwt.DecodeError:
            raise AuthenticationFailed('Token is invalid')
        except Exception as e:
            raise AuthenticationFailed(str(e))

    def switch_schema(self, tenant_slug):
        """
        Switch to the correct database schema for the current request/thread
        """
        try:
            schema_name = tenant_slug
            set_schema_for_request(schema_name)
            print(f"Schema switched to: {schema_name} for thread {id(current_thread())}")
        except Exception as e:
            raise AuthenticationFailed(f"Error switching schema: {str(e)}")


# API for Ecommerce side where based on tenat_slug schema context changed
from django.utils.deprecation import MiddlewareMixin
from rest_framework.exceptions import AuthenticationFailed
from threading import current_thread


# class TenantSchemaMiddleware(BaseAuthentication):
#     def authenticate(self, request):
        
#         print("authenticate called")
#         """
#         Authentication method that switches schema based on tenant_slug from URL path parameters.
#         Does NOT require authentication token but sets the tenant schema.
        
#         Returns None for both user and auth objects since this doesn't authenticate a user,
#         it just sets the correct schema.
#         """
#         # Get tenant_slug from URL path parameters
#         tenant_slug = None

#         print("calleding:")

#         # Extract from URL path if available
#         if hasattr(request, 'parser_context') and 'kwargs' in request.parser_context:
#             tenant_slug = request.parser_context['kwargs'].get('tenant_slug')
        
#         if not tenant_slug:
#             raise AuthenticationFailed(f"[TenantSchemaMiddleware] Error switching schema: tenant_slug not found in URL")


#         # If not in parser_context, try to get from URL resolver match
#         if not tenant_slug and hasattr(request, 'resolver_match') and request.resolver_match:
#             tenant_slug = request.resolver_match.kwargs.get('tenant_slug')
            
#         if not tenant_slug:
#             # No tenant_slug found, let other authentication methods handle this
#             return None

#         try:
#             # Set the schema for this request
#             set_schema_for_request(tenant_slug)
#             print(f"[TenantSchemaMiddleware] Schema switched to: {tenant_slug} for thread {id(current_thread())}")
            
#             # Store tenant info on the request object for views to access
#             request.tenant_slug = tenant_slug
            
#             # Create a simple tenant object with id and slug for views to use
#             from types import SimpleNamespace
#             tenant = SimpleNamespace(id=1, slug=tenant_slug)  # Default to id=1 for now
            
#             # Try to get the actual tenant ID from the database
#             try:
#                 from django.db import connection
#                 with connection.cursor() as cursor:
#                     # First switch to public schema to query tenant information
#                     cursor.execute("SET search_path TO public")
#                     cursor.execute("SELECT id FROM ecomm_superadmin_tenants WHERE slug = %s", [tenant_slug])
#                     result = cursor.fetchone()
#                     if result:
#                         tenant.id = result[0]
#                     # Switch back to the tenant schema
#                     cursor.execute(f"SET search_path TO {tenant_slug}")
#             except Exception as e:
#                 print(f"[TenantSchemaMiddleware] Error getting tenant ID: {str(e)}")
            
#             # Set the tenant object on the request
#             request.tenant = tenant
            
#             # Return None for both user and auth objects since we're not authenticating a user
#             # but just setting the correct schema
#             return None
#         except Exception as e:
#             raise AuthenticationFailed(f"[TenantSchemaMiddleware] Error switching schema: {str(e)}")



class TenantSchemaMiddleware(BaseAuthentication):
    def authenticate(self, request):

        tenant_slug = None

        # Extract tenant_slug from URL parser context
        if hasattr(request, 'parser_context') and 'kwargs' in request.parser_context:
            tenant_slug = request.parser_context['kwargs'].get('tenant_slug')

        # Fallback: Extract from URL resolver
        if not tenant_slug and hasattr(request, 'resolver_match') and request.resolver_match:
            tenant_slug = request.resolver_match.kwargs.get('tenant_slug')

        if not tenant_slug:
            raise AuthenticationFailed("[TenantSchemaMiddleware] Error switching schema: tenant_slug not found in URL")

        try:
            # Set schema for the tenant
            set_schema_for_request(tenant_slug)
            print(f"[TenantSchemaMiddleware] Schema switched to: {tenant_slug}")

            # Optional: store it on request
            request.tenant_slug = tenant_slug
            print("tenant)slugf::",tenant_slug)
            # Optional: store tenant object on request
            from types import SimpleNamespace
            tenant = SimpleNamespace(id=1, slug=tenant_slug)

            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SET search_path TO public")
                cursor.execute("SELECT id FROM ecomm_superadmin_tenants WHERE url_suffix = %s", [tenant_slug])
                result = cursor.fetchone()
                if result:
                    tenant.id = result[0]
                cursor.execute(f"SET search_path TO {tenant_slug}")

            request.tenant = tenant
            # ✅ Prevent tenant_slug from being passed to view methods
            if hasattr(request, 'parser_context') and 'kwargs' in request.parser_context:
                request.parser_context['kwargs'].pop('tenant_slug', None)

            return None

        except Exception as e:
            raise AuthenticationFailed(f"[TenantSchemaMiddleware] Error switching schema: {str(e)}")
