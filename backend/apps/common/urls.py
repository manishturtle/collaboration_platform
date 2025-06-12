from django.urls import path
from apps.common.auth_views import AuthenticateUserView

urlpatterns = [
    path('auth/login/', AuthenticateUserView.as_view(), name='auth-login'),
]
