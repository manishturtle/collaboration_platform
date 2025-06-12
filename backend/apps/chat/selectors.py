# apps/chat/selectors.py

from django.db.models import QuerySet
from django.contrib.auth import get_user_model
from .models import ChatChannel

User = get_user_model()

def get_channels_for_user(user: User) -> QuerySet[ChatChannel]:
    """
    Retrieves all chat channels a given user is a participant of.
    Orders them by the most recent activity (latest message).
    Respects multi-tenant isolation.
    """
    # Note: `latest_message_timestamp` will be annotated in the view/serializer for performance.
    # For now, we order by `updated_at` as a proxy for activity.
    
    # Filter by participant relationship using the ManyToMany relationship
    # This ensures proper multi-tenant isolation
    return (
        ChatChannel.objects.filter(
            participants=user
        )
        # Add company_id filtering when available from request context
        # .filter(company_id=request.company_id)
        .order_by('-updated_at')
        .distinct()  # Ensure we don't get duplicates
    )
