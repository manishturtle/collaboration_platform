# apps/chat/api/urls.py

from rest_framework_nested import routers
from django.urls import path, include
from .views import ChannelViewSet, MessageViewSet

# Create a router for channels
router = routers.SimpleRouter()
router.register(r'channels', ChannelViewSet, basename='channel')

# Create a nested router for messages within channels
channel_router = routers.NestedSimpleRouter(router, r'channels', lookup='channel')
channel_router.register(r'messages', MessageViewSet, basename='channel-messages')

# The API URLs are now determined automatically by the routers
urlpatterns = [
    path('', include(router.urls)),
    path('', include(channel_router.urls)),
]