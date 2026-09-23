# Despliegue en un VPS de IONOS con dominio de OVHcloud

Despliegue con contenedores y actualización automática: cada cambio que llegue a `main` pasa las pruebas, se
empaqueta como imagen y se publica en el VPS sin que tengas que entrar a mano.

```
  Tu portátil            GitHub                         VPS de IONOS
  ───────────            ──────                         ────────────
  git push main  ──▶  pruebas (manage.py test)
                      build de la imagen  ──▶  ghcr.io/usuario/practicas-empresa
                      ssh al VPS ─────────────▶  docker compose pull && up -d
                                                    ├── proxy (Caddy) :80 :443 ─ HTTPS automático
                                                    ├── app (gunicorn) :8000
                                                    └── copias (tar diario)
                                                 volumen «datos»: db.sqlite3 + privado/
```

## Resumen: de cero a producción

Si ya te manejas con Docker, esto es todo. Cada apartado está detallado más abajo.

```bash
# 1. En OVH: registro A de «practicas» → IP del VPS.  Comprueba: dig +short practicas.midominio.es

# 2. En el VPS, como root, una sola vez
bash scripts/instalar-vps.sh practicas

# 3. Como usuario practicas
cd /opt/practicas
# copia aquí compose.yaml, Caddyfile, scripts/ y .env
cp .env.example .env && nano .env          # dominio, clave secreta, imagen, datos LOPD
echo TOKEN_GITHUB | docker login ghcr.io -u TU_USUARIO --password-stdin
docker compose up -d

# 4. En GitHub → Settings → Secrets → Actions
#    VPS_HOST, VPS_USUARIO, VPS_SSH_KEY, GHCR_TOKEN

# A partir de aquí, desplegar es:
git push
```

Piezas que ya están en el repositorio:

| Fichero | Para qué |
|---|---|
| `Dockerfile` | Imagen de la aplicación (Python 3.12, gunicorn, usuario sin privilegios) |
| `scripts/arranque.sh` | Migra, recopila estáticos y crea el administrador en el primer arranque |
| `compose.yaml` | Los tres servicios y los volúmenes |
| `Caddyfile` | Proxy con certificado de Let's Encrypt automático |
| `scripts/copia.sh` | Copia diaria con rotación |
| `scripts/instalar-vps.sh` | Prepara el VPS desde cero |
| `.github/workflows/desplegar.yml` | Pruebas, imagen y despliegue |
| `.env.example` | Plantilla de la configuración del servidor |

---

## 1. El dominio en OVHcloud

En el panel de OVH, zona DNS del dominio, añade un registro apuntando a la IP del VPS (la tienes en el panel de
IONOS, apartado del servidor):

| Tipo | Subdominio | Destino | TTL |
|---|---|---|---|
| A | `practicas` | `IP.DEL.VPS` | 600 |
| AAAA | `practicas` | IPv6 del VPS, si la tiene | 600 |

Quedará como `practicas.midominio.es`. Comprueba que ha propagado antes de seguir; con TTL bajo suele tardar
minutos:

```bash
dig +short practicas.midominio.es
```

Caddy pedirá el certificado solo cuando el dominio ya resuelva a la IP, así que este paso va primero.

---

## 2. Preparar el VPS

Entra por SSH como root y ejecuta el script de preparación, que instala Docker, crea el usuario de despliegue,
abre el cortafuegos y prepara `/opt/practicas`:

```bash
ssh root@IP.DEL.VPS
curl -fsSL https://raw.githubusercontent.com/USUARIO/REPOSITORIO/main/scripts/instalar-vps.sh -o instalar-vps.sh
bash instalar-vps.sh practicas
```

Si prefieres no descargar nada, copia el fichero `scripts/instalar-vps.sh` del repositorio y ejecútalo.

Después, asegura el acceso SSH (recomendable en IONOS, donde la IP se escanea desde el minuto uno):

```bash
# En tu portátil, si aún no tienes clave:
ssh-keygen -t ed25519 -C "despliegue practicas"
ssh-copy-id -i ~/.ssh/id_ed25519.pub practicas@IP.DEL.VPS

# En el VPS, desactiva contraseña y acceso directo de root:
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/;s/^#\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

---

## 3. Primera instalación

Como usuario `practicas`, deja en `/opt/practicas` los cuatro ficheros que necesita el servidor:

```bash
ssh practicas@IP.DEL.VPS
cd /opt/practicas
# Desde tu portátil, o con scp/git:
#   scp compose.yaml Caddyfile .env.example practicas@IP:/opt/practicas/
#   scp -r scripts practicas@IP:/opt/practicas/
cp .env.example .env
nano .env
```

Rellena `.env`. Lo imprescindible:

```ini
IMAGEN=ghcr.io/USUARIO/REPOSITORIO:latest
DOMINIO=practicas.midominio.es
EMAIL_TLS=informatica@midominio.es
DJANGO_SECRET_KEY=...          # genera una con el comando de abajo
DJANGO_ALLOWED_HOSTS=practicas.midominio.es
DJANGO_CSRF_TRUSTED_ORIGINS=https://practicas.midominio.es
DJANGO_ADMIN_USUARIO=admin
DJANGO_ADMIN_PASSWORD=...      # solo para el primer arranque
LOPD_RESPONSABLE=IES ...
```

Para la clave secreta:

```bash
docker run --rm python:3.12-slim python -c "import secrets;print(secrets.token_urlsafe(64))"
```

Da acceso al registro de imágenes de GitHub (necesitas un *personal access token* clásico con permiso
`read:packages`) y arranca:

```bash
echo TU_TOKEN | docker login ghcr.io -u TU_USUARIO_GITHUB --password-stdin
docker compose up -d
docker compose logs -f app
```

En el primer arranque la aplicación migra la base de datos, recopila los estáticos y crea el administrador. Caddy
pide el certificado en segundos. Abre `https://practicas.midominio.es`.

Cuando compruebes que entras, borra del `.env` las tres líneas `DJANGO_ADMIN_*` y ejecuta `docker compose up -d`:
ya no hacen falta y es una contraseña menos guardada en texto plano.

---

## 4. Despliegue automático

### Secretos del repositorio

En GitHub, *Settings → Secrets and variables → Actions*:

| Secreto | Valor |
|---|---|
| `VPS_HOST` | IP del VPS |
| `VPS_USUARIO` | `practicas` |
| `VPS_SSH_KEY` | Contenido de la clave **privada** de despliegue (`~/.ssh/id_ed25519`) |
| `VPS_PUERTO` | Solo si cambiaste el puerto SSH |
| `GHCR_TOKEN` | Token con `read:packages`, el mismo del paso anterior |

Conviene generar un par de claves exclusivo para el despliegue en lugar de reutilizar el tuyo personal:

```bash
ssh-keygen -t ed25519 -f ~/.ssh/despliegue_practicas -C "github actions"
ssh-copy-id -i ~/.ssh/despliegue_practicas.pub practicas@IP.DEL.VPS
cat ~/.ssh/despliegue_practicas      # esto es lo que pegas en VPS_SSH_KEY
```

### Qué hace el flujo

`.github/workflows/desplegar.yml` tiene tres trabajos encadenados:

1. **pruebas** — `manage.py check --deploy` y las 70 pruebas. Se ejecuta también en cada *pull request*.
2. **imagen** — solo en `main`: construye la imagen y la publica en `ghcr.io` con dos etiquetas, `latest` y el hash
   del commit.
3. **desplegar** — entra por SSH, hace `docker compose pull && up -d`, limpia imágenes viejas y espera a que el
   contenedor se declare sano. Si no lo consigue en dos minutos y medio, el despliegue falla y te avisa.

Como las pruebas van delante, un fallo nunca llega al servidor. A partir de aquí, publicar un cambio es:

```bash
git add -A && git commit -m "Lo que sea" && git push
```

El entorno `produccion` del trabajo de despliegue permite, si lo configuras en GitHub, exigir tu aprobación manual
antes de tocar el servidor. Útil en época de matrícula.

---

## 5. Operación diaria

```bash
cd /opt/practicas

docker compose ps                    # estado de los tres servicios
docker compose logs -f app           # registro de la aplicación
docker compose logs -f proxy         # certificado y accesos

# Ejecutar comandos de gestión
docker compose exec app python manage.py changepassword admin
docker compose exec app python manage.py purgar_datos            # simula
docker compose exec app python manage.py purgar_datos --ejecutar # anonimiza

# Volver a la versión anterior si algo sale mal
docker compose pull app
IMAGEN=ghcr.io/USUARIO/REPOSITORIO:HASH_ANTERIOR docker compose up -d app
```

### Copias de seguridad

El servicio `copias` genera cada 24 horas un `.tar.gz` con la base de datos y los currículums en
`/opt/practicas/copias`, y conserva los últimos 14 (`COPIAS_RETENER`).

**Esas copias contienen datos personales**, así que sácalas del VPS y cífralas. Por ejemplo, desde un equipo del
centro, con una tarea programada:

```bash
rsync -az practicas@IP.DEL.VPS:/opt/practicas/copias/ /ruta/local/copias-practicas/
```

Restaurar:

```bash
docker compose stop app
docker run --rm -v practicas_datos:/datos -v /opt/practicas/copias:/copias alpine \
  sh -c "rm -rf /datos/* && tar xzf /copias/practicas-AAAAMMDD-HHMM.tar.gz -C /datos"
docker compose start app
```

Prueba la restauración una vez al año; una copia que no se ha restaurado nunca no es una copia.

---

## 6. Detalles que conviene saber

**SQLite en contenedor.** La base de datos vive en el volumen `datos`, no en la imagen, así que sobrevive a los
despliegues. Gunicorn arranca con tres procesos; SQLite en modo WAL lo lleva sin problema para el uso de un centro.
No escales la aplicación a varias réplicas: con SQLite tienen que compartir el mismo fichero y el mismo servidor.

**Estáticos.** Los sirve WhiteNoise desde el propio contenedor, comprimidos y con nombre con hash, así que no hace
falta montar volúmenes de estáticos ni configurarlos en Caddy.

**Los currículums** están en el mismo volumen, en `/datos/privado`, fuera de cualquier carpeta pública, y solo se
descargan a través de la vista que comprueba permisos y registra el acceso.

**Recursos.** El VPS más pequeño de IONOS (1 vCPU, 2 GB) sobra: los tres contenedores no llegan a 400 MB de
memoria. Si el servidor tiene poca RAM, añade un fichero de intercambio antes de construir nada pesado.

**Actualizaciones del sistema.** `unattended-upgrades` para los parches de seguridad del VPS, y `docker compose
pull` se encarga de la aplicación. La imagen base de Python se refresca cada vez que Actions reconstruye.

**Si el certificado no sale.** Casi siempre es DNS: comprueba con `dig` que el dominio apunta al VPS y que los
puertos 80 y 443 están abiertos (`sudo ufw status`). Caddy reintenta solo; mira `docker compose logs proxy`.

**Restablecimientos de contraseña.** Cada vez que un tutor o la administración restablecen una contraseña, queda
registrado quién lo hizo y a quién, y se consulta en `https://tu-dominio/admin/admin/logentry/`. Ese registro es de
solo lectura, ni siquiera desde el admin se puede editar o borrar.

**Si ves «CSRF verification failed»** al enviar un formulario, falta tu dominio en `DJANGO_CSRF_TRUSTED_ORIGINS`
(con `https://` delante).
