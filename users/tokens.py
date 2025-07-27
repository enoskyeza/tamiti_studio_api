# users/tokens.py
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import smart_str, force_str, force_bytes, DjangoUnicodeDecodeError
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

account_activation_token = PasswordResetTokenGenerator()

def encode_uid(user):
    return urlsafe_base64_encode(force_bytes(user.pk))

def decode_uid(uidb64):
    try:
        return force_str(urlsafe_base64_decode(uidb64))
    except (TypeError, ValueError, OverflowError, DjangoUnicodeDecodeError):
        return None
