#!/bin/sh
set -e

python - <<'PY'
import os, sys, time
import environ
import psycopg

url = environ.Env.db_url_config(os.environ["DATABASE_URL"])
for _ in range(30):
    try:
        psycopg.connect(
            dbname=url["NAME"], user=url["USER"], password=url["PASSWORD"],
            host=url["HOST"], port=url["PORT"] or 5432, connect_timeout=2,
        ).close()
        break
    except psycopg.OperationalError:
        print("waiting for database...", flush=True)
        time.sleep(1)
else:
    sys.exit("database is unavailable")
PY

# Only the web container migrates, so the worker does not race it.
if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
fi

exec "$@"
