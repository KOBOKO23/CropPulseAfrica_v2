# apps/accounts/urls.py

from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    UserProfileView,
    PasswordChangeView,
    VerifyPhoneView,
    SendVerificationCodeView,
    UserListView,
    UserDetailView,
    check_auth_status,
    deactivate_account,
    user_statistics
)

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('status/', check_auth_status, name='auth_status'),
    
    # User Profile
    path('profile/', UserProfileView.as_view(), name='user_profile'),
    path('password/change/', PasswordChangeView.as_view(), name='password_change'),
    path('deactivate/', deactivate_account, name='deactivate_account'),
    
    # Phone Verification
    path('verify-phone/', VerifyPhoneView.as_view(), name='verify_phone'),
    path('send-verification-code/', SendVerificationCodeView.as_view(), name='send_verification_code'),
    
    # User Management (Admin)
    path('users/', UserListView.as_view(), name='user_list'),
    path('users/<int:id>/', UserDetailView.as_view(), name='user_detail'),
    path('statistics/', user_statistics, name='user_statistics'),
]