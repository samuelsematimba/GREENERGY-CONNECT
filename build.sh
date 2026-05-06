#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate

# Create superuser if not exists
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='SAMUEL').exists():
    User.objects.create_superuser('SAMUEL', 'samuelsematimba14@gmail.com', 'semat@123')
    print('Superuser created.')
else:
    print('Superuser already exists.')
"