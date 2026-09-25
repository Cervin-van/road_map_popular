from unittest.mock import patch

from django.core.cache import cache
from django.http import QueryDict

from apps.locations import cache as list_cache


def qd(query: str) -> QueryDict:
    return QueryDict(query)


# --- cache module ---------------------------------------------------------


def test_key_ignores_parameter_order():
    assert list_cache.make_key("list", qd("a=1&b=2")) == list_cache.make_key("list", qd("b=2&a=1"))


def test_key_depends_on_values_kind_and_repeated_params():
    base = list_cache.make_key("list", qd("page=1"))
    assert base != list_cache.make_key("list", qd("page=2"))
    assert base != list_cache.make_key("map", qd("page=1"))
    assert list_cache.make_key("list", qd("a=1&a=2")) != list_cache.make_key("list", qd("a=1"))


def test_set_then_get():
    list_cache.set("list", qd("page=1"), {"count": 1})
    assert list_cache.get("list", qd("page=1")) == {"count": 1}
    assert list_cache.get("list", qd("page=2")) is None


def test_invalidate_makes_old_entries_unreachable():
    list_cache.set("list", qd(""), {"count": 1})
    list_cache.invalidate()
    assert list_cache.get("list", qd("")) is None


def test_invalidate_without_version_key():
    cache.delete(list_cache.VERSION_KEY)
    list_cache.invalidate()  # incr on a missing key raises ValueError internally
    assert cache.get(list_cache.VERSION_KEY) is not None


def test_version_does_not_restart_from_one_after_eviction():
    list_cache.set("list", qd(""), {"stale": True})
    cache.delete(list_cache.VERSION_KEY)  # simulate eviction of the version key only
    assert list_cache.get("list", qd("")) is None


def test_cache_outage_is_not_fatal():
    with patch.object(list_cache.cache, "get", side_effect=ConnectionError("down")):
        assert list_cache.get("list", qd("")) is None
    with patch.object(list_cache.cache, "set", side_effect=ConnectionError("down")):
        list_cache.set("list", qd(""), {"count": 1})  # no exception
    with patch.object(list_cache.cache, "incr", side_effect=ConnectionError("down")):
        list_cache.invalidate()  # no exception
