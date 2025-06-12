# apps/chat/models.py

import uuid
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from django_tenants.models import TenantMixin, DomainMixin
from apps.common.models import BaseTenantModel

class ChatChannel(BaseTenantModel):
    class ChannelType(models.TextChoices):
        DIRECT = 'direct', 'Direct Message'
        GROUP = 'group', 'Group'
        CONTEXTUAL = 'contextual_object', 'Contextual Object'

    # Explicitly define all fields to match the database schema
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    channel_type = models.CharField(max_length=20, choices=ChannelType.choices, default=ChannelType.GROUP)
    name = models.CharField(max_length=255, blank=True, null=True)
    
    # Fields for uniquely identifying the context
    host_application_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    context_object_type = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    context_object_id = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    
    # Timestamps from BaseTenantModel
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    # User references - match the database column names
    created_by_id = models.IntegerField(null=True, blank=True, db_column='created_by_id')
    updated_by_id = models.IntegerField(null=True, blank=True, db_column='updated_by_id')
    
    # Required fields from BaseTenantModel
    company_id = models.IntegerField(default=1, editable=False)
    client_id = models.IntegerField(default=1, editable=False)
    
    # ManyToMany field for participants
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        through='ChannelParticipant', 
        through_fields=('channel', 'user'), 
        related_name='chat_channels'
    )

    def __str__(self):
        return self.name or str(self.id)
    
    class Meta:
        db_table = 'chat_chatchannel'  # Explicitly set the table name
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
    
    # Timestamps from BaseTenantModel
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    # User references - match the database column names
    created_by_id = models.IntegerField(null=True, blank=True, db_column='created_by_id')
    updated_by_id = models.IntegerField(null=True, blank=True, db_column='updated_by_id')
    
    # Required fields from BaseTenantModel
    company_id = models.IntegerField(default=1, editable=False)
    client_id = models.IntegerField(default=1, editable=False)

    class Meta:
        db_table = 'chat_channelparticipant'  # Explicitly set the table name
        unique_together = ('user', 'channel')
        verbose_name = "Channel Participant"
        verbose_name_plural = "Channel Participants"

class ChatMessage(BaseTenantModel):
    """
    Model for storing chat messages in a multi-tenant environment.
    Each message belongs to a specific channel and is sent by a user.
    """
    id = models.BigAutoField(primary_key=True)
    channel = models.ForeignKey(
        'ChatChannel',
        on_delete=models.CASCADE,
        related_name='messages',
        db_index=True
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_messages',
        db_index=True
    )
    content = models.TextField()
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='replies',
        db_index=True
    )
    metadata = models.JSONField(default=dict, blank=True)
    # is_edited = models.BooleanField(default=False)
    # is_deleted = models.BooleanField(default=False)
    # deleted_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps from BaseTenantModel
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    # User references - match the database column names
    created_by_id = models.IntegerField(null=True, blank=True, db_column='created_by_id')
    updated_by_id = models.IntegerField(null=True, blank=True, db_column='updated_by_id')
    
    # Required fields from BaseTenantModel
    company_id = models.IntegerField(default=1, editable=False)
    client_id = models.IntegerField(default=1, editable=False)
    
    read_by = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='MessageReadStatus',
        related_name='read_messages',
        blank=True
    )

    class Meta:
        db_table = 'chat_message'  # Changed from chat_chatmessage to chat_message
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['channel', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]
        verbose_name = "Chat Message"
        verbose_name_plural = "Chat Messages"

    def __str__(self):
        return f"{self.user.username}: {self.content[:50]}"

    def mark_as_deleted(self):
        """Mark the message as deleted without actually deleting it.
        Note: This functionality is currently disabled as the fields don't exist in the database.
        """
        from django.core.exceptions import FieldError
        import logging
        logger = logging.getLogger(__name__)
        logger.warning("mark_as_deleted called but fields do not exist in database")
        # self.is_deleted = True
        # self.deleted_at = timezone.now()
        # self.save(update_fields=['is_deleted', 'deleted_at', 'updated_at'])

class MessageReadStatus(BaseTenantModel):
    """
    Tracks which users have read which messages.
    """
    message = models.ForeignKey('ChatMessage', on_delete=models.CASCADE, related_name='read_statuses')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='message_reads')
    read_at = models.DateTimeField(auto_now_add=True)
    
    # Timestamps from BaseTenantModel
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    
    # User references - match the database column names
    created_by_id = models.IntegerField(null=True, blank=True, db_column='created_by_id')
    updated_by_id = models.IntegerField(null=True, blank=True, db_column='updated_by_id')
    
    # Required fields from BaseTenantModel
    company_id = models.IntegerField(default=1, editable=False)
    client_id = models.IntegerField(default=1, editable=False)

    class Meta:
        db_table = 'chat_messagereadstatus'  # Explicitly set the table name
        unique_together = ('message', 'user')
        verbose_name = 'Message Read Status'
        verbose_name_plural = 'Message Read Statuses'

    def __str__(self):
        return f"{self.user.username} read message {self.message_id}"

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
