# Blinkit Dashboard

Django + HTMX dashboard with an ETL pipeline and an ML sales model for the Blinkit grocery data.

## Quick start

```bash
uv sync                               # install dependencies from uv.lock
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py run_etl       # load data/raw/BlinkIT_Grocery_Data.xlsx
uv run python manage.py train_model   # train + register the model
uv run python manage.py runserver
```

Copy `.env.example` to `.env` and set `SECRET_KEY` on a fresh clone.

## Docker

```bash
docker compose up -d --build       # start Postgres + web (migrations run on startup)
docker compose exec web python manage.py run_etl        # load data/raw/BlinkIT_Grocery_Data.xlsx
docker compose exec web python manage.py train_model    # train + register the model
docker compose exec web python manage.py createsuperuser
```

The app is then available at http://localhost:8000. Configuration lives in
`docker-compose.yml` / `Dockerfile` and can be overridden via environment
variables (`WEB_PORT`, `POSTGRES_*`, `SECRET_KEY`, ...).

## Layout

- `apps/core` - database models (Outlet, Item, SalesRecord)
- `apps/etl` - extract / transform / validate / load pipeline
- `apps/ml` - features, training, evaluation, registry, prediction
- `apps/dashboard` - views and HTMX partial endpoints
- `templates/dashboard/partials` - HTMX fragments

---