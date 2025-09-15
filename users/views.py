# users/views.py
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken, TokenError
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework import serializers as drf_serializers


from config.settings import base
from django.conf import settings
from users.serializers import RegisterSerializer, LoginSerializer, PasswordResetRequestSerializer, \
    PasswordResetConfirmSerializer, UserSerializer
from users.tokens import account_activation_token, decode_uid
from users.models import User
from users.utils import send_password_reset_email

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
        print("\n========== 🔁 REFRESH TOKEN ATTEMPT ==========")
        refresh_token = request.COOKIES.get('refresh_token')

        if not refresh_token:
            print("🚫 No refresh token found in cookies.")
            print("========== ❌ REFRESH FAILED ❌ ==========\n")
            return Response(
                {"error": "No refresh token in cookies"},
                status=status.HTTP_400_BAD_REQUEST
            )

        print("🍪 Received refresh token from cookie:", refresh_token)

        try:
            refresh = RefreshToken(refresh_token)
        except TokenError as e:
            print("❌ Refresh token error:", str(e))
            print("========== ❌ REFRESH FAILED ❌ ==========\n")
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        new_access = str(refresh.access_token)
        new_refresh = str(refresh)

        print("✅ Refresh successful")
        print("🔐 New access token:", new_access)
        print("🔁 New refresh token:", new_refresh)
        print("========== ✅ REFRESH SUCCESS ✅ ==========\n")

        res = Response({"access": new_access}, status=200)
        res.set_cookie(
            key='refresh_token',
            value=new_refresh,
            httponly=True,
            secure=not base.DEBUG,
            samesite="None" if not base.DEBUG else "Lax",
            domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
            max_age=24 * 60 * 60,
            path='/'
        )

        return res


class CurrentUserView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserSerializer

    def get(self, request):

        # print("\n========== 🙋‍♂️ CURRENT USER ATTEMPT ==========")
        # print("👤 User:", request.user)
        # print("🛡️ Authenticated:", request.user.is_authenticated)
        # print("🔐 Headers received:", request.headers.get("Authorization", "❌ No Authorization header"))
        # print("========== END CURRENT USER ==========\n")

        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


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
        print("\n================== 🌐 LOGIN ATTEMPT ==================")
        print("📩 Endpoint hit: /api/users/login/")
        print("📦 Raw data from frontend:", request.data)

        serializer = self.get_serializer(data=request.data)

        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            print("❌ serializer.is_valid() raised an error")
            print("🛑 Validation errors:", serializer.errors)
            print("================== ❌ END LOGIN ATTEMPT ❌ ==================\n")
            raise e

        user = serializer.validated_data
        print("✅ User validated and returned from serializer:", user)

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        print("🎫 Access token generated:", access_token)
        print("🔁 Refresh token generated:", str(refresh))

        res = Response({"access": access_token}, status=200)

        cookie_max_age = 24 * 60 * 60
        res.set_cookie(
            key='refresh_token',
            value=str(refresh),
            httponly=True,
            secure=not base.DEBUG,
            samesite="None" if not base.DEBUG else "Lax",
            domain=getattr(settings, 'SESSION_COOKIE_DOMAIN', None),
            max_age=cookie_max_age,
            path='/'
        )

        print("✅ Login success, response prepared and refresh_token cookie set.")
        print("================== ✅ END LOGIN ATTEMPT ✅ ==================\n")
        return res


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
