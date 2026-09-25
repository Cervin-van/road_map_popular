DC = docker compose
WEB = $(DC) exec web

.PHONY: up down build logs migrate makemigrations superuser shell test lint check

up:
	$(DC) up --build

down:
	$(DC) down

build:
	$(DC) build

logs:
	$(DC) logs -f web worker

migrate:
	$(WEB) python manage.py migrate

makemigrations:
	$(WEB) python manage.py makemigrations

superuser:
	$(WEB) python manage.py createsuperuser

shell:
	$(WEB) python manage.py shell

test:
	$(WEB) pytest

lint:
	$(WEB) ruff check . --fix
	$(WEB) ruff format .

check:
	$(WEB) pytest
	$(WEB) ruff check .
	$(WEB) python manage.py makemigrations --check --dry-run
