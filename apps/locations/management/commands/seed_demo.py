"""Fill the database with demo data: categories, users, Kyiv locations, reviews, votes, views.

Idempotent: a second run does nothing unless --reset is given. Writes via the
ORM on purpose (not services) so seeding does not send review emails.
"""

import random
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.categories.models import Category
from apps.locations import cache as list_cache
from apps.locations.models import Location, LocationView
from apps.reviews.models import Review, ReviewVote

User = get_user_model()

DEMO_PASSWORD = "DemoPass-2026"
ADMIN_USERNAME = "demo_admin"
USERNAMES = ["olena", "taras", "iryna", "andrii", "sofia", "maksym"]

CATEGORIES = {
    "Парки": "Зелені зони для прогулянок",
    "Музеї": "Історія, мистецтво, наука",
    "Пам'ятки": "Архітектура та історичні місця",
    "Кав'ярні": "Кава й десерти",
    "Ринки": "Локальні продукти та вулична їжа",
}

# title, category, address, lat, lng, description
LOCATIONS = [
    (
        "Маріїнський парк",
        "Парки",
        "вул. Михайла Грушевського",
        "50.447300",
        "30.537900",
        "Один із найстаріших парків Києва поруч із Маріїнським палацом.",
    ),
    (
        "Ботанічний сад ім. Гришка",
        "Парки",
        "вул. Тимірязєвська, 1",
        "50.414600",
        "30.563300",
        "Бузковий сад і краєвиди на Дніпро та Видубицький монастир.",
    ),
    (
        "Парк Наталка",
        "Парки",
        "Оболонська набережна",
        "50.504400",
        "30.518600",
        "Сучасний парк на набережній з велодоріжками.",
    ),
    (
        "Національний художній музей",
        "Музеї",
        "вул. Михайла Грушевського, 6",
        "50.449200",
        "30.530300",
        "Українське мистецтво від ікон до модернізму.",
    ),
    (
        "Музей історії Києва",
        "Музеї",
        "вул. Богдана Хмельницького, 7",
        "50.446400",
        "30.520100",
        "Історія міста від давнини до сьогодення.",
    ),
    (
        "Софійський собор",
        "Пам'ятки",
        "вул. Володимирська, 24",
        "50.452900",
        "30.514300",
        "Собор XI століття з мозаїками та фресками, об'єкт ЮНЕСКО.",
    ),
    (
        "Золоті ворота",
        "Пам'ятки",
        "вул. Володимирська, 40А",
        "50.448800",
        "30.513400",
        "Реконструкція головної брами давнього Києва.",
    ),
    (
        "Андріївська церква",
        "Пам'ятки",
        "Андріївський узвіз, 23",
        "50.458900",
        "30.518300",
        "Барокова церква Растреллі над Подолом.",
    ),
    (
        "Кав'ярня на Подолі",
        "Кав'ярні",
        "вул. Сагайдачного, 10",
        "50.463600",
        "30.519600",
        "Спешелті кава та свіжа випічка.",
    ),
    (
        "Кава біля Опери",
        "Кав'ярні",
        "вул. Володимирська, 50",
        "50.446400",
        "30.512400",
        "Невелика кав'ярня для перерви між прогулянками.",
    ),
    (
        "Бессарабський ринок",
        "Ринки",
        "Бессарабська площа, 2",
        "50.441700",
        "30.522200",
        "Критий ринок у центрі міста.",
    ),
    (
        "Житній ринок",
        "Ринки",
        "вул. Верхній Вал, 16",
        "50.466800",
        "30.512100",
        "Великий ринок на Подолі з фермерськими продуктами.",
    ),
]

REVIEW_TEXTS = [
    "Дуже сподобалось, повернуся ще.",
    "Гарне місце, але багато людей у вихідні.",
    "Варто відвідати хоча б раз.",
    "Нічого особливого.",
    "Одне з моїх улюблених місць у Києві!",
    "Атмосферно, рекомендую.",
]


class Command(BaseCommand):
    help = "Create demo data (idempotent). Use --reset to delete and recreate it."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete demo data first")
        parser.add_argument("--seed", type=int, default=42, help="Random seed")

    def handle(self, *args, reset, seed, **options):
        if reset:
            self._delete_demo_data()
        elif User.objects.filter(username=ADMIN_USERNAME).exists():
            self.stdout.write("Demo data already present; use --reset to recreate.")
            return

        rng = random.Random(seed)
        with transaction.atomic():
            admin, users = self._users()
            categories = self._categories()
            locations = self._locations(categories, users)
            reviews = self._reviews(rng, locations, users)
            votes = self._votes(rng, reviews, users)
            views = self._views(rng, locations)
            transaction.on_commit(list_cache.invalidate)

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {len(users)} users + admin, {len(categories)} categories, "
                f"{len(locations)} locations, {len(reviews)} reviews, "
                f"{votes} votes, {views} views."
            )
        )
        self.stdout.write(
            f"Admin: {admin.username} / {DEMO_PASSWORD}; users: {', '.join(USERNAMES)} "
            f"(same password)."
        )

    def _delete_demo_data(self):
        demo_users = User.objects.filter(username__in=[ADMIN_USERNAME, *USERNAMES])
        Location.all_objects.filter(author__in=demo_users).delete()  # cascades
        Category.objects.filter(name__in=CATEGORIES, locations__isnull=True).delete()
        demo_users.delete()

    def _users(self):
        admin = User.objects.create_superuser(
            ADMIN_USERNAME, f"{ADMIN_USERNAME}@example.com", DEMO_PASSWORD
        )
        users = [
            User.objects.create_user(name, f"{name}@example.com", DEMO_PASSWORD)
            for name in USERNAMES
        ]
        return admin, users

    def _categories(self):
        return {
            name: Category.objects.get_or_create(name=name, defaults={"description": text})[0]
            for name, text in CATEGORIES.items()
        }

    def _locations(self, categories, users):
        return [
            Location.objects.create(
                title=title,
                category=categories[category],
                address=address,
                latitude=Decimal(lat),
                longitude=Decimal(lng),
                description=description,
                author=users[index % len(users)],
            )
            for index, (title, category, address, lat, lng, description) in enumerate(LOCATIONS)
        ]

    def _reviews(self, rng, locations, users):
        reviews = []
        for location in locations:
            reviewers = rng.sample(users, k=rng.randint(0, len(users)))
            quality = rng.uniform(2.5, 5)  # each location has its own "true" level
            for user in reviewers:
                rating = min(5, max(1, round(rng.gauss(quality, 0.8))))
                reviews.append(
                    Review(
                        location=location, author=user, rating=rating, text=rng.choice(REVIEW_TEXTS)
                    )
                )
        return Review.objects.bulk_create(reviews)

    def _votes(self, rng, reviews, users):
        votes = [
            ReviewVote(review=review, user=user, value=rng.choice([1, 1, 1, -1]))
            for review in reviews
            for user in users
            if user.pk != review.author_id and rng.random() < 0.3
        ]
        return len(ReviewVote.objects.bulk_create(votes))

    def _views(self, rng, locations):
        now = timezone.now()
        views = []
        for location in locations:
            for _ in range(rng.randint(0, 40)):
                views.append(
                    (
                        LocationView(
                            location=location, viewer_key=f"anon:seed{rng.getrandbits(64):x}"
                        ),
                        now
                        - timedelta(days=rng.uniform(0, 14)),  # half fall outside the 7-day window
                    )
                )
        created = LocationView.objects.bulk_create([view for view, _ in views])
        # auto_now_add ignores explicit values on insert: backdate afterwards
        for view, created_at in zip(created, (moment for _, moment in views), strict=True):
            view.created_at = created_at
        LocationView.objects.bulk_update(created, ["created_at"])
        return len(created)
