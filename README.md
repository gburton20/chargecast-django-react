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
