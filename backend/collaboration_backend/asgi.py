"""
ASGI config for collaboration_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os
import sys
import logging
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.urls import path

# Set up logging
logger = logging.getLogger(__name__)

# Set the default Django settings module
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

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# Import WebSocket URL patterns after Django setup
from apps.chat import routing as chat_routing

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(
        URLRouter(
            chat_routing.websocket_urlpatterns
        )
    ),
})
