#!/bin/sh
# Prepara la instancia en cada arranque y cede el control a gunicorn.
set -e

echo "→ Aplicando migraciones"
python manage.py migrate --noinput

echo "→ Recopilando ficheros estáticos"
python manage.py collectstatic --noinput --clear >/dev/null

# Primer arranque: crea el administrador si se han indicado sus credenciales.
if [ -n "$DJANGO_ADMIN_USUARIO" ] && [ -n "$DJANGO_ADMIN_PASSWORD" ]; then
  python manage.py shell -c "
from django.contrib.auth import get_user_model
import os
U = get_user_model()
usuario = os.environ['DJANGO_ADMIN_USUARIO']
if not U.objects.filter(username=usuario).exists():
    U.objects.create_superuser(usuario, os.environ.get('DJANGO_ADMIN_EMAIL', ''), os.environ['DJANGO_ADMIN_PASSWORD'])
    print('→ Administrador', usuario, 'creado')
"
fi

exec "$@"
