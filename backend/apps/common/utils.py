"""
Common utility functions shared across the application.
"""
from rest_framework.views import exception_handler
from rest_framework import status
from rest_framework.exceptions import NotAuthenticated, AuthenticationFailed

def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    Ensures authentication errors return 401 status codes instead of 403.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    # Check if this is an authentication error
    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        if response is not None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
    
    return response
