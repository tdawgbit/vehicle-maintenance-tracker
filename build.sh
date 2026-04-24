#!/usr/bin/env bash

set -o errexit

cd vehicle_tracker

python manage.py collectstatic --no-input
python manage.py migrate
