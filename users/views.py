# users/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, TokenError
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework import serializers as drf_serializers
import logging
from django.utils import timezone

from config.settings import base
from django.conf import settings
from users.serializers import RegisterSerializer, LoginSerializer, PasswordResetRequestSerializer, \
    PasswordResetConfirmSerializer, UserSerializer
from users.tokens import account_activation_token, decode_uid
from users.models import User
from users.utils import send_password_reset_email
from django.contrib.auth import authenticate


logger = logging.getLogger(__name__)

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }


class CookieTokenRefreshView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = drf_serializers.Serializer

    def post(self, request):
        logger.info(f"🔵 [TOKEN REFRESH] Refresh attempt started", extra={
            'timestamp': timezone.now().isoformat(),
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'cookies_present': list(request.COOKIES.keys()),
            'has_refresh_cookie': 'refresh_token' in request.COOKIES,
        })
        
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            logger.warning(f"🔴 [TOKEN REFRESH] No refresh token in cookies", extra={
                'timestamp': timezone.now().isoformat(),
                'available_cookies': list(request.COOKIES.keys()),
            })
            return Response({'error': 'Refresh token not found'}, status=400)

        try:
            logger.info(f"🔵 [TOKEN REFRESH] Validating refresh token", extra={
                'timestamp': timezone.now().isoformat(),
                'token_preview': refresh_token[:20] + '...',
                'token_length': len(refresh_token),
            })
            
            refresh = RefreshToken(refresh_token)
            user = refresh.get_user()
            
            logger.info(f"🟢 [TOKEN REFRESH] Token validation successful", extra={
                'timestamp': timezone.now().isoformat(),
                'user_id': user.id,
                'username': user.username,
            })
            
            # Generate new access token
            new_access_token = str(refresh.access_token)
            
            logger.info(f"🟢 [TOKEN REFRESH] New access token generated", extra={
                'timestamp': timezone.now().isoformat(),
                'user_id': user.id,
                'new_token_length': len(new_access_token),
                'new_token_preview': new_access_token[:20] + '...',
            })

            # Create response with new refresh token
            new_refresh = RefreshToken.for_user(user)
            new_refresh_token = str(new_refresh)
            
            response = Response({
                'access': new_access_token,
            })

            # Set new refresh token cookie
            cookie_max_age = 7 * 24 * 60 * 60  # 7 days
            response.set_cookie(
                'refresh_token',
                new_refresh_token,
                httponly=True,
                secure=not base.DEBUG,
                samesite="None" if not base.DEBUG else "Lax",
                domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                max_age=cookie_max_age,
                path='/'
            )
            
            logger.info(f"🟢 [TOKEN REFRESH] Response prepared with new tokens", extra={
                'timestamp': timezone.now().isoformat(),
                'user_id': user.id,
                'new_refresh_preview': new_refresh_token[:20] + '...',
                'cookie_domain': getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
            })

            return response

        except TokenError as e:
            logger.warning(f"🔴 [TOKEN REFRESH] Token validation failed", extra={
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'token_preview': refresh_token[:20] + '...',
            })
            return Response({'error': 'Invalid or expired refresh token'}, status=400)
        except Exception as e:
            logger.error(f"🔴 [TOKEN REFRESH] Unexpected error", extra={
                'timestamp': timezone.now().isoformat(),
                'error': str(e),
                'error_type': type(e).__name__,
            })
            return Response({'error': 'Token refresh failed'}, status=500)


class CurrentUserView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):
        logger.info(f"🔵 [USER ME] Request started", extra={
            'timestamp': timezone.now().isoformat(),
            'user_id': request.user.id if request.user.is_authenticated else None,
            'username': request.user.username if request.user.is_authenticated else None,
            'is_authenticated': request.user.is_authenticated,
            'auth_header_present': 'HTTP_AUTHORIZATION' in request.META,
            'ip_address': request.META.get('REMOTE_ADDR'),
        })
        
        if not request.user.is_authenticated:
            logger.warning(f"🔴 [USER ME] User not authenticated", extra={
                'timestamp': timezone.now().isoformat(),
                'auth_header_present': 'HTTP_AUTHORIZATION' in request.META,
            })
            return Response({'error': 'Authentication required'}, status=401)
        
        user_data = {
            'id': request.user.id,
            'username': request.user.username,
            'email': request.user.email,
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'is_staff': request.user.is_staff,
            'is_superuser': request.user.is_superuser,
        }
        
        logger.info(f"🟢 [USER ME] Response prepared", extra={
            'timestamp': timezone.now().isoformat(),
            'user_id': request.user.id,
            'username': request.user.username,
            'response_keys': list(user_data.keys()),
        })
        
        return Response(user_data)


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        # You can trigger email verification here
        # send_verification_email(user, self.request)
        return user


class LoginView(generics.GenericAPIView):
    serializer_class = LoginSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        logger.info(f"🔵 [AUTH LOGIN] Login attempt started", extra={
            'timestamp': timezone.now().isoformat(),
            'ip_address': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'request_data_keys': list(request.data.keys()),
            'has_username': 'username' in request.data,
            'has_password': 'password' in request.data,
        })
        
        username = request.data.get('username')
        password = request.data.get('password')

        if not username or not password:
            logger.warning(f"🔴 [AUTH LOGIN] Missing credentials", extra={
                'timestamp': timezone.now().isoformat(),
                'has_username': bool(username),
                'has_password': bool(password),
            })
            return Response({'error': 'Username and password required'}, status=400)

        user = authenticate(request, username=username, password=password)
        if user:
            logger.info(f"🟢 [AUTH LOGIN] Authentication successful", extra={
                'timestamp': timezone.now().isoformat(),
                'user_id': user.id,
                'username': user.username,
                'is_active': user.is_active,
            })
            
            # Generate tokens
            refresh = RefreshToken.for_user(user)
            access_token = str(refresh.access_token)
            refresh_token = str(refresh)
            
            logger.info(f"🟢 [AUTH LOGIN] Tokens generated", extra={
                'timestamp': timezone.now().isoformat(),
                'user_id': user.id,
                'access_token_length': len(access_token),
                'refresh_token_length': len(refresh_token),
                'access_preview': access_token[:20] + '...',
                'refresh_preview': refresh_token[:20] + '...',
            })

            # Create response
            response = Response({
                'access': access_token,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'is_staff': user.is_staff,
                    'is_superuser': user.is_superuser,
                }
            })

            # Set refresh token cookie
            cookie_max_age = 7 * 24 * 60 * 60  # 7 days
            response.set_cookie(
                'refresh_token',
                refresh_token,
                max_age=cookie_max_age,
                httponly=True,
                secure=not base.DEBUG,
                samesite="None" if not base.DEBUG else "Lax",
                domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                max_age=24 * 60 * 60,
                path='/'
            )
            
            logger.info(f"🟢 [AUTH LOGIN] Response prepared with cookie", extra={
                'timestamp': timezone.now().isoformat(),
                'user_id': user.id,
                'cookie_domain': getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
                'cookie_secure': not base.DEBUG,
                'cookie_samesite': "None" if not base.DEBUG else "Lax",
                'cookie_max_age': cookie_max_age,
            })

            return response
        else:
            logger.warning(f"🔴 [AUTH LOGIN] Authentication failed", extra={
                'timestamp': timezone.now().isoformat(),
                'username': username,
                'ip_address': request.META.get('REMOTE_ADDR'),
            })
            return Response({'error': 'Invalid credentials'}, status=401)


class VerifyEmailView(APIView):

    @extend_schema(
        parameters=[
            OpenApiParameter(name="uid", type=str, location=OpenApiParameter.QUERY),
            OpenApiParameter(name="token", type=str, location=OpenApiParameter.QUERY),
        ],
        responses={
            200: OpenApiResponse(description="Email verified successfully"),
            400: OpenApiResponse(description="Invalid link or token"),
            404: OpenApiResponse(description="Invalid user"),
        },
    )
    def get(self, request):
        uid = decode_uid(request.GET.get('uid'))
        token = request.GET.get('token')

        if not uid or not token:
            return Response({"detail": "Invalid link"}, status=400)

        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            return Response({"detail": "Invalid user"}, status=404)

        if account_activation_token.check_token(user, token):
            user.is_verified = True
            user.save()
            return Response({"detail": "Email verified successfully"}, status=200)

        return Response({"detail": "Invalid or expired token"}, status=400)


class PasswordResetRequestView(generics.GenericAPIView):
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.get(email=serializer.validated_data['email'])
        send_password_reset_email(user, request)
        return Response({"detail": "Password reset email sent"}, status=200)


class PasswordResetConfirmView(generics.GenericAPIView):
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": "Password reset successful"}, status=200)
