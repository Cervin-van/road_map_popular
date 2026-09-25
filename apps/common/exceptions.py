from django.db.models import ProtectedError
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework.views import exception_handler


class Conflict(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Conflict."
    default_code = "conflict"


def custom_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        exc = Conflict(
            detail="Object is referenced by other objects and cannot be deleted.",
            code="protected",
        )

    response = exception_handler(exc, context)

    if response is not None and isinstance(exc, Conflict):
        response.data = {"detail": str(exc.detail), "code": exc.detail.code}
    return response
