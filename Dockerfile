FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system django \
    && useradd --system --gid django --create-home django

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY --chown=django:django . .
RUN chmod +x /app/docker-entrypoint.sh \
    && DJANGO_DEBUG=False \
       DJANGO_SECRET_KEY=build-only-static-files-secret \
       DJANGO_ALLOWED_HOSTS=localhost \
       python manage.py collectstatic --noinput

USER django

EXPOSE 8000

ENTRYPOINT ["/app/docker-entrypoint.sh"]
