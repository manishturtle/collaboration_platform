# apps/chat/services.py

import uuid
from typing import List, Any, Union
from django.db import transaction, connection
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from .models import ChatChannel

User = get_user_model()

@transaction.atomic
def create_channel(
    name: str,
    user_id: Any,
    participants: List[Any],
    is_contextual_chat: bool = False,
    host_application_id: str = None,
    context_object_type: str = None,
    context_object_id: str = None,
    tenant_schema: str = None
) -> ChatChannel:
    """
    Creates a new chat channel and adds participants.
    The creator is automatically made an admin.
    
    Args:
        name: Optional channel name
        participants: List of user IDs to add as participants
    
    Raises:
        ValueError: If no participants are provided
    """
    # Validate that participants are provided
    if not participants:
        raise ValueError("At least one participant is required to create a channel")
    
    # Get user ID from either User instance or SimpleTenantUser
    user_id = getattr(user, 'id', None) or getattr(user, '_user_id', None)
    if not user_id:
        raise ValueError("Cannot determine user ID from the provided user object")
    
    # Convert all IDs to integers for consistent comparison
    user_id = int(user_id)
    
    # Add creator to participants if not already present (avoiding duplicates)
    all_participant_ids = set(int(p) for p in participants)
    
    # Only add the user if they're not already in the participants list
    if user_id not in all_participant_ids:
        all_participant_ids.add(user_id)
        
    # Determine channel type based on context
    if is_contextual_chat:
        channel_type = ChatChannel.ChannelType.CONTEXTUAL
    else:
        # For regular chats, type depends on participant count
        channel_type = ChatChannel.ChannelType.DIRECT if len(all_participant_ids) == 2 else ChatChannel.ChannelType.GROUP
    
    # For direct chats, name is not needed
    if channel_type == ChatChannel.ChannelType.DIRECT:
        name = None

    # Create the channel
    channel_data = {
        'name': name,
        'channel_type': channel_type,
        'created_by_id': user_id,  # Set created_by directly with user ID
        'updated_by_id': user_id,  # Set updated_by directly with user ID
        'client_id': 1,            # Hardcoded tenant value
        'company_id': 1,           # Hardcoded tenant value
    }
    
    # Add contextual object fields if applicable
    if is_contextual_chat:
        # For contextual chats, require the context fields
        if not all([host_application_id, context_object_type, context_object_id]):
            raise ValueError("Contextual chats require host_application_id, context_object_type, and context_object_id")
            
        # Check if a channel for this contextual object already exists
        existing_channel = ChatChannel.objects.filter(
            host_application_id=host_application_id,
            context_object_type=context_object_type,
            context_object_id=context_object_id
        ).first()
        
        if existing_channel:
            # Return the existing channel instead of creating a new one
            return existing_channel
            
        # Set contextual fields only for contextual chats
        channel_data.update({
            'host_application_id': host_application_id,
            'context_object_type': context_object_type,
            'context_object_id': context_object_id,
        })
    else:
        # For regular chats, ensure contextual fields are null
        channel_data.update({
            'host_application_id': None,
            'context_object_type': None,
            'context_object_id': None,
        })
    
    # Create the channel object
    new_channel = ChatChannel.objects.create(**channel_data)

    # Create participant entries using raw SQL to bypass Django ORM's User model constraint
    now = timezone.now()
    with connection.cursor() as cursor:
        for participant_id in all_participant_ids:
            role = 'admin' if int(participant_id) == int(user_id) else 'member'
            user_type = 'internal'  # Default to internal users
            
            # Insert participant relationship using raw SQL
            # Note: We don't specify 'id' since it's an auto-increment field
            cursor.execute("""
                INSERT INTO chat_channelparticipant 
                (channel_id, user_id, role, user_type, created_at, updated_at, created_by_id, updated_by_id, client_id, company_id) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (channel_id, user_id) DO NOTHING
            """, [
                new_channel.id,               # Channel ID 
                participant_id,               # User ID
                role,                         # Role (admin/member)
                user_type,                    # User type
                now,                          # created_at
                now,                          # updated_at
                user_id,                      # created_by_id
                user_id,                      # updated_by_id
                1,                            # client_id (hardcoded value 1)
                1                             # company_id (hardcoded value 1)
            ])
    
    
    return new_channel
