# chargecast-django-react
ChargeCast is a climate-aware fleet optimisation engine with Django + Supabase + React + Tailwind. It is a refactored product based on a prior version jointly built by myself, George Burton, and my co-contributor, Blae Quayle, as part of the Software x Climate September 2025 cohort programme.

# Activating the venv for the backend/ folder

This repo standardises on a single Python virtual environment located at `backend/venv/`.

The venv folder should never be committed to GitHub (which is why it is included in .gitignore).

# To instantiate the venv for the first time from the repo root:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

# To reactivate the venv during subsequent sessions:

```bash
cd backend
source venv/bin/activate
```

# Recommendation for Python interpreter choice

Ensure VS Code is using the backend virtual environment interpreter:

Python: Select Interpreter → `backend/venv/bin/python`

# Testing

Run the Django test suite for the `core`, `carbon` and `fleet` apps:

```bash
cd backend
python manage.py test app_1_name app_2_name app_3_name --keepdb --noinput
```

Notes:
- `--keepdb` avoids dropping/recreating the test database (useful with Supabase session pooler connections).
- `--noinput` prevents interactive prompts during the test run.

# Database setup and running migrations

This project's remote PostgreSQL databases are hosted via Supabase. 

There are three Django apps within this project: `core`, `carbon` and `fleet`. 

Here is a list of the names of DB models created per app:

1) `core`: Region, PostcodeRegionCache, ChargerLocation
2) `carbon`: CarbonIntensityRecord
3) `fleet`: FleetUploadBatch, FleetChargingEvent

Before running migrations, it is essential to configure the project's .env file with the correct env vars which are themselves derived from the project's Supabase connection settings:

1) DB_NAME
2) DB_USER
3) DB_PASSWORD
4) DB_HOST
5) DB_PORT

To generate migrations (only if models have been changed):

```bash
cd backend
python manage.py makemigrations
```

To apply migrations (recommended for new setups / pulling latest):

```bash
cd backend
python manage.py migrate
```

To confirm the status of your migrations:

```bash
cd backend
python manage.py showmigrations
```

# Orchestration of carbon data ingestion via CLI (for human input and Render cron jobs)

Use the management command below to orchestrate carbon ingestion jobs:

```bash
cd backend
python manage.py ingest_carbon_data [--national-only | --regional-only | --actual-only] [--dry-run]
```

Notes:
- If no `--*-only` flag is provided, all three jobs run (national forecast, regional forecast, national actual).
- The `--national-only`, `--regional-only`, and `--actual-only` flags are mutually exclusive (only one can be used per run).
- `--dry-run` executes the flow but rolls back database writes at the end.

Examples:

```bash
# Run all three ingestion jobs
cd backend
python manage.py ingest_carbon_data

# Run one job only
python manage.py ingest_carbon_data --national-only
python manage.py ingest_carbon_data --regional-only
python manage.py ingest_carbon_data --actual-only

# Dry-run variants (no persisted DB writes)
python manage.py ingest_carbon_data --dry-run
python manage.py ingest_carbon_data --national-only --dry-run
```

# Render cron job configuration for 30-minute ingestion

The configuration file for this automated Render cron job is located at the root level of this project, in render.yaml.

The service name for this Render cron job is 'chargecast-ingest-carbon-data-30m', and is located within the 'ChargeCast' Render project. 

The cron job currently uses the dev branch to build and deploy, and uses backend/ as its root directory. In production, it will use the main branch.

Its Command is: backend/ $ python manage.py ingest_carbon_data

Its Build Command is: backend/ $ pip install -r requirements.txt. 

It autodeploys on commit to GitHub, and its environment variables replicate those of the chargecast-django-react Render web service. 