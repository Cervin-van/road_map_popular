"""Invalidate the shared location list cache when its data changes.

Triggers: Location (create/update/soft delete via save, hard delete from the
admin), Review (avg_rating, reviews_count, popularity) and Category (its name
is part of the list). Views and votes do not invalidate: otherwise the cache
would never live long enough to help; views_7d in the list lags by <= TTL.

on_commit: a rolled-back change must not invalidate, and a reader must not
repopulate the cache with pre-commit data between invalidation and commit.
"""

from django.db import transaction
from django.db.models.signals import post_delete, post_save

from apps.categories.models import Category
from apps.reviews.models import Review

from . import cache as list_cache
from .models import Location


def _invalidate_list_cache(sender, **kwargs):
    transaction.on_commit(list_cache.invalidate)


def connect_signals():
    for model in (Location, Review, Category):
        for signal, name in ((post_save, "save"), (post_delete, "delete")):
            signal.connect(
                _invalidate_list_cache,
                sender=model,
                dispatch_uid=f"locations_list_cache_{name}_{model.__name__}",
            )
