# apps/chat/api/serializers.py

from django.contrib.auth import get_user_model
from rest_framework import serializers
from ..models import ChatChannel, ChannelParticipant

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
    """
    # Use the participant serializer for a nested representation of participants
    participations = serializers.SerializerMethodField()
    # A write-only field to accept a list of user IDs when creating a channel
    participants = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        write_only=True,
        required=True
    )
    
    def get_participations(self, obj):
        """Get all participants with their roles for this channel"""
        participants = ChannelParticipant.objects.filter(channel=obj)
        return ChannelParticipantSerializer(participants, many=True).data

    class Meta:
        model = ChatChannel
        fields = [
            'id',
            'name',
            'channel_type',
            'participations',
            'participants', # for write operations
            'created_at',
            'context_object_id',
            'context_object_type',
        ]
        read_only_fields = ['id', 'channel_type', 'created_at']
