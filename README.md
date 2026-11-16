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

## Layout

- `apps/core` - database models (Outlet, Item, SalesRecord)
- `apps/etl` - extract / transform / validate / load pipeline
- `apps/ml` - features, training, evaluation, registry, prediction
- `apps/dashboard` - views and HTMX partial endpoints
- `templates/dashboard/partials` - HTMX fragments
