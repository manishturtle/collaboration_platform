"""
WebSocket consumers for real-time chat functionality.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django_tenants.utils import schema_context
from django.contrib.auth import get_user_model
from apps.common.authentication import JWTAuthentication

logger = logging.getLogger(__name__)
User = get_user_model()

class ChatConsumer(AsyncWebsocketConsumer):
    """Handles WebSocket connections for chat channels with JWT authentication."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel_id = None
        self.channel_group_name = None
        self.user = None
        self.subscribed_channels = set()
        
    async def connect(self):
        """Handle new WebSocket connection.
        
        Initially accept all connections. Authentication will be handled via
        the 'auth' message event.
        """
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave all channel groups on disconnect
        for channel_id in self.subscribed_channels:
            await self.channel_layer.group_discard(
                f"chat_{channel_id}",
                self.channel_name
            )
            
            # Notify group that user has left
            if self.user and self.user.is_authenticated:
                await self.channel_layer.group_send(
                    f"chat_{channel_id}",
                    {
                        'type': 'user_left',
                        'user_id': str(self.user.id),
                        'username': self.user.get_username(),
                    }
                )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            event_type = data.get("event_type")

            if event_type == "auth":
                await self.handle_auth(data)
            elif hasattr(self, 'user') and self.user and self.user.is_authenticated:
                # Only process other events if the user is authenticated
                if event_type == "subscribe":
                    await self.handle_subscribe(data)
                elif event_type == "chat_message":
                    await self.handle_chat_message(data)
                elif event_type == "typing":
                    await self.handle_typing_indicator(data)
                else:
                    await self.send_error(f"Unknown event type: {event_type}")
            else:
                await self.send_error("Authentication required.")
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format.")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            await self.send_error(str(e))
    
    async def handle_auth(self, data):
        """Handle authentication request."""
        token = data.get("payload", {}).get("token")
        if not token:
            await self.send_error("Authentication token not provided.", close=True)
            return

        try:
            # Authenticate using JWT
            auth = JWTAuthentication()
            user, _ = await database_sync_to_async(auth.authenticate_credentials)(token)
            if not user or not user.is_authenticated:
                raise Exception("Invalid authentication credentials")
                
            self.user = user
            self.scope["user"] = user
            await self.send_json({
                "event_type": "connection.success", 
                "payload": {"message": "Authentication successful."}
            })
            logger.info(f"User {user.id} authenticated successfully")
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            await self.send_error(f"Authentication failed: {str(e)}", close=True)
    
    async def handle_subscribe(self, data):
        """Handle channel subscription request."""
        channel_id = data.get("payload", {}).get("channel_id")
        if not channel_id:
            await self.send_error("Channel ID not provided for subscription.")
            return
            
        # Verify user has permission to access this channel
        has_permission = await self.check_channel_permission(channel_id)
        if not has_permission:
            await self.send_error("You don't have permission to access this channel.")
            return

        # Add user to channel group
        await self.channel_layer.group_add(
            f"chat_{channel_id}",
            self.channel_name
        )
        self.subscribed_channels.add(channel_id)
        
        await self.send_json({
            "event_type": "subscription.success", 
            "payload": {"channel_id": channel_id}
        })
        
        # Notify group that user has joined
        await self.channel_layer.group_send(
            f"chat_{channel_id}",
            {
                'type': 'user_joined',
                'user_id': str(self.user.id),
                'username': self.user.get_username(),
            }
        )
    
    async def handle_chat_message(self, data):
        """Handle incoming chat message."""
        message = data.get("payload", {}).get("message", "").strip()
        channel_id = data.get("payload", {}).get("channel_id")
        
        if not message or not channel_id:
            await self.send_error("Message and channel_id are required.")
            return
            
        if channel_id not in self.subscribed_channels:
            await self.send_error("You are not subscribed to this channel.")
            return
            
        # Save message to database
        try:
            message_id = await self.save_message(channel_id, message)
            
            # Broadcast message to channel group
            await self.channel_layer.group_send(
                f"chat_{channel_id}",
                {
                    'type': 'chat_message',
                    'message_id': str(message_id),
                    'channel_id': channel_id,
                    'user_id': str(self.user.id),
                    'username': self.user.get_username(),
                    'message': message,
                    'timestamp': data.get("payload", {}).get("timestamp"),
                }
            )
        except Exception as e:
            logger.error(f"Error saving message: {str(e)}")
            await self.send_error("Failed to save message.")
    
    async def handle_typing_indicator(self, data):
        """Handle typing indicator."""
        channel_id = data.get("payload", {}).get("channel_id")
        is_typing = data.get("payload", {}).get("is_typing", False)
        
        if not channel_id or channel_id not in self.subscribed_channels:
            return
            
        await self.channel_layer.group_send(
            f"chat_{channel_id}",
            {
                'type': 'user_typing',
                'user_id': str(self.user.id),
                'username': self.user.get_username(),
                'channel_id': channel_id,
                'is_typing': is_typing,
            }
        )
    
    @database_sync_to_async
    def check_channel_permission(self, channel_id):
        """Check if user has permission to access the channel."""
        from .models import ChatChannel, ChannelParticipant
        
        try:
            # Get the current tenant schema
            schema_name = self.scope.get('tenant', {}).schema_name
            if not schema_name:
                return False
                
            with schema_context(schema_name):
                # Check if user is a participant in the channel
                return ChannelParticipant.objects.filter(
                    channel_id=channel_id,
                    user_id=self.user.id
                ).exists()
        except Exception as e:
            logger.error(f"Error checking channel permission: {str(e)}")
            return False
    
    async def send_json(self, data):
        """Send JSON data through WebSocket."""
        await self.send(text_data=json.dumps(data))
    
    async def send_error(self, message, close=False):
        """Send an error message through WebSocket."""
        await self.send_json({
            "event_type": "error",
            "payload": {"message": message}
        })
        if close:
            await self.close()
    
    async def chat_message(self, event):
        """Handle incoming chat message from channel layer."""
        await self.send_json({
            "event_type": "message.new",
            "payload": {
                "message_id": event["message_id"],
                "channel_id": event["channel_id"],
                "user_id": event["user_id"],
                "username": event["username"],
                "message": event["message"],
                "timestamp": event.get("timestamp"),
            }
        })
    
    async def user_joined(self, event):
        """Notify that a user has joined the channel."""
        await self.send_json({
            "event_type": "user.joined",
            "payload": {
                "user_id": event["user_id"],
                "username": event["username"],
                "timestamp": event.get("timestamp"),
            }
        })
    
    async def user_left(self, event):
        """Notify that a user has left the channel."""
        await self.send_json({
            "event_type": "user.left",
            "payload": {
                "user_id": event["user_id"],
                "username": event["username"],
                "timestamp": event.get("timestamp"),
            }
        })
    
    async def user_typing(self, event):
        """Notify that a user is typing."""
        await self.send_json({
            "event_type": "user.typing",
            "payload": {
                "user_id": event["user_id"],
                "username": event["username"],
                "channel_id": event["channel_id"],
                "is_typing": event["is_typing"],
            }
        })
    
    @database_sync_to_async
    def save_message(self, channel_id, content):
        """Save message to the database."""
        from .models import ChatMessage
        
        # Get the current tenant schema
        schema_name = self.scope.get('tenant', {}).schema_name
        if not schema_name:
            raise Exception("No tenant schema found in scope")
        
        with schema_context(schema_name):
            message = ChatMessage.objects.create(
                channel_id=channel_id,
                user=self.user,
                content=content,
                company_id=self.scope.get('company_id'),
                client_id=self.scope.get('client_id'),
            )
            return message.id


class PresenceConsumer(AsyncWebsocketConsumer):
    """Handles user presence (online/offline status)."""
    
    async def connect(self):
        """Handle new WebSocket connection for presence."""
        self.user = self.scope.get('user')
        
        if not self.user or not self.user.is_authenticated:
            await self.close(code=4001)  # Unauthorized
            return
        
        # Add user to their presence group
        self.presence_group = f'presence_{self.user.id}'
        await self.channel_layer.group_add(
            self.presence_group,
            self.channel_name
        )
        
        await self.accept()
        logger.info(f"User {self.user.id} connected to presence channel")
        
        # Notify user's contacts that they're online
        await self.notify_presence(True)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'presence_group'):
            # Notify user's contacts that they're offline
            await self.notify_presence(False)
            
            # Leave presence group
            await self.channel_layer.group_discard(
                self.presence_group,
                self.channel_name
            )
    
    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming WebSocket messages."""
        if text_data:
            try:
                data = json.loads(text_data)
                if data.get('type') == 'heartbeat':
                    # Update last seen timestamp
                    await self.update_last_seen()
            except json.JSONDecodeError:
                logger.error("Invalid JSON received in presence consumer")
    
    async def presence_update(self, event):
        """Send presence update to the user."""
        await self.send(text_data=json.dumps({
            'type': 'presence_update',
            'user_id': event['user_id'],
            'is_online': event['is_online'],
            'last_seen': event.get('last_seen'),
        }))
    
    async def notify_presence(self, is_online):
        """Notify user's contacts about presence change."""
        # Get user's contacts (implement this based on your app's logic)
        contacts = await self.get_user_contacts()
        
        for contact_id in contacts:
            # Notify each contact
            await self.channel_layer.group_send(
                f'presence_{contact_id}',
                {
                    'type': 'presence_update',
                    'user_id': str(self.user.id),
                    'is_online': is_online,
                    'last_seen': None if is_online else self.user.last_login.isoformat()
                }
            )
    
    @database_sync_to_async
    def get_user_contacts(self):
        """Get list of user IDs that should be notified about presence."""
        # This is a placeholder - implement based on your app's contact/friend system
        return []
    
    @database_sync_to_async
    def update_last_seen(self):
        """Update user's last seen timestamp."""
        if self.user and self.user.is_authenticated:
            self.user.save(update_fields=['last_login'])
