#!/bin/sh
# Copia diaria de la base de datos y de los currículums, con rotación.
set -e
DESTINO=/copias
RETENER=${COPIAS_RETENER:-14}
MARCA=$(date +%Y%m%d-%H%M)

mkdir -p "$DESTINO"
tar czf "$DESTINO/practicas-$MARCA.tar.gz" -C /datos .
echo "Copia creada: practicas-$MARCA.tar.gz"

# Conserva solo las últimas N copias.
ls -1t "$DESTINO"/practicas-*.tar.gz | tail -n +$((RETENER + 1)) | while read -r antigua; do
  rm -f "$antigua"
  echo "Eliminada copia antigua: $antigua"
done
