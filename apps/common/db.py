from django.db import IntegrityError


def violates_constraint(exc: IntegrityError, constraint: str) -> bool:
    """True if the IntegrityError was raised by the named DB constraint.

    psycopg exposes the constraint name; stabler than parsing the message.
    """
    diag = getattr(exc.__cause__, "diag", None)
    return getattr(diag, "constraint_name", None) == constraint
