import hashlib

from django.conf import settings


def get_client_ip(request) -> str:
    # X-Forwarded-For is client-controlled; trust it only behind a known proxy
    if settings.USE_X_FORWARDED_FOR:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def viewer_key(request) -> str:
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return f"user:{user.pk}"
    raw = f"{get_client_ip(request)}|{request.META.get('HTTP_USER_AGENT', '')}"
    return f"anon:{hashlib.sha256(raw.encode()).hexdigest()}"
