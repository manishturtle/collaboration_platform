# apps/chat/services.py

from typing import List
from django.db import transaction
from django.contrib.auth import get_user_model
from .models import ChatChannel, ChannelParticipant

User = get_user_model()

@transaction.atomic
def create_channel(*, user: User, name: str = None, participants: List[User]) -> ChatChannel:
    """
    Creates a new chat channel and adds participants.
    The creator is automatically made an admin.
    
    Raises:
        ValueError: If no participants are provided
    """
    # Validate that participants are provided
    if not participants:
        raise ValueError("At least one participant is required to create a channel")
        
    # Ensure all participants exist and add the creator to the list
    all_participants = set(participants)
    all_participants.add(user)

    # Determine channel type
    channel_type = ChatChannel.ChannelType.DIRECT if len(all_participants) == 2 else ChatChannel.ChannelType.GROUP
    
    # For a direct chat, a name is not needed.
    if channel_type == ChatChannel.ChannelType.DIRECT:
        name = None

    new_channel = ChatChannel.objects.create(
        created_by=user,
        name=name,
        channel_type=channel_type
    )

    # Create participant entries
    participant_objects = []
    for p_user in all_participants:
        role = ChannelParticipant.Role.ADMIN if p_user == user else ChannelParticipant.Role.MEMBER
        participant_objects.append(
            ChannelParticipant(
                channel=new_channel,
                user=p_user,
                created_by=user,
                role=role
            )
        )
    
    ChannelParticipant.objects.bulk_create(participant_objects)
    
    return new_channel
