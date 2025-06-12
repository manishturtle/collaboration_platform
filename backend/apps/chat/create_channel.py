"""
Direct channel creation implementation that avoids ORM constraints
and works with tenant-specific user tables.
"""
import uuid
import logging
from typing import List, Any, Optional
from django.utils import timezone
from django.db import connection
from django_tenants.utils import schema_context
from .tenant_utils import execute_in_tenant_schema
from .check_user_exists import check_user_exists

logger = logging.getLogger(__name__)


def create_tenant_channel(
    name: str,
    user_id: int,
    participants: List[int],
    is_contextual_chat: bool = False,
    host_application_id: Optional[str] = None,
    context_object_type: Optional[str] = None,
    context_object_id: Optional[str] = None,
    schema_name: str = "public"
) -> dict:
    """
    Creates a new chat channel using raw SQL to bypass ORM constraints.
    Works directly with tenant-specific user tables.
    
    Args:
        name: Channel name
        user_id: ID of the user creating the channel (from JWT token)
        participants: List of user IDs to add (from tenant user table)
        is_contextual_chat: Whether this is a contextual object chat
        host_application_id: For contextual chat - host application identifier
        context_object_type: For contextual chat - type of the context object
        context_object_id: For contextual chat - ID of the context object
        schema_name: Name of the tenant schema to use
        
    Returns:
        Dictionary with channel details including ID
    """
    # Default to turtlesoftware if no schema specified
    if not schema_name or schema_name == "public":
        schema_name = "turtlesoftware"
    
    # Generate values needed outside the schema context
    channel_id = str(uuid.uuid4())
    now = timezone.now().isoformat()
    
    # Determine channel type
    if is_contextual_chat:
        channel_type = 'contextual_object'
    else:
        # For regular chats, direct if 2 participants, group otherwise
        participant_count = len(set(participants)) + 1  # +1 for creator
        channel_type = 'direct' if participant_count == 2 else 'group'
    
    logger.info(f"Creating {channel_type} channel in schema '{schema_name}' with ID {channel_id}")
    
    try:
        # Use django-tenants schema_context to ensure operations run in the correct schema
        with schema_context(schema_name):
            # First verify the user exists
            with connection.cursor() as cursor:
                # Check if user exists in tenant user table
                cursor.execute("""
                    SELECT EXISTS(
                        SELECT 1 FROM ecomm_tenant_admins_tenantuser WHERE id = %s
                    )
                """, [user_id])
                user_exists = cursor.fetchone()[0]
                
                if not user_exists:
                    logger.error(f"User {user_id} not found in schema {schema_name}")
                    raise ValueError(f"User {user_id} not found in tenant schema {schema_name}")
            
            # Check if we already have a matching contextual chat
            if is_contextual_chat and all([host_application_id, context_object_type, context_object_id]):
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT id, name, channel_type, created_at 
                        FROM chat_chatchannel 
                        WHERE host_application_id = %s 
                        AND context_object_type = %s 
                        AND context_object_id = %s
                        LIMIT 1
                    """, [host_application_id, context_object_type, context_object_id])
                    
                    existing = cursor.fetchone()
                    if existing:
                        logger.info(f"Found existing contextual channel: {existing[0]}")
                        return {
                            'id': existing[0],
                            'name': existing[1],
                            'channel_type': existing[2],
                            'created_at': existing[3],
                            'is_existing': True
                        }
    
            # Create channel with raw SQL directly in the tenant schema
            with connection.cursor() as cursor:
                # Hardcoded tenant IDs, should be replaced later
                client_id = 1
                company_id = 1
                
                # Create the channel - matching the actual database schema
                cursor.execute("""
                    INSERT INTO chat_chatchannel (
                        id, name, channel_type, 
                        created_at, updated_at, 
                        context_object_id, 
                        context_object_type, host_application_id,
                        created_by_id, updated_by_id,
                        client_id, company_id
                    ) VALUES (
                        %s, %s, %s, 
                        %s, %s, 
                        %s, 
                        %s, %s,
                        %s, %s,
                        %s, %s
                    ) RETURNING id
                """, [
                    channel_id, name, channel_type,
                    now, now,
                    context_object_id,
                    context_object_type, host_application_id,
                    user_id, user_id,
                    client_id, company_id
                ])
                
                # Get next participant ID from sequence
                cursor.execute("SELECT nextval('chat_channelparticipant_id_seq')")
                participant_id = cursor.fetchone()[0]
                
                # Add creator as participant - admin role
                cursor.execute("""
                    INSERT INTO chat_channelparticipant (
                        id, channel_id, user_id, 
                        role, user_type, created_at, updated_at,
                        created_by_id, updated_by_id,
                        client_id, company_id
                    ) VALUES (
                        %s, %s, %s, 
                        %s, %s, %s, %s,
                        %s, %s,
                        %s, %s
                    )
                """, [
                    participant_id, channel_id, user_id,
                    'admin', 'internal', now, now, 
                    user_id, user_id,
                    client_id, company_id
                ])
                
                # Add other participants to channel
                if participants:
                    for p_user_id in participants:
                        # Skip if participant is the creator
                        if int(p_user_id) == int(user_id):
                            continue
                        
                        try:
                            # First check if participant user exists
                            cursor.execute("""
                                SELECT EXISTS(SELECT 1 FROM ecomm_tenant_admins_tenantuser WHERE id = %s)
                            """, [p_user_id])
                            if cursor.fetchone()[0]:
                                # Get next participant ID from sequence
                                cursor.execute("SELECT nextval('chat_channelparticipant_id_seq')")
                                p_id = cursor.fetchone()[0]
                                
                                # Add participant as member
                                cursor.execute("""
                                    INSERT INTO chat_channelparticipant (
                                        id, channel_id, user_id, 
                                        role, user_type, created_at, updated_at,
                                        created_by_id, updated_by_id,
                                        client_id, company_id
                                    ) VALUES (
                                        %s, %s, %s, 
                                        %s, %s, %s, %s,
                                        %s, %s,
                                        %s, %s
                                    )
                                """, [
                                    p_id, channel_id, p_user_id,
                                    'member', 'internal', now, now,
                                    user_id, user_id,
                                    client_id, company_id
                                ])
                                logger.info(f"Added participant {p_user_id} to channel {channel_id}")
                            else:
                                logger.warning(f"Participant {p_user_id} not found in schema {schema_name}, skipping")
                        except Exception as e:
                            logger.error(f"Error adding participant {p_user_id}: {str(e)}")
                            # Continue with other participants
                    
            # Return channel details
            return {
                'id': channel_id,
                'name': name,
                'channel_type': channel_type,
                'created_at': now,
                'is_existing': False
            }
            
    except Exception as e:
        logger.error(f"Error creating channel in schema {schema_name}: {str(e)}")
        raise ValueError(f"Failed to create channel in tenant schema {schema_name}: {str(e)}")
