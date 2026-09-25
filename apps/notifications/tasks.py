from smtplib import SMTPException

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mass_mail
from django.template.loader import render_to_string

from apps.reviews.models import Review

from .services import recipients_for_review


@shared_task(autoretry_for=(SMTPException,), retry_backoff=True, max_retries=3)
def send_new_review_emails(review_id: int) -> int:
    """Email the location author and subscribers about a new review.

    One message per recipient, so addresses are never disclosed to each other.
    Returns the number of emails sent.
    """
    review = (
        Review.objects.select_related("location", "author")
        .filter(pk=review_id, location__is_deleted=False)
        .first()
    )
    if review is None:  # deleted before the task ran
        return 0

    location = review.location
    subject = f'New review for "{location.title}"'
    location_url = f"{settings.FRONTEND_URL}/locations/{location.pk}"
    messages = [
        (
            subject,
            render_to_string(
                "emails/new_review.txt",
                {
                    "recipient": user,
                    "review": review,
                    "location": location,
                    "location_url": location_url,
                },
            ),
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
        )
        for user in recipients_for_review(review)
    ]
    return send_mass_mail(messages, fail_silently=False) if messages else 0
