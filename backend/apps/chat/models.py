# apps/chat/models.py

import uuid
from django.db import models
from django.conf import settings
from apps.common.models import BaseTenantModel

class ChatChannel(BaseTenantModel):
    class ChannelType(models.TextChoices):
        DIRECT = 'direct', 'Direct Message'
        GROUP = 'group', 'Group'
        CONTEXTUAL = 'contextual_object', 'Contextual Object'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices, default=ChannelType.GROUP)
    name = models.CharField(max_length=255, blank=True, null=True)
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, through='ChannelParticipant', through_fields=('channel', 'user'), related_name='chat_channels')
    
    # Fields for uniquely identifying the context
    host_application_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    context_object_type = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    context_object_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)

    def __str__(self):
        return self.name or str(self.id)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['host_application_id', 'context_object_type', 'context_object_id'],
                name='unique_contextual_chat'
            )
        ]
        verbose_name = "Chat Channel"
        verbose_name_plural = "Chat Channels"

class ChannelParticipant(BaseTenantModel):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Admin'
        MEMBER = 'member', 'Member'
        GUEST = 'guest', 'Guest' # For Phase 2

    class UserType(models.TextChoices):
        INTERNAL = 'internal', 'Internal'
        GUEST = 'guest', 'Guest' # For Phase 2
        
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='channel_participations')
    channel = models.ForeignKey(ChatChannel, on_delete=models.CASCADE, related_name='participations')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.MEMBER)
    user_type = models.CharField(max_length=10, choices=UserType.choices, default=UserType.INTERNAL)

    class Meta:
        unique_together = ('user', 'channel')
        verbose_name = "Channel Participant"
        verbose_name_plural = "Channel Participants"

class Message(BaseTenantModel):
    id = models.BigAutoField(primary_key=True)
    channel = models.ForeignKey(ChatChannel, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='replies') # For Phase 2 Threading
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = "Message"
        verbose_name_plural = "Messages"

class UserChannelState(BaseTenantModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='chat_channel_states')
    channel = models.ForeignKey(ChatChannel, on_delete=models.CASCADE, related_name='user_states')
    last_read_message_id = models.BigIntegerField(null=True, blank=True)
    is_muted = models.BooleanField(default=False)

    class Meta:
        unique_together = ('user', 'channel')
        verbose_name = "User Channel State"
        verbose_name_plural = "User Channel States"

class Device(BaseTenantModel):
    class DeviceType(models.TextChoices):
        ANDROID = 'android', 'Android'
        IOS = 'ios', 'iOS'
        WEB = 'web', 'Web'
        
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_devices')
    token = models.CharField(max_length=255, unique=True)
    device_type = models.CharField(max_length=10, choices=DeviceType.choices)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices"
