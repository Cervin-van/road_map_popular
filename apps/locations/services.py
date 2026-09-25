from .models import Location

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
