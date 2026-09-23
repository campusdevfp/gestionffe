#!/usr/bin/env bash
# Prepara un VPS Ubuntu/Debian recién creado para alojar la aplicación.
# Uso:  sudo bash instalar-vps.sh usuario-despliegue
set -euo pipefail

USUARIO=${1:-practicas}
DESTINO=/opt/practicas

echo "→ Actualizando el sistema"
apt-get update && apt-get upgrade -y
apt-get install -y ca-certificates curl git ufw

echo "→ Instalando Docker"
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc 2>/dev/null \
  || curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker

echo "→ Creando el usuario de despliegue: $USUARIO"
id -u "$USUARIO" >/dev/null 2>&1 || adduser --disabled-password --gecos "" "$USUARIO"
usermod -aG docker "$USUARIO"

echo "→ Preparando $DESTINO"
mkdir -p "$DESTINO/copias"
chown -R "$USUARIO:$USUARIO" "$DESTINO"

echo "→ Cortafuegos: solo SSH, HTTP y HTTPS"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "→ Arranque automático de los contenedores al reiniciar"
systemctl enable docker

cat <<FIN

Listo. Ahora, como usuario $USUARIO:
  1. Copia compose.yaml, Caddyfile, scripts/copia.sh y .env a $DESTINO
  2. Rellena .env (dominio, clave secreta, imagen)
  3. docker login ghcr.io  (con un token de GitHub con permiso read:packages)
  4. docker compose up -d

FIN
