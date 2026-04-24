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

### Deploy On Railway

This app can be deployed to Railway from the current GitHub repository.

Recommended Railway setup:

1. Create a new Railway project.
2. Add a new service from GitHub and select this repository.
3. Leave the service `Root Directory` at the repo root (`/`) so Railway can use the checked-in `requirements.txt` and `railway.json`.
4. In the service `Variables`, set:

```text
DJANGO_SECRET_KEY=<your-random-secret>
DJANGO_DEBUG=false
DJANGO_ALLOWED_HOSTS=${{RAILWAY_PUBLIC_DOMAIN}}
DJANGO_CSRF_TRUSTED_ORIGINS=https://${{RAILWAY_PUBLIC_DOMAIN}}
```

5. Add a PostgreSQL database service to the same Railway project.
6. Copy the database service's `DATABASE_URL` reference variable into the web service.
7. Generate a public domain for the service.
8. After the app is live, open a Railway shell and create an admin user:

```bash
cd vehicle_tracker
python manage.py createsuperuser
```

### Uploaded Photos In Production

Vehicle photos are uploaded to Django's `MEDIA_ROOT`.

- Locally, that is `vehicle_tracker/media/`
- On Railway, uploaded files are ephemeral by default
- If you want photos to persist across redeploys/restarts, attach a Railway volume and mount it at:

```text
/app/media
```

When a Railway volume is attached, the app will automatically use `RAILWAY_VOLUME_MOUNT_PATH` as `MEDIA_ROOT`. You can still override that explicitly with `DJANGO_MEDIA_ROOT`.

## ERD

![ERD](erd.png)
