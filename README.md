# Звіт про виконання тестового завдання «Мапа популярності локацій»

REST API на Django REST Framework для сервісу, де користувачі додають цікаві локації, залишають відгуки, оцінюють їх і переглядають найпопулярніші місця на мапі. Популярність і рейтинг обчислюються автоматично на основі активності користувачів.

**Репозиторій:** https://github.com/Cervin-van/road_map_popular

## Підсумок

| Показник | Значення |
|---|---|
| Обов'язкові вимоги ТЗ | виконано всі |
| Додаткове завдання (бонус) | виконано обидва пункти |
| API-тести | 276, усі проходять (PostgreSQL) |
| Лінтер / форматер | `ruff check`, `ruff format` — без зауважень |
| Міграції | синхронізовані з моделями (`makemigrations --check` — без змін) |
| OpenAPI-схема | генерується без попереджень (`spectacular --validate --fail-on-warn`) |
| Запуск | одна команда `docker compose up --build` на чистій машині, без `.env` |

---

## Технологічний стек

| Компонент | Версія | Призначення |
|---|---|---|
| Python | 3.12 | |
| Django | 5.2 | фреймворк, стандартна аутентифікація |
| Django REST Framework | 3.18 | REST API |
| PostgreSQL | 16 | основна БД |
| Redis | 7.4 | кеш списку, дедуплікація переглядів, брокер Celery |
| django-filter | 26.1 | фільтрація |
| django-redis | 7.0 | Redis як cache backend Django |
| Celery | 5.6 | фонова відправка email |
| pandas | 2.3 | експорт у CSV / JSON |
| drf-spectacular | 0.30 | OpenAPI-схема, Swagger UI |
| psycopg | 3.3 | драйвер PostgreSQL |
| pytest, pytest-django, factory_boy, freezegun | 9.1 / — / 3.3 / — | тести |
| ruff | 0.16 | лінтер і форматер |
| Mailpit | latest | SMTP-пастка з веб-інтерфейсом для dev |
| Docker Compose | v2 | сервіси `web`, `db`, `redis`, `worker`, `mailpit` |

---

## Відповідність вимогам ТЗ

### Обов'язковий стек

| Вимога | Реалізація |
|---|---|
| Django, Django REST Framework | ✅ |
| PostgreSQL | ✅ сервіс `db`, на ньому ж проходять тести |
| Redis | ✅ кеш списку локацій і мапи, дедуплікація переглядів, брокер Celery |
| Django Authentication (Session + Cookies) | ✅ єдиний клас аутентифікації — `SessionAuthentication`; JWT і токенів немає |
| Django Filter | ✅ `LocationFilter` |
| Docker Compose | ✅ |
| API Tests (плюс) | ✅ 276 тестів |

### Функціонал

| Вимога ТЗ | Реалізація | Endpoint |
|---|---|---|
| Реєстрація, авторизація, вихід стандартною системою Django | ✅ `login()` / `logout()`, cookie `sessionid`, CSRF | `/api/auth/register/`, `/login/`, `/logout/`, `/me/` |
| Скидання пароля через email | ✅ `default_token_generator`, лист через Celery | `/api/auth/password-reset/`, `/password-reset/confirm/` |
| CRUD категорій | ✅ | `/api/categories/` |
| CRUD локацій: назва, опис, категорія, адреса, широта, довгота, автор, дата створення й оновлення | ✅ | `/api/locations/` |
| Soft Delete локацій | ✅ поля `is_deleted`, `deleted_at`; запис лишається в БД | `DELETE /api/locations/{id}/` |
| Неавторизовані лише переглядають; створюють авторизовані; редагують і видаляють автор або адміністратор | ✅ | |
| Відгук з рейтингом 1–5 і текстом | ✅ | `/api/locations/{id}/reviews/`, `/api/reviews/{id}/` |
| Один відгук на локацію від користувача, повтор → помилка | ✅ `UniqueConstraint` + перевірка в сервісі → **409** | |
| Like / Dislike відгуків, один голос | ✅ `UniqueConstraint` + перевірка в сервісі → **409** | `/api/reviews/{id}/vote/` |
| Рейтинг не зберігається в БД, обчислюється Django ORM | ✅ анотація `avg_rating` | |
| Популярність не зберігається в БД; з середнього рейтингу, кількості відгуків і переглядів за 7 днів | ✅ анотація `popularity` (формула нижче) | |
| Перегляд +1 при відкритті деталей, не частіше 1 разу на годину, Redis | ✅ `cache.add` з TTL 3600 с | `GET /api/locations/{id}/` |
| Пошук за назвою та описом | ✅ | `?search=` |
| Фільтри за категорією, рейтингом, автором | ✅ | `?category=`, `?category_slug=`, `?min_rating=`, `?max_rating=`, `?author=` |
| Сортування за датою, рейтингом, популярністю | ✅ | `?ordering=created_at\|avg_rating\|popularity` |
| Пагінація списків | ✅ | `?page=`, `?page_size=` |
| Кешування списку локацій у Redis; очищення після створення / оновлення / видалення локації і нового відгуку | ✅ | `GET /api/locations/` |
| Експорт у JSON і CSV через pandas | ✅ | `/api/locations/export/?export_format=csv\|json` |
| Запуск через Docker Compose | ✅ | |
| API-тести | ✅ | `tests/` |

### Додаткове завдання (бонус)

| Вимога | Реалізація |
|---|---|
| Email автору локації після нового відгуку | ✅ Celery-задача, ставиться в чергу після коміту транзакції |
| Підписка на локацію з email про всі нові відгуки | ✅ `POST / DELETE /api/locations/{id}/subscribe/`, список — `GET /api/subscriptions/` |

Додатково реалізовано: GeoJSON-endpoint для мапи (`/api/locations/map/`), команда демо-даних `seed_demo`, Swagger UI.

---

## Запуск

```bash
git clone https://github.com/Cervin-van/road_map_popular.git
cd road_map_popular
docker compose up --build
```

Піднімаються `web` (Django), `db` (PostgreSQL), `redis`, `worker` (Celery), `mailpit`. Міграції застосовуються автоматично. Файл `.env` не обов'язковий: compose використовує значення з `.env.example`, а `.env` (якщо створений) їх перекриває.

Демо-дані — 12 локацій Києва, 5 категорій, 6 користувачів, відгуки, голоси, перегляди:

```bash
docker compose exec web python manage.py seed_demo      # або: make seed
```

| Роль | Логін | Пароль |
|---|---|---|
| Адміністратор | `demo_admin` | `DemoPass-2026` |
| Користувачі | `olena`, `taras`, `iryna`, `andrii`, `sofia`, `maksym` | `DemoPass-2026` |

| Сервіс | URL |
|---|---|
| API | http://localhost:8000/api/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| OpenAPI-схема | http://localhost:8000/api/schema/ |
| Адмін-панель | http://localhost:8000/admin/ |
| Mailpit (листи) | http://localhost:8025 |

### Команди

```bash
make up              # docker compose up --build
make test            # pytest
make lint            # ruff check --fix + ruff format
make check           # pytest + ruff + makemigrations --check
make seed            # демо-дані
make migrate | makemigrations | superuser | shell | logs | down
```

---

## API

Префікс `/api/`, формат JSON. Пагінація: `?page=`, `?page_size=` (20 за замовчуванням, максимум 100). Повна інтерактивна документація — Swagger UI.

### Endpoints

| Метод | URL | Доступ | Опис |
|---|---|---|---|
| GET | `/auth/csrf/` | всі | встановлює cookie `csrftoken`, повертає токен |
| POST | `/auth/register/` | анонім | реєстрація, одразу вхід |
| POST | `/auth/login/` | анонім | вхід, cookie `sessionid` |
| POST | `/auth/logout/` | авторизований | вихід |
| GET | `/auth/me/` | авторизований | поточний користувач |
| POST | `/auth/password-reset/` | всі | лист для скидання пароля |
| POST | `/auth/password-reset/confirm/` | всі | `uid`, `token`, `new_password`, `new_password2` |
| GET | `/categories/`, `/categories/{id}/` | всі | категорії |
| POST, PUT, PATCH, DELETE | `/categories/…` | адміністратор | керування категоріями |
| GET | `/locations/` | всі | список локацій (кешується) |
| POST | `/locations/` | авторизований | створення; автор — поточний користувач |
| GET | `/locations/{id}/` | всі | деталі; реєструє перегляд |
| PUT, PATCH, DELETE | `/locations/{id}/` | автор, адміністратор | редагування; `DELETE` — soft delete |
| GET | `/locations/map/` | всі | GeoJSON для мапи (кешується) |
| GET | `/locations/export/` | всі | файл CSV або JSON |
| GET | `/locations/{id}/reviews/` | всі | відгуки локації |
| POST | `/locations/{id}/reviews/` | авторизований | новий відгук |
| GET | `/reviews/{id}/` | всі | відгук |
| PATCH, DELETE | `/reviews/{id}/` | автор, адміністратор | редагування, видалення |
| POST, DELETE | `/reviews/{id}/vote/` | авторизований | голос `{"value": "like" \| "dislike"}`, скасування |
| POST, DELETE | `/locations/{id}/subscribe/` | авторизований | підписка, відписка |
| GET | `/subscriptions/` | авторизований | мої підписки |

### Параметри списку, мапи та експорту

| Параметр | Опис | Приклад |
|---|---|---|
| `search` | пошук у назві та описі, без урахування регістру | `?search=парк` |
| `category` | id категорії | `?category=3` |
| `category_slug` | slug категорії | `?category_slug=парки` |
| `author` | id автора | `?author=5` |
| `min_rating`, `max_rating` | межі середнього рейтингу (1–5, включно) | `?min_rating=4` |
| `ordering` | `created_at`, `avg_rating`, `popularity`; `-` — спадання | `?ordering=-popularity` |
| `page`, `page_size` | пагінація (крім мапи й експорту) | `?page=2&page_size=50` |

Лише для мапи: `bbox=min_lng,min_lat,max_lng,max_lat`, `limit` (за замовчуванням 100, максимум 500). Сортування мапи за замовчуванням — `-popularity`, списку — `-created_at`.

Лише для експорту: `export_format=csv|json` (обов'язковий).

### Коди відповідей

| Код | Випадок |
|---|---|
| 200 / 201 / 204 | успіх |
| 400 | помилка валідації |
| 403 | не авторизований або немає прав |
| 404 | об'єкт не знайдено або видалено (soft delete) |
| 405 | метод не підтримується |
| 409 | конфлікт: `review_already_exists`, `already_voted`, `already_subscribed`, `protected` |

Формат помилки 409: `{"detail": "…", "code": "…"}`.

### Приклади відповідей

`GET /api/locations/?ordering=-popularity&page_size=1`

```json
{
  "count": 15,
  "next": "http://localhost:8000/api/locations/?ordering=-popularity&page=2&page_size=1",
  "previous": null,
  "results": [
    {
      "id": 13,
      "title": "Кава біля Опери",
      "short_description": "Невелика кав'ярня для перерви між прогулянками.",
      "category": {"id": 4, "name": "Кав'ярні"},
      "author": {"id": 13, "username": "andrii"},
      "address": "вул. Володимирська, 50",
      "latitude": "50.446400",
      "longitude": "30.512400",
      "avg_rating": 4.33,
      "reviews_count": 6,
      "views_count": 30,
      "views_7d": 12,
      "popularity": 101.84,
      "created_at": "2026-09-25T12:42:18.158337+03:00"
    }
  ]
}
```

`GET /api/locations/4/reviews/`, один елемент:

```json
{
  "id": 7,
  "location": 4,
  "author": {"id": 13, "username": "andrii"},
  "rating": 3,
  "text": "Одне з моїх улюблених місць у Києві!",
  "likes_count": 1,
  "dislikes_count": 1,
  "my_vote": null,
  "created_at": "2026-09-25T12:42:18.162219+03:00",
  "updated_at": "2026-09-25T12:42:18.162223+03:00"
}
```

`GET /api/locations/map/?limit=1`

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "id": 13,
      "geometry": {"type": "Point", "coordinates": [30.5124, 50.4464]},
      "properties": {"id": 13, "title": "Кава біля Опери", "category": "Кав'ярні", "avg_rating": 4.33, "popularity": 101.84}
    }
  ]
}
```

Експорт містить колонки: `id`, `title`, `description`, `category`, `author`, `address`, `latitude`, `longitude`, `avg_rating`, `reviews_count`, `views_count`, `views_7d`, `popularity`, `created_at`. Файл віддається як `locations_YYYY-MM-DD.csv` / `.json`; CSV у UTF-8 з BOM.

### Робота з API через curl

Аутентифікація сесійна. Для `POST`, `PUT`, `PATCH`, `DELETE` потрібен заголовок `X-CSRFToken` зі значенням cookie `csrftoken`; після входу значення cookie оновлюється.

```bash
API=http://localhost:8000/api
JAR=cookies.txt
csrf() { awk '$6 == "csrftoken" {print $7}' "$JAR"; }

# отримати csrftoken
curl -s -c $JAR $API/auth/csrf/ > /dev/null

# вхід
curl -s -b $JAR -c $JAR -X POST $API/auth/login/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" \
  -d '{"username": "olena", "password": "DemoPass-2026"}'

# створити локацію
curl -s -b $JAR -X POST $API/locations/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" \
  -d '{"title": "Пейзажна алея", "description": "Арт-об'"'"'єкти й краєвиди", "category": 1,
       "address": "Пейзажна алея", "latitude": 50.4589, "longitude": 30.5145}'

# відгук і голос
curl -s -b $JAR -X POST $API/locations/1/reviews/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" \
  -d '{"rating": 5, "text": "Чудове місце"}'
curl -s -b $JAR -X POST $API/reviews/1/vote/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" -d '{"value": "like"}'

# читання без авторизації
curl -s "$API/locations/?ordering=-popularity&min_rating=4"
curl -s "$API/locations/map/?bbox=30.4,50.4,30.6,50.5&limit=50"
curl -s -OJ "$API/locations/export/?export_format=csv&category_slug=парки"
```

У Windows-консолі кирилиця в аргументах передається не в UTF-8: тіло запиту варто класти у файл UTF-8 і передавати `--data-binary @payload.json`, а кириличні query-параметри — URL-кодувати.

### Скидання пароля

1. `POST /api/auth/password-reset/` з `{"email": "..."}` — відповідь завжди 200.
2. У листі (Mailpit, http://localhost:8025) є посилання `FRONTEND_URL/reset-password?uid=…&token=…`, а також окремо значення `uid` і `token`.
3. `POST /api/auth/password-reset/confirm/` з `{"uid", "token", "new_password", "new_password2"}` — 200.

Токен одноразовий, діє 3 дні. Після зміни пароля всі сесії користувача стають недійсними.

---

## Модель даних

```
User ──< Location >── Category
  │        │  └──< LocationView
  │        └──< LocationSubscription >── User
  ├──< Review >── Location        (unique: location + author)
  └──< ReviewVote >── Review      (unique: review + user, value = +1 / -1)
```

| Модель | Поля | Обмеження |
|---|---|---|
| `Category` | `name`, `slug` (генерується з назви, кирилиця), `description`, `created_at`, `updated_at` | slug унікальний |
| `Location` | `title`, `description`, `category` (PROTECT), `address`, `latitude`, `longitude` (Decimal 9,6), `author`, `is_deleted`, `deleted_at`, `created_at`, `updated_at` | CHECK: широта −90…90, довгота −180…180; індекс `(is_deleted, created_at)` |
| `LocationView` | `location`, `user` (nullable), `viewer_key`, `created_at` | індекс `(location, created_at)` |
| `Review` | `location`, `author`, `rating`, `text`, `created_at`, `updated_at` | UNIQUE `(location, author)`; CHECK рейтинг 1–5 |
| `ReviewVote` | `review`, `user`, `value` (+1 / −1), `created_at` | UNIQUE `(review, user)`; CHECK value ∈ {1, −1} |
| `LocationSubscription` | `user`, `location`, `created_at` | UNIQUE `(user, location)` |

Рейтинг, кількість відгуків, перегляди та популярність у моделях не зберігаються.

---

## Рейтинг і популярність

Обчислюються анотаціями Django ORM у `apps/locations/selectors.py::locations_with_stats()` — один SQL-запит на сторінку списку, кожен агрегат окремим `Subquery`.

```
avg_rating   = середня оцінка відгуків (null, якщо відгуків немає)
bayes_rating = (C · m + avg_rating · reviews_count) / (C + reviews_count)

popularity   = W_R · bayes_rating / 5
             + W_C · ln(1 + reviews_count)
             + W_V · ln(1 + views_7d)
```

| Параметр | Значення | Змінна оточення |
|---|---|---|
| `m` — нейтральний рейтинг | 3.0 | `POPULARITY_PRIOR_MEAN` |
| `C` — вага нейтрального рейтингу | 5 | `POPULARITY_PRIOR_WEIGHT` |
| `W_R` — вага рейтингу | 50 | `POPULARITY_WEIGHT_RATING` |
| `W_C` — вага кількості відгуків | 20 | `POPULARITY_WEIGHT_REVIEWS` |
| `W_V` — вага переглядів | 10 | `POPULARITY_WEIGHT_VIEWS` |
| вікно переглядів | 7 днів | `POPULARITY_VIEWS_WINDOW_DAYS` |

Поля в API: `avg_rating` і `popularity` (округлені до 2 знаків), `reviews_count`, `views_count` (усі зараховані перегляди), `views_7d` (перегляди за 7 днів).

---

## Перегляди

- Перегляд реєструється при `GET /api/locations/{id}/`; значення у відповіді вже враховує поточний перегляд.
- Глядач визначається як `user:<id>` для авторизованих і `anon:<sha256(IP | User-Agent)>` для анонімів.
- Дедуплікація — `cache.add` у Redis (атомарний `SET NX EX`) з TTL `LOCATION_VIEW_DEDUP_SECONDS` = 3600 с: один глядач збільшує лічильник локації не частіше разу на годину.
- Кожен зарахований перегляд зберігається рядком `LocationView`.
- Список, мапа, експорт перегляди не реєструють.

## Кешування

- Кешуються `GET /api/locations/` і `GET /api/locations/map/` у Redis, TTL `LOCATIONS_LIST_CACHE_TTL` = 300 с.
- Ключ кешу: `locations:list:v{версія}:{list|map}:{md5 query-параметрів}` — окремий запис для кожної комбінації фільтрів, сортування та сторінки.
- Очищення: сигнали `post_save` / `post_delete` моделей `Location`, `Review`, `Category` через `transaction.on_commit` збільшують версію (`cache.incr`), усі попередні записи стають недосяжними.
- Сторінка деталей локації не кешується.
- Кеш спільний для всіх користувачів.

## Email і фонові задачі

| Подія | Отримувачі | Задача |
|---|---|---|
| Запит скидання пароля | власник email | `apps.users.tasks.send_password_reset_email` |
| Новий відгук | автор локації та підписники, крім автора відгуку; кожному окремий лист | `apps.notifications.tasks.send_new_review_emails` |

Задачі ставляться в чергу Celery (брокер Redis) після коміту транзакції, повторюються до 3 разів при помилці SMTP. У dev листи потрапляють у Mailpit.

---

## Правила поведінки

- Видалена (soft delete) локація повертає 404, не з'являється у списку, мапі, експорті; її відгуки також недоступні. Запис лишається в БД і видимий в адмін-панелі (фільтр `is_deleted`).
- Категорію, на яку посилається хоча б одна локація (включно з видаленими), видалити не можна — 409 `protected`.
- Назви категорій унікальні без урахування регістру та розділових знаків.
- Локація без відгуків має `avg_rating = null`; фільтри `min_rating` / `max_rating` її не повертають; при сортуванні за рейтингом вона йде останньою.
- При однакових значеннях сортування додатково йде за `-id`.
- Координати з більш ніж 6 знаками після коми округлюються.
- `author` локації та відгуку береться з сесії; значення з тіла запиту ігнорується.
- Голос можна скасувати (`DELETE`) і поставити знову; повторний `POST` — 409. Голосувати за власний відгук дозволено.
- Реєстрація та вхід доступні лише анонімам; повторний вхід без виходу — 403.
- CSRF перевіряється для всіх змінюючих запитів, включно з анонімними (реєстрація, вхід, скидання пароля).
- `password-reset` відповідає 200 незалежно від того, чи існує email.
- `bbox`, що перетинає антимеридіан (min_lng > max_lng), — 400.
- Експорт не пагінується й не кешується.
- Нечисловий id у URL — 404.
- Повідомлення API англійською; помилки конфлікту мають машиночитне поле `code`.

---

## Тестування

```bash
docker compose exec web pytest              # або make test
docker compose exec web pytest tests/test_reviews.py -v
```

276 тестів, pytest + pytest-django + factory_boy + freezegun, БД — PostgreSQL. Celery у тестах виконується синхронно, email — у `mail.outbox`, кеш — LocMemCache.

| Файл | Тестів | Що покрито |
|---|---|---|
| `test_reviews.py` | 38 | моделі й обмеження, CRUD відгуків, права, 409 на дубль, лічильники, `my_vote`, голоси та їх скасування |
| `test_locations.py` | 27 | модель, CHECK координат, soft delete, PROTECT, CRUD, права автора й адміна, валідація, округлення координат |
| `test_location_filters.py` | 21 | пошук, фільтри за категорією / slug / автором / рейтингом, сортування, стабільна пагінація |
| `test_categories.py` | 19 | slug з кирилиці, унікальність, читання для всіх, запис лише адміну |
| `test_location_cache.py` | 18 | ключі кешу, повторний запит без SQL, очищення після змін локації / відгуку / категорії, лише після коміту |
| `test_auth.py` | 16 | реєстрація, вхід, вихід, `me`, CSRF для анонімних запитів |
| `test_location_views.py` | 15 | дедуплікація переглядів за годину, різні глядачі, недоступність Redis, реєстрація в деталях |
| `test_location_map.py` | 15 | GeoJSON, `bbox`, `limit`, фільтри, кеш мапи |
| `test_password_reset.py` | 14 | лист, невідомий email, підтвердження, одноразовість токена, завершення старих сесій |
| `test_lookup_ids.py` | 14 | нечислові id → 404 |
| `test_common.py` | 14 | Swagger, permissions, обробник 409, ідентифікація глядача |
| `test_location_stats.py` | 13 | `avg_rating`, кількості, вікно 7 днів, формула популярності, коефіцієнти з налаштувань, відсутність N+1 |
| `test_subscriptions.py` | 12 | підписка, 409 на дубль, відписка, отримувачі листів |
| `test_review_services.py` | 12 | сервіси відгуків і голосів, 409 при одночасних запитах |
| `test_location_export.py` | 9 | CSV / JSON, заголовки, фільтри, без пагінації, видалені не потрапляють |
| `test_review_notifications.py` | 6 | лист автору й підписникам, без автора відгуку, лише після коміту |
| `test_location_services.py` | 6 | сервіси локацій |
| `test_seed_demo.py` | 4 | демо-дані, повторний запуск |
| `test_browsable_api.py` | 3 | усі endpoints відкриваються в Browsable API без помилок |

---

## Змінні оточення

Робочі значення для запуску — у `.env.example`.

| Змінна | Значення в `.env.example` | Призначення |
|---|---|---|
| `DJANGO_SECRET_KEY` | `dev-insecure-change-me` | секрет Django |
| `DJANGO_DEBUG` | `True` | режим налагодження |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | дозволені хости |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000` | довірені origin'и для CSRF |
| `FRONTEND_URL` | `http://localhost:3000` | база посилань у листах |
| `USE_X_FORWARDED_FOR` | `False` | брати IP глядача з `X-Forwarded-For` |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | `road_map` | параметри контейнера БД |
| `DATABASE_URL` | `postgres://road_map:road_map@db:5432/road_map` | підключення до БД |
| `REDIS_URL` | `redis://redis:6379/0` | кеш |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | брокер Celery |
| `EMAIL_HOST`, `EMAIL_PORT` | `mailpit`, `1025` | SMTP |
| `DEFAULT_FROM_EMAIL` | `noreply@road-map.local` | адреса відправника |
| `POPULARITY_*` | див. «Рейтинг і популярність» | коефіцієнти формули |
| `LOCATION_VIEW_DEDUP_SECONDS` | `3600` | інтервал дедуплікації переглядів |
| `LOCATIONS_LIST_CACHE_TTL` | `300` | TTL кешу списку та мапи |

---

## Структура проєкту

```
config/
  settings/        base.py, dev.py, test.py
  urls.py          /api/…, /api/docs/, /api/schema/, /admin/
  celery.py
apps/
  common/          TimeStampedModel, SoftDeleteModel, permissions, пагінація,
                   обробник 409, StableOrderingFilter, EnforceCsrfMixin
  users/           реєстрація, вхід, вихід, me, скидання пароля
  categories/      категорії
  locations/       локації, перегляди, селектор статистики, кеш, фільтри,
                   мапа, експорт, команда seed_demo
  reviews/         відгуки та голоси
  notifications/   підписки та листи про нові відгуки
tests/             276 тестів, фабрики, фікстури
docker/            entrypoint.sh
Dockerfile, docker-compose.yml, Makefile, pyproject.toml, requirements*.txt, .env.example
```

Логіка запису — у `services.py`, читання з анотаціями — у `selectors.py` (`locations`, `reviews`), views тонкі. Побічні ефекти (кеш, email) виконуються через `transaction.on_commit`.
