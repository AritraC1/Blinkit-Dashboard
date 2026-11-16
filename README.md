# Blinkit Dashboard

A Django dashboard for exploring Blinkit grocery sales data. It includes an ETL pipeline for importing the source spreadsheet, interactive sales analytics, and a machine-learning workflow for comparing and serving sales predictions.

## Features

- **Sales overview:** KPI cards, item and outlet charts, top and bottom items,and filters for outlets, outlet type, location tier, item type fat content, establishment year, and text search.
- **Predictions:** model performance metrics, feature importance, actual vs. predicted results, item-type comparisons, and an interactive prediction form.
- **ETL:** extract data from Excel, transform and validate it, load it into the database, and optionally export a cleaned CSV.
- **Model training:** compare Ridge, Random Forest, and Gradient Boosting regressors against a mean baseline, evaluate with item-grouped splits, and register the best model.
- **Responsive updates:** dashboard widgets use HTMX; charts are rendered with Chart.js.

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- The source spreadsheet at `data/raw/BlinkIT_Grocery_Data.xlsx` to run the ETL

## Local development

Install dependencies and configure the required Django secret:

```bash
uv sync
cp .env.example .env
```

> Set a private `SECRET_KEY` in `.env`. For a local SQLite database, remove or comment out the sample `DATABASE_URL` in `.env`; Django then uses `db.sqlite3`. Alternatively, set `DATABASE_URL` to a reachable PostgreSQL database.

Apply migrations, import the data, train a model, and start the development server:

```bash
uv run python manage.py migrate
uv run python manage.py run_etl
uv run python manage.py train_model
uv run python manage.py runserver
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Create an admin account if needed with `uv run python manage.py createsuperuser`; the Django admin is at `/admin/`.

The ETL reads `data/raw/BlinkIT_Grocery_Data.xlsx` by default and writes the cleaned dataset to `data/processed/cleaned_sales.csv`. To use another workbook or validate without loading it:

```bash
uv run python manage.py run_etl --file path/to/data.xlsx
uv run python manage.py run_etl --dry-run
```

The training command must run after the ETL has loaded sales records. It activates the winning model by default. Use `--notes` to annotate a run, `--no-activate` to register it without switching the active model, or `--with-rating` / `--with-outlet-size` to opt into additional features.

Run the test suite with:

```bash
uv run python manage.py test
```

## Production deployment

The app is designed to run behind gunicorn with WhiteNoise serving static
files. The required run order is:

```bash
# 1. Apply database migrations
uv run python manage.py migrate

# 2. Import and validate the Blinkit sales data
uv run python manage.py run_etl

# 3. Train and activate the sales prediction model
uv run python manage.py train_model

# 4. Collect static files for WhiteNoise
uv run python manage.py collectstatic

# 5. Serve with gunicorn (config/prod settings)
DJANGO_SETTINGS_MODULE=config.settings.prod uv run gunicorn config.wsgi
```

Set `SECRET_KEY`, `ALLOWED_HOSTS`, `DATABASE_URL` (Postgres) or leave the
default SQLite, and `SECURE_SSL_REDIRECT` via the environment or a `.env`
file. See `config/settings/prod.py` for the env-driven values. Gunicorn is a
declared dependency (`pyproject.toml`) and is installed by `uv sync`.

## Docker Compose

Compose starts PostgreSQL and the Django app. Migrations run automatically when the app starts. The raw-data directory is mounted read-only and model artifacts are persisted in a named volume.

```bash
docker compose up -d --build
docker compose exec web python manage.py run_etl
docker compose exec web python manage.py train_model
docker compose exec web python manage.py createsuperuser
```

The app is available at [http://localhost:8001](http://localhost:8001) by default. Set `WEB_PORT` to change the host port. Configure `SECRET_KEY`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` through environment variables or a `.env` file. Compose's database credentials are for local development only; replace them before using this setup in a shared or deployed environment.

## Project structure

```text
apps/
  core/       Sales, item, and outlet models
  dashboard/  Analytics views, filters, and HTMX partials
  etl/        Extract, transform, validate, and load pipeline
  ml/         Feature preparation, training, evaluation, and prediction
config/       Django settings and URL configuration
data/
  raw/        Source workbook
  processed/  Cleaned CSV output
templates/    Django templates and dashboard partials
static/       CSS, JavaScript, and vendored frontend libraries
```

---