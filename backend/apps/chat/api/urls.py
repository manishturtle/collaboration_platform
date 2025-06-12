# apps/chat/api/urls.py

from rest_framework.routers import DefaultRouter
from .views import ChannelViewSet

router = DefaultRouter()
router.register(r'channels', ChannelViewSet, basename='channel')

urlpatterns = router.urls
