from django.urls import re_path
from . import consumers

# WebSocket URL patterns for the chat application
websocket_urlpatterns = [
    # WebSocket connection for chat with JWT authentication
    re_path(
        r'ws/chat/$',
        consumers.ChatConsumer.as_asgi(),
        name='chat_websocket'
    ),
    
    # Legacy WebSocket connection for backward compatibility
    re_path(
        r'ws/chat/(?P<channel_id>[\w-]+)/$',
        consumers.LegacyChatConsumer.as_asgi(),
        name='legacy_chat_websocket'
    ),
    
    # WebSocket connection for user presence
    re_path(
        r'ws/presence/$',
        consumers.PresenceConsumer.as_asgi(),
        name='presence_websocket'
    ),
]
