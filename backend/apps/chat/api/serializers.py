# apps/chat/api/serializers.py

from django.contrib.auth import get_user_model
from django_tenants.utils import schema_context
from rest_framework import serializers
from ..models import ChatChannel, ChannelParticipant, ChatMessage

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    A simple serializer for nested user representation.
    """
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name'] # Add avatar_url later if available


class ChannelParticipantSerializer(serializers.ModelSerializer):
    """
    Serializer for the through-model ChannelParticipant.
    """
    user = UserSerializer(read_only=True)

    class Meta:
        model = ChannelParticipant
        fields = ['user', 'role']


class ChatChannelSerializer(serializers.ModelSerializer):
    """
    Serializer for the ChatChannel model.
    Supports both direct/group chats and contextual object chats.
    """
    # Use the participant serializer for a nested representation of participants
    participations = serializers.SerializerMethodField()
    
    # A write-only field to accept a list of user IDs when creating a channel
    participants = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=True
    )
    
    # Additional fields for contextual object chats
    is_contextual_chat = serializers.BooleanField(write_only=True, required=False, default=False)
    host_application_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    context_object_type = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    context_object_id = serializers.CharField(required=False, allow_null=True, allow_blank=True, default=None)
    
    def get_participations(self, obj):
        """Get all participants with their roles for this channel"""
        participants = ChannelParticipant.objects.filter(channel=obj)
        return ChannelParticipantSerializer(participants, many=True).data

    class Meta:
        model = ChatChannel
        fields = [
            # Standard fields
            'id',
            'name',
            'channel_type',
            'participations',
            'participants',  # for write operations
            'created_at',
            
            # Contextual object fields
            'is_contextual_chat',  # Flag for API to know this is a contextual chat
            'host_application_id',
            'context_object_type',
            'context_object_id',
        ]
        read_only_fields = ['id', 'channel_type', 'created_at']


class MessageSerializer(serializers.ModelSerializer):
    """Serializer for the ChatMessage model."""
    user = UserSerializer(read_only=True)
    user_id = serializers.PrimaryKeyRelatedField(
        source='user',
        queryset=User.objects.all(),
        write_only=True,
        required=False
    )
    channel = serializers.PrimaryKeyRelatedField(queryset=ChatChannel.objects.all(), required=False)

    class Meta:
        model = ChatMessage
        fields = ['id', 'channel', 'user', 'user_id', 'content', 'created_at', 'parent', 'metadata']
        read_only_fields = ['id', 'user', 'created_at', 'channel']
    
    def create(self, validated_data):
        request = self.context.get('request')
        from .views import get_schema_name
        schema_name = get_schema_name(request)
        
        with schema_context(schema_name):
            # Get channel from URL if not in data
            if 'channel' not in validated_data:
                view = self.context.get('view')
                if view and hasattr(view, 'kwargs') and 'channel_pk' in view.kwargs:
                    channel_pk = view.kwargs['channel_pk']
                    validated_data['channel'] = ChatChannel.objects.get(pk=channel_pk)
            
            # Set the current user as the message author
            if request and hasattr(request, 'user') and request.user.is_authenticated:
                validated_data['user'] = request.user
            
            # Set created_by_id and updated_by_id
            if 'user' in validated_data:
                validated_data['created_by_id'] = validated_data['user'].id
                validated_data['updated_by_id'] = validated_data['user'].id
            
            return super().create(validated_data)
        
    def validate(self, data):
        """
        Validate that the user has permission to post to this channel.
        """
        request = self.context.get('request')
        channel = data.get('channel')
        
        from .views import get_schema_name
        schema_name = get_schema_name(request)
        
        # If channel is not in data, try to get it from URL
        if not channel and 'channel_pk' in self.context.get('view').kwargs:
            try:
                with schema_context(schema_name):
                    channel = ChatChannel.objects.get(pk=self.context['view'].kwargs['channel_pk'])
                    data['channel'] = channel
            except (ChatChannel.DoesNotExist, ValueError):
                raise serializers.ValidationError({"channel": "Invalid channel ID"})
        
        if request and hasattr(request, 'user') and channel:
            with schema_context(schema_name):
                # Check if user is a participant in the channel
                if not ChannelParticipant.objects.filter(
                    channel=channel,
                    user=request.user
                ).exists():
                    raise serializers.ValidationError(
                        "You don't have permission to post in this channel."
                    )
        return data