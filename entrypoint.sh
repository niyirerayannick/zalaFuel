#!/bin/bash
set -e

echo "==> Waiting for database..."
python << END
import sys, time, dj_database_url, os
url = os.environ.get("DATABASE_URL", "")
if not url:
    print("No DATABASE_URL set, skipping wait")
    sys.exit(0)

parsed = dj_database_url.parse(url)
host = parsed.get("HOST", "localhost")
port = parsed.get("PORT", 5432)

import socket
for i in range(30):
    try:
        sock = socket.create_connection((host, int(port)), timeout=2)
        sock.close()
        print(f"Database at {host}:{port} is ready!")
        break
    except (OSError, ConnectionRefusedError):
        print(f"Waiting for {host}:{port}... ({i+1}/30)")
        time.sleep(2)
else:
    print("Could not connect to database after 60s")
    sys.exit(1)
END

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Collecting static files..."
python manage.py collectstatic --noinput

echo "==> Creating superuser if needed..."
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
import os
full_name = os.environ.get('DJANGO_SUPERUSER_FULL_NAME', 'Administrator')
email = os.environ.get('DJANGO_SUPERUSER_EMAIL', '')
password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', '')
if email and password and not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, full_name=full_name, password=password)
    print(f'Superuser {email} created')
else:
    print('Superuser already exists or env vars not set, skipping')
"

echo "==> Starting server..."
exec "$@"
