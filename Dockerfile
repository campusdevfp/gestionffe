# Imagen de la aplicación. Multietapa para no arrastrar el compilador a la imagen final.
FROM python:3.12-slim AS dependencias
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt /tmp/
RUN python -m venv /opt/venv && /opt/venv/bin/pip install -r /tmp/requirements.txt

FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH" TZ=Europe/Madrid
RUN apt-get update && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 practicas
COPY --from=dependencias /opt/venv /opt/venv
WORKDIR /app
COPY --chown=practicas:practicas . /app

# Los datos persistentes viven fuera de la imagen, en volúmenes.
ENV DJANGO_DB_PATH=/datos/db.sqlite3 \
    DJANGO_ALMACEN_PRIVADO=/datos/privado \
    DJANGO_STATIC_ROOT=/app/staticfiles \
    DJANGO_STATIC_MANIFEST=1 \
    DJANGO_DEBUG=0
RUN mkdir -p /datos /app/staticfiles && chown -R practicas:practicas /datos /app/staticfiles

USER practicas
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/salud/ || exit 1
ENTRYPOINT ["/app/scripts/arranque.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", \
     "--workers", "3", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]
