import redis
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_CONFIG = {
    'host': '127.0.0.1',  # Use localhost
    'port': 6379,
    'db': 0,  # Default database
    'decode_responses': True,  # Automatically decode responses to strings
    'socket_connect_timeout': 5,  # 5 seconds timeout
    'socket_timeout': 5,  # 5 seconds socket timeout
    'retry_on_timeout': True,
}

# Create Redis client
try:
    redis_client = redis.Redis(**REDIS_CONFIG)
    # Test the connection
    redis_client.ping()
    logger.info("Successfully connected to Redis")
except redis.ConnectionError as e:
    logger.error(f"Could not connect to Redis: {e}")
    redis_client = None
except Exception as e:
    logger.error(f"Unexpected error connecting to Redis: {e}")
    redis_client = None
    print("Unable to connect to Redis.")