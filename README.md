# ZALA Terminal

This Django project is now prepared for Docker-based deployment on Coolify with PostgreSQL.

## Coolify Deployment

1. Create a new application in Coolify from this repository.
2. Choose the `Dockerfile` build pack.
3. Add a PostgreSQL service in Coolify and connect it to this app.
4. Set these environment variables in Coolify:

```env
DJANGO_SETTINGS_MODULE=nopra_fuel.settings.production
SECRET_KEY=your-long-random-secret
DEBUG=False
ATMS_PUBLIC_BASE_URL=https://your-domain.com
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CSRF_TRUSTED_ORIGINS=https://your-domain.com,https://www.your-domain.com
TIME_ZONE=Africa/Johannesburg
DATABASE_URL=postgres://USER:PASSWORD@HOST:PORT/DBNAME
DATABASE_SSL_REQUIRE=False
DJANGO_SUPERUSER_FULL_NAME=ZALA Terminal Administrator
DJANGO_SUPERUSER_EMAIL=admin@your-domain.com
DJANGO_SUPERUSER_PASSWORD=change-me
```

`REDIS_URL`, `CELERY_BROKER_URL`, and `CELERY_RESULT_BACKEND` are optional. Leave them empty if you are deploying only Django and PostgreSQL.

## What Happens On Start

The container entrypoint will:

1. Wait for PostgreSQL.
2. Run migrations.
3. Collect static files.
4. Create the first superuser when the superuser env vars are present.
5. Start Gunicorn on port `8000`.

## Local Docker Compose

For local testing:

```bash
docker compose up --build
```

That compose file includes PostgreSQL, Redis, the web app, and Celery services.
