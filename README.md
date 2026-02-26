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
python manage.py test '${app_name}' --keepdb --noinput
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