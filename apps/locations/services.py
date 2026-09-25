import logging

from django.conf import settings
from django.core.cache import cache

from apps.common.utils import viewer_key

from .models import Location, LocationView

logger = logging.getLogger(__name__)

UPDATABLE_FIELDS = frozenset(
    {"title", "description", "category", "address", "latitude", "longitude"}
)


def create_location(*, author, **fields) -> Location:
    # author always comes from the request user, never from the payload
    return Location.objects.create(author=author, **fields)


def update_location(location: Location, **fields) -> Location:
    forbidden = fields.keys() - UPDATABLE_FIELDS
    if forbidden:
        raise ValueError(f"Fields cannot be updated: {', '.join(sorted(forbidden))}")
    if not fields:
        return location

    for name, value in fields.items():
        setattr(location, name, value)
    # auto_now is applied only when updated_at is listed in update_fields
    location.save(update_fields=[*fields, "updated_at"])
    return location


def soft_delete_location(location: Location) -> None:
    location.soft_delete()


def register_view(location: Location, request) -> bool:
    """Count a view at most once per LOCATION_VIEW_DEDUP_SECONDS per viewer.

    Takes the request (unlike other services) because the viewer identity
    is derived from the user or IP + User-Agent. Returns True if counted.
    """
    key = viewer_key(request)
    try:
        # cache.add == atomic SET NX EX in Redis: concurrent requests cannot both win
        is_new = cache.add(
            f"loc:view:{location.pk}:{key}", 1, timeout=settings.LOCATION_VIEW_DEDUP_SECONDS
        )
    except Exception:  # any cache backend failure: skip rather than inflate the counter
        logger.warning("View dedup cache unavailable, view not counted", exc_info=True)
        return False
    if not is_new:
        return False

    user = request.user if request.user.is_authenticated else None
    LocationView.objects.create(location=location, user=user, viewer_key=key)
    return True
