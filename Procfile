web: gunicorn config.wsgi:application --workers 4 --bind 0.0.0.0:$PORT --timeout 120 --access-logfile - --error-logfile -
worker: celery -A config.celery worker --loglevel=info --concurrency=4
beat: celery -A config.celery beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
release: python manage.py migrate --noinput
