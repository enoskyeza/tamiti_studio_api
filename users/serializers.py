# users/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate
from users.models import User, UserPreferences


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = ["dark_mode", "language", "daily_summary"]


class UserSerializer(serializers.ModelSerializer):
    preferences = UserPreferencesSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "phone",
            "is_verified",
            "avatar",
            "bio",
            "role",
            "total_tasks_completed",
            "last_seen",
            "streak_days",
            "current_streak_started",
            "preferences",
            "is_superuser",
            "is_staff",
        ]
        read_only_fields = [
            "is_verified",
            "role",
            "total_tasks_completed",
            "last_seen",
            "streak_days",
            "current_streak_started",
            "preferences",
            "is_superuser",
            "is_staff",
        ]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(**validated_data)
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        print("🔎 LoginSerializer.validate() called")
        print("📨 Data received for authentication:", data)

        user = authenticate(**data)

        if not user:
            print("🚫 Authentication failed — Invalid credentials")
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_active:
            print("🚫 Authentication failed — User inactive")
            raise serializers.ValidationError("User is inactive")

        print("✅ Authentication successful for user:", user)
        return user


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, email):
        if not User.objects.filter(email=email).exists():
            raise serializers.ValidationError("No user found with this email")
        return email


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        from users.tokens import account_activation_token, decode_uid
        uid = decode_uid(attrs.get('uid'))
        token = attrs.get('token')

        try:
            user = User.objects.get(pk=uid)
        except User.DoesNotExist:
            raise serializers.ValidationError("Invalid user")

        if not account_activation_token.check_token(user, token):
            raise serializers.ValidationError("Invalid or expired token")

        self.user = user
        return attrs

    def save(self):
        self.user.set_password(self.validated_data['new_password'])
        self.user.save()
