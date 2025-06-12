# apps/common/authentication.py

from django.contrib.auth import get_user_model
from rest_framework import authentication
from rest_framework import exceptions

# TODO: Import actual JWT decoding and validation libraries (e.g., PyJWT, python-jose)
# TODO: Import requests or httpx for fetching JWKS

User = get_user_model()

class JWTAuthentication(authentication.BaseAuthentication):
    """
    Custom JWT authentication backend.
    
    This class validates a JWT provided in the 'Authorization: Bearer <token>'
    header and returns the corresponding local Django user.
    """
    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).split()

        if not auth_header or auth_header[0].lower() != b'bearer':
            return None

        if len(auth_header) == 1:
            raise exceptions.AuthenticationFailed('Invalid token header. No credentials provided.')
        elif len(auth_header) > 2:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain spaces.')

        try:
            token = auth_header[1].decode('utf-8')
            # --- Placeholder for actual JWT validation logic ---
            # TODO: 1. Fetch public keys from the central Auth Service's JWKS endpoint.
            # TODO: 2. Decode and validate the token signature and claims (issuer, audience, expiry).
            # TODO: 3. Extract the 'sub' (user_id) and 'tenant_id' claims from the token payload.
            
            # For now, we will simulate a successful validation with a dummy user ID.
            # Replace this with the actual user ID from the token payload.
            user_id_from_token = "1" # DUMMY VALUE - REPLACE
            
            # --- End Placeholder ---

            user, created = User.objects.get_or_create(id=user_id_from_token)
            if created:
                # If the user is created for the first time, you might want to
                # populate their details from other token claims if available.
                user.username = f'user_{user_id_from_token}'
                user.save()

        except UnicodeError:
            raise exceptions.AuthenticationFailed('Invalid token header. Token string should not contain invalid characters.')
        except Exception as e:
            # In a real implementation, log this error
            raise exceptions.AuthenticationFailed(f'Invalid token. {e}')

        return (user, token)
