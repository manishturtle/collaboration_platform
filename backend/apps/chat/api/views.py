# apps/chat/api/views.py

from rest_framework import viewsets, mixins, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import ChatChannel
from .serializers import ChatChannelSerializer
from ..selectors import get_channels_for_user
from ..services import create_channel

class ChannelViewSet(mixins.ListModelMixin,
                     mixins.CreateModelMixin,
                     mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    A ViewSet for listing, retrieving, and creating Chat Channels.
    """
    serializer_class = ChatChannelSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all the channels
        for the currently authenticated user.
        """
        return get_channels_for_user(user=self.request.user)

    def perform_create(self, serializer):
        """
        Overrides the default create behavior to use our service function.
        """
        # The service function handles adding the creator to the participant list.
        channel = create_channel(
            user=self.request.user,
            name=serializer.validated_data.get('name'),
            participants=serializer.validated_data.get('participants', [])
        )
        # We need to return the created channel object for the serializer to render it.
        # The serializer instance passed to perform_create doesn't have an object yet.
        # So we create a new serializer instance with the channel object.
        return Response(self.get_serializer(channel).data, status=status.HTTP_201_CREATED)

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
