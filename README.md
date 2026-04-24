# Vehicle Maintenance Tracker

A Django web app for tracking vehicles, service types, and maintenance history across a personal collection of cars, motorcycles, and trucks.

## Current Status

The active application in this repository is the Django project under `vehicle_tracker/`.

## Features

- Dashboard with total vehicles, maintenance logs, service types, and total spend
- Vehicle CRUD with validation for year, mileage, VIN, optional photo uploads, and automatic image resizing/compression
- Service type CRUD with protected deletes when a service is already in use
- Maintenance log CRUD with multiple services per visit
- Django authentication with login, signup, and login-required app pages
- Django admin support for all core models

## Data Model

- `vehicle_types`: Lookup table for vehicle categories such as Car, Motorcycle, and Truck
- `vehicles`: Stores each vehicle including year, make, model, nickname, type, color, mileage, VIN, and notes
- `service_types`: Stores maintenance services such as Oil Change or Tire Rotation, including default intervals
- `maintenance_logs`: Stores each maintenance visit for a vehicle
- `log_services`: Junction table linking a maintenance log to one or more service types with optional per-service cost and notes

## Project Layout

```text
vehicle-maintenance-tracker/
|-- vehicle_tracker/
|   |-- manage.py
|   |-- db.sqlite3
|   |-- core/
|   `-- vehicle_tracker/
|-- requirements.txt
`-- README.md
```

## Requirements

- Python 3.13
- `pip`

## Local Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
py -3 -m pip install -r requirements.txt
```

3. Move into the Django project directory if needed:

```bash
cd vehicle_tracker
```

4. Run migrations:

```bash
py -3 manage.py migrate
```

5. Seed the default vehicle types:

```bash
py -3 manage.py seed_initial_data
```

6. Create an admin user if you want access to `/admin/`:

```bash
py -3 manage.py createsuperuser
```

7. Start the development server:

```bash
py -3 manage.py runserver
```

8. Open the app in your browser:

```text
http://127.0.0.1:8000/
```

## Environment Variables

The Django settings support simple local development by default.

- If `DATABASE_URL` is not set, the app uses the local SQLite database at `vehicle_tracker/db.sqlite3`
- If `DATABASE_URL` is set to a PostgreSQL connection string, Django will use PostgreSQL instead
- `DJANGO_SECRET_KEY` overrides the local development secret key
- `DJANGO_DEBUG` controls debug mode
- `DJANGO_ALLOWED_HOSTS` accepts a comma-separated host list
- `DJANGO_CSRF_TRUSTED_ORIGINS` accepts a comma-separated list of trusted HTTPS origins for deployed environments
- `DJANGO_MEDIA_ROOT` overrides where uploaded vehicle photos are stored
- `PGSSLMODE` can be used for PostgreSQL SSL settings when needed

Example PowerShell session:

```powershell
$env:DATABASE_URL = "postgresql://username:password@host:5432/dbname"
$env:DJANGO_DEBUG = "true"
$env:DJANGO_CSRF_TRUSTED_ORIGINS = "https://your-app.example.com"
py -3 vehicle_tracker\manage.py runserver
```

## Running Checks

Run the Django system check:

```bash
py -3 vehicle_tracker\manage.py check
```

Run the test suite:

```bash
py -3 vehicle_tracker\manage.py test
```

## Deployment

This repo now includes a Render-ready deployment setup:

- `build.sh` runs `collectstatic` and `migrate`
- `render.yaml` defines a Python web service and PostgreSQL database
- `.python-version` pins Python to `3.13`
- WhiteNoise serves Django static files in production

### Deploy On Render

1. Push the latest code to GitHub.
2. In Render, create a new Blueprint and connect this repository.
3. Apply the Blueprint from `render.yaml`.
4. After the first deploy finishes, open the Render shell and create an admin user:

```bash
cd vehicle_tracker
python manage.py createsuperuser
```

### Uploaded Photos In Production

Vehicle photos are uploaded to Django's `MEDIA_ROOT`.

- Locally, that is `vehicle_tracker/media/`
- On Render, uploaded files are ephemeral by default
- If you want photos to persist across deploys/restarts, attach a persistent disk and mount it at:

```text
/opt/render/project/src/vehicle_tracker/media
```

If you use a different mount path, set `DJANGO_MEDIA_ROOT` to match it.

## ERD

![ERD](erd.png)
