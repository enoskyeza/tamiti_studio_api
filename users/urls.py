# users/urls.py
from django.urls import path


from users.views import RegisterView, LoginView, VerifyEmailView, PasswordResetRequestView, PasswordResetConfirmView, \
    CurrentUserView, CookieTokenRefreshView, LogoutView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('password-reset-request/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('password-reset-confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path("token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path('me/', CurrentUserView.as_view(), name='current-user'),
]

