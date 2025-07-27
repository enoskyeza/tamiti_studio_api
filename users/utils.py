# users/utils.py
from django.core.mail import send_mail
from django.conf import settings

def send_verification_email(user, request):
    from users.tokens import account_activation_token, encode_uid

    uid = encode_uid(user)
    token = account_activation_token.make_token(user)

    verify_url = f"{request.scheme}://{request.get_host()}/api/auth/verify-email/?uid={uid}&token={token}"

    subject = "Verify your Tamiti Studio account"
    message = f"Hi {user.username},\n\nPlease verify your email by clicking the link below:\n\n{verify_url}"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])


def send_password_reset_email(user, request):
    from users.tokens import account_activation_token, encode_uid

    uid = encode_uid(user)
    token = account_activation_token.make_token(user)

    reset_url = f"{request.scheme}://{request.get_host()}/api/auth/password-reset-confirm/?uid={uid}&token={token}"

    subject = "Tamiti Studio Password Reset"
    message = f"Hi {user.username},\n\nTo reset your password, click the link below:\n{reset_url}"
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
