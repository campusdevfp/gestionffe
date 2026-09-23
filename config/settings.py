"""Configuración del proyecto de gestión de prácticas (FCT)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# En producción define DJANGO_SECRET_KEY, DJANGO_DEBUG=0 y DJANGO_ALLOWED_HOSTS.
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "solo-desarrollo-cambia-esta-clave-en-produccion"
)
DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "cuentas",
    "practicas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sirve los ficheros estáticos desde el propio contenedor, comprimidos y con caché.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "cuentas.middleware.CambioPasswordObligatorioMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "practicas.context_processors.navegacion",
                "practicas.context_processors.responsable",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("DJANGO_DB_PATH", BASE_DIR / "db.sqlite3"),
        "OPTIONS": {
            # Evita bloqueos con varios usuarios simultáneos.
            "transaction_mode": "IMMEDIATE",
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
        },
    }
}

AUTH_USER_MODEL = "cuentas.Usuario"
LOGIN_URL = "cuentas:login"
LOGIN_REDIRECT_URL = "inicio"
LOGOUT_REDIRECT_URL = "cuentas:login"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = Path(os.environ.get("DJANGO_STATIC_ROOT", BASE_DIR / "staticfiles"))
# Con manifiesto los ficheros llevan hash en el nombre y se pueden cachear un mes; requiere
# haber ejecutado collectstatic, así que solo se activa en el contenedor (DJANGO_STATIC_MANIFEST=1).
CON_MANIFIESTO = os.environ.get("DJANGO_STATIC_MANIFEST", "0") == "1"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage" if CON_MANIFIESTO
                    else "whitenoise.storage.CompressedStaticFilesStorage"},
}
WHITENOISE_MAX_AGE = 60 * 60 * 24 * 30 if CON_MANIFIESTO else 0

# Los CV NO se guardan en una carpeta pública: se sirven desde una vista con control de acceso.
ALMACEN_PRIVADO = Path(os.environ.get("DJANGO_ALMACEN_PRIVADO", BASE_DIR / "privado"))
CV_TAMANO_MAXIMO = 5 * 1024 * 1024  # 5 MB
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

SESSION_COOKIE_AGE = 60 * 60 * 8  # una jornada
SESSION_COOKIE_HTTPONLY = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# Detrás de Caddy o Nginx, Django tiene que saber que la petición original llegó por HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_EXPIRE_AT_BROWSER_CLOSE = True
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# Datos del responsable del tratamiento, para la información de protección de datos.
RESPONSABLE = {
    "nombre": os.environ.get("LOPD_RESPONSABLE", "el centro educativo"),
    "email": os.environ.get("LOPD_EMAIL", "secretaria@example.com"),
    "dpd": os.environ.get("LOPD_DPD", "protecciondedatos@example.com"),
    "conservacion_anios": int(os.environ.get("LOPD_CONSERVACION_ANIOS", "4")),
}

MESSAGE_TAGS = {40: "error", 30: "aviso", 25: "ok", 20: "info"}
