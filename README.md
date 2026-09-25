# Мапа популярності локацій — REST API

REST API на Django + DRF: користувачі додають локації, пишуть відгуки, ставлять like/dislike відгукам, а сервіс рахує рейтинг і популярність місць і показує найпопулярніші на мапі.

**Стек:** Python 3.12, Django 5.2, Django REST Framework, PostgreSQL 16, Redis 7 (кеш + брокер), Celery, django-filter, pandas, drf-spectacular, pytest. Усе запускається в Docker Compose.

---

## Швидкий старт

```bash
docker compose up --build
```

Одна команда на чистій машині піднімає `web`, `db`, `redis`, `worker` і `mailpit`. `.env` не потрібен: compose читає `.env.example` (dev-значення), а `.env`, якщо є, перекриває їх. Міграції застосовуються автоматично.

Демо-дані (12 локацій Києва, користувачі, відгуки, голоси, перегляди):

```bash
docker compose exec web python manage.py seed_demo     # або: make seed
```

Адмін `demo_admin` / `DemoPass-2026`; користувачі `olena`, `taras`, `iryna`, `andrii`, `sofia`, `maksym` з тим самим паролем.

| Що | URL |
|---|---|
| API | http://localhost:8000/api/ |
| Swagger UI | http://localhost:8000/api/docs/ |
| OpenAPI-схема | http://localhost:8000/api/schema/ |
| Адмінка | http://localhost:8000/admin/ |
| Листи (Mailpit) | http://localhost:8025 |

### Корисні команди

```bash
make test        # pytest (проти PostgreSQL у контейнері)
make lint        # ruff check --fix + ruff format
make check       # pytest + ruff + makemigrations --check
make migrate / make makemigrations / make superuser / make shell / make seed
```

Без `make`: `docker compose exec web pytest`, `docker compose exec web ruff check .` тощо.

---

## Змінні оточення

Усі мають робочі dev-значення в `.env.example`. Для продакшну створіть `.env` і змініть щонайменше `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, паролі БД.

| Змінна | За замовчуванням | Призначення |
|---|---|---|
| `DJANGO_SECRET_KEY` | `dev-insecure-change-me` | секрет Django |
| `DJANGO_DEBUG` | `True` | режим налагодження |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,0.0.0.0` | дозволені хости |
| `CSRF_TRUSTED_ORIGINS` | `http://localhost:8000,…,http://localhost:3000` | origin'и фронтенду для CSRF |
| `FRONTEND_URL` | `http://localhost:3000` | база посилань у листах |
| `USE_X_FORWARDED_FOR` | `False` | брати IP з `X-Forwarded-For` (лише за довіреним проксі) |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `road_map` | БД для контейнера `db` |
| `DATABASE_URL` | `postgres://road_map:road_map@db:5432/road_map` | підключення Django до БД |
| `REDIS_URL` | `redis://redis:6379/0` | кеш |
| `CELERY_BROKER_URL` | `redis://redis:6379/1` | брокер Celery |
| `EMAIL_HOST` / `EMAIL_PORT` | `mailpit` / `1025` | SMTP |
| `DEFAULT_FROM_EMAIL` | `noreply@road-map.local` | відправник |
| `POPULARITY_PRIOR_MEAN` | `3.0` | `m` у формулі популярності |
| `POPULARITY_PRIOR_WEIGHT` | `5` | `C` (має бути > 0) |
| `POPULARITY_WEIGHT_RATING` / `_REVIEWS` / `_VIEWS` | `50` / `20` / `10` | ваги `W_R`, `W_C`, `W_V` |
| `POPULARITY_VIEWS_WINDOW_DAYS` | `7` | вікно переглядів |
| `LOCATION_VIEW_DEDUP_SECONDS` | `3600` | не частіше одного перегляду на глядача |
| `LOCATIONS_LIST_CACHE_TTL` | `300` | TTL кешу списку та мапи, с |

---

## API

Префікс `/api/`, JSON, пагінація `?page=` / `?page_size=` (20 за замовчуванням, до 100). Повний опис — у Swagger.

| Метод | URL | Доступ | Опис |
|---|---|---|---|
| GET | `/auth/csrf/` | всі | ставить cookie `csrftoken` |
| POST | `/auth/register/` | анонім | реєстрація + одразу логін |
| POST | `/auth/login/` | анонім | логін → cookie `sessionid` |
| POST | `/auth/logout/` | auth | вихід |
| GET | `/auth/me/` | auth | поточний користувач |
| POST | `/auth/password-reset/` | всі | лист зі скиданням пароля (завжди 200) |
| POST | `/auth/password-reset/confirm/` | всі | `uid`, `token`, новий пароль |
| GET | `/categories/` , `/categories/{id}/` | всі | категорії |
| POST / PUT / PATCH / DELETE | `/categories/…` | адмін | категорія з локаціями → 409 |
| GET | `/locations/` | всі | список (кешується) |
| POST | `/locations/` | auth | створити (автор = поточний користувач) |
| GET | `/locations/{id}/` | всі | деталі + реєстрація перегляду |
| PUT / PATCH / DELETE | `/locations/{id}/` | автор / адмін | DELETE = soft delete |
| GET | `/locations/map/` | всі | GeoJSON для мапи |
| GET | `/locations/export/?export_format=csv\|json` | всі | експорт через pandas |
| GET / POST | `/locations/{id}/reviews/` | всі / auth | відгуки локації; повторний відгук → 409 |
| GET / PATCH / DELETE | `/reviews/{id}/` | всі / автор / адмін | відгук |
| POST / DELETE | `/reviews/{id}/vote/` | auth | `{"value": "like"\|"dislike"}`; повторний голос → 409 |
| POST / DELETE | `/locations/{id}/subscribe/` | auth | підписка на нові відгуки (бонус) |
| GET | `/subscriptions/` | auth | мої підписки |

**Список, мапа та експорт** приймають однакові параметри:

| Параметр | Приклад |
|---|---|
| `search` — назва й опис | `?search=парк` |
| `category`, `category_slug` | `?category=3`, `?category_slug=парки` |
| `author` | `?author=5` |
| `min_rating`, `max_rating` (1–5) | `?min_rating=4` |
| `ordering`: `created_at`, `avg_rating`, `popularity` (`-` = спадання) | `?ordering=-popularity` |

Мапа додатково: `bbox=min_lng,min_lat,max_lng,max_lat`, `limit` (100, максимум 500), сортування за замовчуванням `-popularity`.

**Коди відповідей:** 400 — валідація, 403 — не залогінений або немає прав, 404 — не знайдено або soft-deleted, 409 — дублікат (`{"detail": "...", "code": "review_already_exists" | "already_voted" | "already_subscribed" | "protected"}`).

### Приклад: сесія + CSRF через curl

Аутентифікація лише сесійна (cookies), без JWT. Для POST/PUT/PATCH/DELETE потрібен заголовок `X-CSRFToken` зі значенням cookie `csrftoken`.

```bash
API=http://localhost:8000/api
JAR=cookies.txt
csrf() { awk '$6 == "csrftoken" {print $7}' "$JAR"; }

# 1. Отримати csrftoken
curl -s -c $JAR $API/auth/csrf/ > /dev/null

# 2. Логін (після логіну Django змінює csrftoken — беремо новий з cookie)
curl -s -b $JAR -c $JAR -X POST $API/auth/login/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" \
  -d '{"username": "olena", "password": "DemoPass-2026"}'

# 3. Створити локацію
curl -s -b $JAR -X POST $API/locations/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" \
  -d '{"title": "Пейзажна алея", "description": "Арт-об'"'"'єкти й краєвиди", "category": 1,
       "address": "Пейзажна алея", "latitude": 50.4589, "longitude": 30.5145}'

# 4. Відгук і голос
curl -s -b $JAR -X POST $API/locations/1/reviews/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" \
  -d '{"rating": 5, "text": "Чудове місце"}'
curl -s -b $JAR -X POST $API/reviews/1/vote/ \
  -H "X-CSRFToken: $(csrf)" -H "Content-Type: application/json" -d '{"value": "like"}'

# 5. Читання — без авторизації
curl -s "$API/locations/?ordering=-popularity&min_rating=4"
curl -s "$API/locations/map/?bbox=30.4,50.4,30.6,50.5&limit=50"
curl -s -OJ "$API/locations/export/?export_format=csv&category_slug=парки"
```

> **Windows (Git Bash / PowerShell):** консоль передає кирилицю в аргументах не в UTF-8, і API відповідає `400 JSON parse error`. Кладіть тіло запиту у файл у кодуванні UTF-8 і надсилайте `--data-binary @payload.json`, а кириличні query-параметри URL-кодуйте (`category_slug=%D0%BF%D0%B0%D1%80%D0%BA%D0%B8`). Swagger UI (`/api/docs/`) цієї проблеми не має.

---

## Рейтинг і популярність

Нічого з цього не зберігається в БД: усе рахується анотаціями Django ORM в `apps/locations/selectors.py::locations_with_stats()` одним SQL-запитом на список.

```
avg_rating   = середня оцінка відгуків (null, якщо відгуків немає)
bayes_rating = (C · m + avg_rating · reviews_count) / (C + reviews_count)

popularity   = W_R · bayes_rating / 5
             + W_C · ln(1 + reviews_count)
             + W_V · ln(1 + views_7d)
```

`m = 3.0`, `C = 5`, `W_R = 50`, `W_C = 20`, `W_V = 10`, `views_7d` — зараховані перегляди за останні 7 днів. Усі коефіцієнти задаються в змінних оточення.

- **Байєсівське середнє** тягне оцінку локації з кількома відгуками до нейтральної `m`: одна «5» не обходить десять «4».
- **`ln(1 + x)`** згладжує великі числа: тисячі переглядів не перекривають якість.
- **Агрегати — окремими `Subquery`**, а не `Count`/`Avg` через JOIN: спільний JOIN відгуків і переглядів перемножив би рядки (3 відгуки × 4 перегляди = 12 і 12).

**Перегляди.** Відкриття `GET /locations/{id}/` зараховує перегляд не частіше разу на годину на глядача (`user:<id>` або `anon:<sha256(IP|User-Agent)>`) через `cache.add` — атомарний `SET NX EX` у Redis. Кожен зарахований перегляд — рядок `LocationView`: сирі події потрібні для вікна «останні 7 днів». В API є обидва лічильники: `views_count` — усі зараховані перегляди, `views_7d` — лише за останні 7 днів (саме він входить у популярність).

**Кеш списку.** `GET /locations/` і `/locations/map/` кешуються в Redis на 5 хвилин. Ключ = версія + md5 усіх query-параметрів. Створення/зміна/видалення локації, відгуку чи категорії піднімає версію (`cache.incr`) через сигнали в `transaction.on_commit` — старі сторінки одразу стають недосяжними.

---

## Прийняті рішення

Там, де ТЗ неоднозначне, вибрано найпростіше коректне рішення.

**Дані та бізнес-правила**
- **`avg_rating = null` без відгуків**, а не 0: «немає оцінок» ≠ «оцінка 0». Тому `min_rating`/`max_rating` не повертають локації без відгуків, а сортування за рейтингом ставить їх у кінець (NULLS LAST в обох напрямках).
- **Soft delete локацій.** Видалена локація зникає з API (404, немає у списку, мапі, експорті), її відгуки — теж, але рядки лишаються в БД і видні в адмінці.
- **Категорію не можна видалити**, поки на неї посилається хоч одна локація, навіть soft-deleted (PROTECT → 409): інакше видалену локацію не можна було б відновити.
- **Slug категорії генерується з назви з підтримкою кирилиці** (`музеї`), унікальний slug = унікальна назва без урахування регістру та пунктуації.
- **Один відгук на локацію і один голос на відгук** гарантують `UniqueConstraint` у БД і перевірка в сервісі; одночасні запити теж отримують 409 (ловиться порушення саме цього constraint).
- **Голос за власний відгук дозволено** (ТЗ не забороняє). Змінити like на dislike — DELETE + POST.
- **Координати** округлюються до 6 знаків замість помилки: віджети мап надсилають більше.

**Перегляди, кеш, мапа, експорт**
- Якщо Redis недоступний, перегляд **не зараховується** (не накручуємо), а сторінка працює; кеш списку в такому разі просто пропускається.
- Перегляди та голоси **не інвалідують кеш** — інакше він не жив би довше секунди. `views_7d` у списку оновлюється з лагом до 5 хвилин; сторінка деталей не кешується і завжди свіжа.
- Список кешується спільно для всіх, тому не містить полів, що залежать від користувача.
- `X-Forwarded-For` ігнорується, доки `USE_X_FORWARDED_FOR=False` (заголовок легко підробити).
- Початкова версія кешу випадкова: якщо Redis витіснить лише ключ версії, старі сторінки не «оживуть».
- Сортування завжди додає `-id`, щоб сторінки не перекривались, коли значення однакові.
- bbox через антимеридіан (min_lng > max_lng) не підтримується → 400.
- Експорт не пагінується й не кешується; CSV має UTF-8 BOM, щоб Excel правильно показував кирилицю; параметр `export_format`, бо `format` зарезервований DRF.

**Аутентифікація та листи**
- **CSRF перевіряється і для анонімних POST** (login, register, password-reset): стандартна `SessionAuthentication` робить це лише для залогінених, що дозволяло б login CSRF.
- Після логіну Django змінює `csrftoken` — клієнт має перечитати cookie.
- `password-reset` завжди відповідає 200, щоб не розкривати, чи зареєстрований email. Токен генерується в Celery-задачі, а не в запиті, тож не потрапляє в брокер.
- Лист про новий відгук отримують автор локації та підписники, крім автора відгуку, кожен окремим листом (адреси не розкриваються). Задача ставиться в чергу після commit; при ретраї після часткового SMTP-збою можливий повторний лист.
- Повідомлення API — англійською; клієнтам варто орієнтуватися на поле `code`.

---

## Структура

```
config/            налаштування (base / dev / test), urls, celery
apps/common/       базові моделі (TimeStamped, SoftDelete), permissions, пагінація, 409-хендлер, фільтр сортування
apps/users/        реєстрація, логін/логаут, me, скидання пароля (Celery)
apps/categories/   категорії
apps/locations/    локації, перегляди, селектор зі статистикою, кеш, фільтри, мапа, експорт, seed_demo
apps/reviews/      відгуки та голоси
apps/notifications/ підписки й листи про нові відгуки (бонус)
tests/             pytest + factory_boy, проти PostgreSQL
```

Логіка запису — у `services.py`, читання й анотації — у `selectors.py`, views тонкі. Побічні ефекти (кеш, листи) виконуються тільки в `transaction.on_commit`.
