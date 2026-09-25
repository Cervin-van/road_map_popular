from decimal import Decimal

import factory
from django.contrib.auth import get_user_model

from apps.categories.models import Category
from apps.locations.models import Location
from apps.reviews.models import Review, ReviewVote

DEFAULT_PASSWORD = "S3cure-pass!"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()
        skip_postgeneration_save = True

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.PostGenerationMethodCall("set_password", DEFAULT_PASSWORD)

    @factory.post_generation
    def _save(obj, create, extracted, **kwargs):
        if create:
            obj.save()


class AdminFactory(UserFactory):
    is_staff = True
    is_superuser = True


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location

    title = factory.Sequence(lambda n: f"Location {n}")
    description = factory.Faker("paragraph")
    category = factory.SubFactory(CategoryFactory)
    address = factory.Faker("street_address")
    latitude = Decimal("50.450100")  # Kyiv
    longitude = Decimal("30.523400")
    author = factory.SubFactory(UserFactory)


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    location = factory.SubFactory(LocationFactory)
    author = factory.SubFactory(UserFactory)
    rating = 4
    text = factory.Faker("sentence")


class ReviewVoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewVote

    review = factory.SubFactory(ReviewFactory)
    user = factory.SubFactory(UserFactory)
    value = ReviewVote.Value.LIKE
