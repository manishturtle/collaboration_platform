# apps/chat/api/views.py

import logging
from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

# Setup logger
logger = logging.getLogger(__name__)
from django.db import connection
from django_tenants.utils import schema_context
from django_tenants.utils import get_tenant_model

from ..models import ChatChannel, ChannelParticipant, ChatMessage
from ..create_channel import create_tenant_channel  # Import the new tenant-aware function
from ..selectors import get_channels_for_user
from .serializers import ChatChannelSerializer, MessageSerializer, ChannelParticipantSerializer
from apps.chat.tenant_middleware import CustomJWTAuthentication
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def get_schema_name(request):
    """Helper to get schema name from request"""
    # Try to get tenant from request object
    if hasattr(request, 'tenant'):
        return request.tenant.schema_name if request.tenant else 'public'
    
    # Try to get tenant from URL kwargs
    if hasattr(request, 'resolver_match') and hasattr(request.resolver_match, 'kwargs'):
        tenant_slug = request.resolver_match.kwargs.get('tenant_slug')
        if tenant_slug:
            try:
                from django_tenants.utils import get_tenant_model
                TenantModel = get_tenant_model()
                tenant = TenantModel.objects.get(schema_name=tenant_slug)
                return tenant.schema_name
            except (TenantModel.DoesNotExist, AttributeError):
                pass
    
    # Default to public schema
    return 'public'

class ChannelViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    A ViewSet for listing, retrieving, and creating Chat Channels.
    """

    authentication_classes = [CustomJWTAuthentication]

    serializer_class = ChatChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all the channels
        for the currently authenticated user.
        """
        return get_channels_for_user(user=self.request.user)

    def perform_create(self, serializer):
        # Get user ID from the authenticated user (from JWT token)
        user_id = self.request.user.id if hasattr(self.request.user, 'id') else None
        
        # If using SimpleTenantUser, handle it differently
        if not user_id and hasattr(self.request.user, 'user_id'):
            user_id = self.request.user.user_id
        
        # Extract participant IDs
        participants = serializer.validated_data.pop('participants', [])
        
        # Handle contextual chat fields
        is_contextual_chat = serializer.validated_data.pop('is_contextual_chat', False)
        host_application_id = serializer.validated_data.pop('host_application_id', None)
        context_object_type = serializer.validated_data.pop('context_object_type', None)
        context_object_id = serializer.validated_data.pop('context_object_id', None)
        
        # Set created_by and updated_by from the current user
        if hasattr(self.request.user, 'id'):
            serializer.validated_data['created_by_id'] = self.request.user.id
            serializer.validated_data['updated_by_id'] = self.request.user.id
        
        # Extract tenant slug from URL path
        tenant_slug = None
        if 'tenant_slug' in self.kwargs:
            tenant_slug = self.kwargs['tenant_slug']
        elif hasattr(self.request, 'tenant') and self.request.tenant:
            tenant_slug = self.request.tenant
        elif hasattr(self.request, 'path'):
            # URL format: /api/v1/{tenant_slug}/chat/channels/
            path_parts = self.request.path.strip('/').split('/')
            if len(path_parts) >= 3 and path_parts[0] == 'api' and path_parts[1] == 'v1':
                tenant_slug = path_parts[2]
        
        # Make sure tenant_slug is not None and log it
        if not tenant_slug:
            tenant_slug = 'turtlesoftware'
            
        logger.info(f"Using tenant schema: {tenant_slug}")
        
        # Set schema name to tenant_slug
        schema_name = tenant_slug
        
        try:
            # Create channel using tenant-aware function
            result = create_tenant_channel(
                name=serializer.validated_data.get('name', 'New Channel'),
                user_id=user_id,
                participants=participants,
                is_contextual_chat=is_contextual_chat,
                host_application_id=host_application_id,
                context_object_type=context_object_type,
                context_object_id=context_object_id,
                schema_name=schema_name
            )
            
            # Process result - result is already a dictionary with channel details
            if not result or 'id' not in result:
                raise ValueError("Failed to create channel: No channel ID returned")
            
            # Get the channel ID and ensure it's a string
            channel_id = str(result['id'])  # Convert UUID to string if needed
            
            # Create a new dictionary with just the fields that match our serializer
            response_data = {
                'id': channel_id,
                'name': result.get('name', ''),
                'channel_type': result.get('channel_type', 'group'),
                'created_at': result.get('created_at'),
                # Add other fields that your serializer expects
            }
            
            # If this is an existing channel, include the participants
            if result.get('is_existing', False):
                with schema_context(schema_name):
                    channel = ChatChannel.objects.get(id=channel_id)
                    response_data['participations'] = ChannelParticipantSerializer(
                        channel.participations.all(), many=True
                    ).data
            
            # Return the response data directly, bypassing the serializer
            headers = self.get_success_headers(response_data)
            return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)
            
        except ValueError as e:
            # Handle known validation errors with specific messages
            error_message = str(e)
            logger.error(f"Validation error creating channel: {error_message}")
            
            # Check for specific error types
            if "User not found in schema" in error_message:
                return Response(
                    {"detail": error_message}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            else:
                return Response(
                    {"detail": error_message}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            # Handle unexpected errors
            error_message = str(e)
            logger.error(f"Unexpected error creating channel: {error_message}")
            
            # Return a more descriptive error message but not internal details
            return Response(
                {"detail": "Error creating chat channel. Please check server logs."}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def create(self, request, *args, **kwargs):
        # We override create to call our custom perform_create which returns a Response
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Check participants validation
        participants = serializer.validated_data.get('participants', [])
        if not participants:
            return Response(
                {"participants": ["At least one participant is required to create a channel"]},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            return self.perform_create(serializer)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)


class MessageViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     viewsets.GenericViewSet):
    """
    A ViewSet for listing and creating Messages within a Channel.
    """
    serializer_class = MessageSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [CustomJWTAuthentication]

    def get_queryset(self):
        """
        This view should return a list of all messages for the
        channel as determined by the `channel_pk` URL parameter.
        """
        channel_pk = self.kwargs.get('channel_pk')
        # Get the tenant schema from the request
        schema_name = getattr(self.request.tenant, 'schema_name', 'public')
        
        # Filter messages by channel and order by creation date (newest first)
        with schema_context(schema_name):
            # First verify the channel exists and user has access
            try:
                channel = ChatChannel.objects.get(pk=channel_pk)
                # Verify user is a participant
                if not ChannelParticipant.objects.filter(
                    channel=channel,
                    user=self.request.user
                ).exists():
                    return ChatMessage.objects.none()
                
                return ChatMessage.objects.filter(
                    channel_id=channel_pk
                ).select_related('user').order_by('-created_at')
                
            except (ChatChannel.DoesNotExist, ValueError):
                return ChatMessage.objects.none()

    def create(self, request, *args, **kwargs):
        """
        Custom create method to completely bypass serializer issues
        """
        channel_pk = self.kwargs.get('channel_pk')
        
        # Extract tenant_slug directly from URL path
        # URL format is typically /api/v1/{tenant_slug}/chat/channels/{channel_pk}/messages/
        path_parts = request.path.strip('/').split('/')
        tenant_slug = None
        
        # Look for tenant slug in the URL path
        for i, part in enumerate(path_parts):
            if part == 'api' and i+2 < len(path_parts):
                tenant_slug = path_parts[i+2]
                break
        
        # If we found a tenant_slug, use it; otherwise fallback to get_schema_name
        if tenant_slug:
            schema_name = tenant_slug
        else:
            schema_name = get_schema_name(request)
        
        logger.info(f"Using schema: {schema_name} for message creation from path: {request.path}")
        
        # Ensure we're using the correct schema context
        with schema_context(schema_name):
            try:
                # Get the channel and verify it exists
                channel = ChatChannel.objects.get(pk=channel_pk)
                
                # Get user ID - ensure it's an integer
                user_id = getattr(request.user, 'id', None)
                if not isinstance(user_id, int) and user_id is not None:
                    try:
                        user_id = int(user_id)
                    except (ValueError, TypeError):
                        user_id = None
                
                # Extract fields from request data
                content = request.data.get('content', '')
                parent_id = request.data.get('parent') 
                metadata = request.data.get('metadata', {}) or {}
                
                # Create message using SQL to bypass model validation
                from django.db import connection
                
                # Prepare the query with only fields that exist in the database
                query = """
                INSERT INTO chat_message 
                (channel_id, user_id, content, parent_id, metadata, 
                created_at, updated_at, created_by_id, updated_by_id, company_id, client_id) 
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW(), %s, %s, %s, %s) 
                RETURNING id, created_at
                """
                
                # Convert metadata to JSON string
                import json
                metadata_json = json.dumps(metadata)
                
                # Execute the query
                with connection.cursor() as cursor:
                    cursor.execute(query, [
                        str(channel.id),  # channel_id (UUID)
                        user_id,          # user_id
                        content,          # content
                        parent_id,        # parent_id
                        metadata_json,    # metadata
                        user_id,          # created_by_id
                        user_id,          # updated_by_id
                        1,                # company_id
                        1                 # client_id
                    ])
                    
                    # Get the result
                    result = cursor.fetchone()
                    message_id = result[0]
                    created_at = result[1]
                
                # Create a minimal message object for the response
                class SimpleMessage:
                    pass
                
                message = SimpleMessage()
                message.id = message_id
                message.content = content
                message.created_at = created_at
                message.channel = channel
                message.metadata = metadata
                
                # Create response data manually
                response_data = {
                    'id': message.id,
                    'content': message.content,
                    'created_at': message.created_at.isoformat() if hasattr(message.created_at, 'isoformat') else message.created_at,
                    'channel': str(message.channel.id),
                    'user': {
                        'id': user_id,
                        'username': getattr(request.user, 'username', f'user_{user_id}'),
                        'first_name': getattr(request.user, 'first_name', ''),
                        'last_name': getattr(request.user, 'last_name', '')
                    },
                    'metadata': message.metadata
                }
                
                if parent_id:
                    response_data['parent'] = parent_id
                
                # Get the channel layer and broadcast the message
                channel_layer = get_channel_layer()
                
                # Broadcast to the channel's group
                async_to_sync(channel_layer.group_send)(
                    f"chat_{channel_pk}",
                    {
                        "type": "chat.message",  # This maps to the `chat_message` method in the consumer
                        "payload": {
                            "event_type": "message.new",
                            "payload": response_data
                        }
                    }
                )
                
                logger.info(f"Message {message.id} created and broadcast to channel {channel_pk}")
                
                # Return the response
                return Response(response_data, status=status.HTTP_201_CREATED)
                
            except ChatChannel.DoesNotExist:
                logger.error(f"Channel {channel_pk} not found")
                return Response({"error": "Channel not found"}, status=status.HTTP_404_NOT_FOUND)
            except Exception as e:
                logger.error(f"Error creating/broadcasting message: {str(e)}", exc_info=True)
                return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)