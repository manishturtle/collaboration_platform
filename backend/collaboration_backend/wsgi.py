"""
WSGI config for collaboration_backend project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os
import logging
from django.core.wsgi import get_wsgi_application

# Set up logging
logger = logging.getLogger(__name__)


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'collaboration_backend.settings')

# Check Redis connection on startup
try:
    # Import Django after setting the environment variable
    import django
    django.setup()
    
    # Now import the Redis client
    from apps.common.redis import redis_client
    
    if redis_client:
        # Test Redis connection
        redis_client.ping()
        logger.info("[SUCCESS] Redis connection established successfully!")
        print("\n[SUCCESS] Redis connection established successfully!\n")
    else:
        logger.error("Failed to initialize Redis client")
        print("\n[ERROR] Failed to initialize Redis client\n")
        
except Exception as e:
    logger.error(f"Error connecting to Redis: {e}")
    print(f"\n[ERROR] Could not connect to Redis: {e}\n")

# Initialize WSGI application
application = get_wsgi_application()
