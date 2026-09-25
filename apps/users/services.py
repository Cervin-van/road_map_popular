from django.contrib.auth import get_user_model
from django.db import transaction

from .tasks import send_password_reset_email

User = get_user_model()


def register_user(*, username: str, email: str, password: str) -> User:
    return User.objects.create_user(username=username, email=email, password=password)


def request_password_reset(email: str) -> None:
    """Queue reset emails; silent for unknown emails so accounts are not disclosed."""
    # Same recipient rules as django.contrib.auth.forms.PasswordResetForm.get_users
    users = User.objects.filter(email__iexact=email, is_active=True)
    for user in users:
        if user.has_usable_password():
            transaction.on_commit(lambda pk=user.pk: send_password_reset_email.delay(pk))


def reset_password(*, user: User, new_password: str) -> None:
    # Changing the hash invalidates both the reset token and existing sessions
    user.set_password(new_password)
    user.save(update_fields=["password"])
