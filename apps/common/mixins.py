from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import SAFE_METHODS


class EnforceCsrfMixin:
    """SessionAuthentication checks CSRF only for already authenticated users.

    Anonymous unsafe requests (login, register, password reset) would otherwise
    be CSRF-exempt, which allows login CSRF. Reuse DRF's check to get a JSON 403.
    """

    def initial(self, request, *args, **kwargs):
        if request.method not in SAFE_METHODS:
            SessionAuthentication().enforce_csrf(request)
        super().initial(request, *args, **kwargs)
