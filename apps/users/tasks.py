from smtplib import SMTPException
from urllib.parse import urlencode

from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

User = get_user_model()


@shared_task(autoretry_for=(SMTPException,), retry_backoff=True, max_retries=3)
def send_password_reset_email(user_id: int) -> None:
    # The token is built here, not in the request, so it never sits in the broker
    user = User.objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return

    query = urlencode(
        {
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": default_token_generator.make_token(user),
        }
    )
    body = render_to_string(
        "emails/password_reset.txt",
        {"user": user, "reset_url": f"{settings.FRONTEND_URL}/reset-password?{query}"},
    )
    send_mail(
        subject="Password reset",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
    )
