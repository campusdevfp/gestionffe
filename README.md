# Prácticas en empresa (FFE)

Aplicación web interna para gestionar la formación en centros de trabajo de un instituto: centro, cursos, alumnado,
empresas colaboradoras y procesos de selección, con el registro común que necesita un equipo de tutores.

Django 6 · SQLite · plantillas del propio Django · sin dependencias de frontend.

![Portada](docs/img/01-portada.png)

---

## Índice

1. [Puesta en marcha](#1-puesta-en-marcha)
2. [Los cuatro roles](#2-los-cuatro-roles)
3. [Modelo de datos](#3-modelo-de-datos)
4. [El proceso completo, con pantallas](#4-el-proceso-completo-con-pantallas)
   - [4.1 Preparar el curso (administración)](#41-preparar-el-curso-administración)
   - [4.2 Dar de alta al alumnado](#42-dar-de-alta-al-alumnado)
   - [4.3 Mantener la bolsa de empresas](#43-mantener-la-bolsa-de-empresas)
   - [4.4 Abrir un proceso de selección](#44-abrir-un-proceso-de-selección)
   - [4.5 Candidatos: los propone el tutor y también la empresa](#45-candidatos-los-propone-el-tutor-y-también-la-empresa)
   - [4.6 Resultados y cierre](#46-resultados-y-cierre)
   - [4.7 Lo que ve el alumno](#47-lo-que-ve-el-alumno)
   - [4.8 Solicitudes de contacto](#48-solicitudes-de-contacto)
   - [4.9 Informes](#49-informes)
5. [Cupo de horas y disponibilidad](#5-cupo-de-horas-y-disponibilidad)
6. [Casos de uso implementados](#6-casos-de-uso-implementados)
7. [Reglas que la aplicación impide saltarse](#7-reglas-que-la-aplicación-impide-saltarse)
8. [Quién ve qué](#8-quién-ve-qué)
9. [Contraseñas y accesos](#9-contraseñas-y-accesos)
10. [Protección de datos](#10-protección-de-datos)
11. [Formato de los CSV](#11-formato-de-los-csv)
12. [Pruebas](#12-pruebas)
13. [Producción y despliegue](#13-producción-y-despliegue)
14. [Estructura del proyecto](#14-estructura-del-proyecto)

---

## 1. Puesta en marcha

Requiere Python 3.12 o superior.

```bash
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser   # administrador
python manage.py runserver
```

Abre http://127.0.0.1:8000.

### Datos de ejemplo

En una base de datos vacía, en lugar de `createsuperuser`:

```bash
python manage.py datos_demo
```

Crea el IES Ejemplo con dos cursos, dos tutores, 16 alumnos con cupos de horas distintos, cuatro empresas y tres
procesos en distintos estados. La contraseña de todos es `practicas2026`:

| Usuario | Rol |
|---|---|
| `admin` | Administrador |
| `tutor.daw` | Tutora FFE de 2º DAW |
| `tutor.asir` | Tutor FFE de 2º ASIR |
| `51000000F` | Alumna ya seleccionada en una empresa |
| `51023757M` | Alumno en un proceso abierto |
| `empresa.demo` | Empresa Soluciones Web Henares |

Código de autorregistro de 2º DAW: `DAW-2627`.

Para empezar de cero: borra `db.sqlite3` y la carpeta `privado/`, y vuelve a ejecutar `migrate`.

### Si la aplicación se ve sin estilos

Es que no se están sirviendo los ficheros estáticos. Abre `http://127.0.0.1:8000/static/css/app.css`: debe devolver
el CSS. La aplicación los sirve también con `DEBUG=0`, así que basta con reiniciar el servidor.

---

## 2. Los cuatro roles

| Rol | Quién es | Dónde trabaja |
|---|---|---|
| **Administrador** | Jefatura de estudios o quien coordine la FFE | Panel de administración (`/admin/`) |
| **Tutor FFE** | Profesor responsable de las prácticas de uno o varios cursos | `/tutor/` |
| **Alumno** | Alumnado de un curso concreto | `/alumnado/` |
| **Empresa** | Persona de contacto de la empresa colaboradora | `/empresa/` |

Todos entran por la misma pantalla y la aplicación les lleva a su panel. Si alguien intenta abrir una dirección de
otro rol recibe un error 403.

![Pantalla de entrada](docs/img/02-login.png)

---

## 3. Modelo de datos

- **Centro**: el IES, con su código de 8 cifras. Puede haber más de uno.
- **Curso**: pertenece a un centro, tiene promoción, **un** tutor FFE y un código de autorregistro.
- **Tutor FFE**: profesor de un centro; puede tutorizar varios cursos.
- **Alumno**: pertenece a un curso; DNI/NIE, contacto, currículum, cupo de horas y disponibilidad.
- **Empresa**: **común a todos los cursos y centros**; un responsable legal y N tutores laborales.
- **Proceso**: una empresa + un curso + un puesto + unas plazas, llevado por un tutor.
- **Participación**: un alumno dentro de un proceso, con su origen, resultado y condiciones.
- **Seguimiento**: una actuación con una empresa, ligada o no a un proceso.
- **Solicitud de contacto**: petición de una empresa para ver el contacto de un alumno.
- **Comentario sobre el CV** y **acceso a CV**: comentarios del tutor y traza de descargas.

---

## 4. El proceso completo, con pantallas

### 4.1 Preparar el curso (administración)

El administrador entra en `/admin/` y crea el centro, los tutores FFE y los cursos. Es lo único que hace de forma
habitual; como superusuario puede además consultar y corregir cualquier dato.

![Panel de administración](docs/img/04-admin-inicio.png)

En cada curso se indica la promoción, el tutor FFE y el **código de autorregistro** que el tutor repartirá a su
grupo, además de si el autorregistro está abierto.

![Cursos en el admin](docs/img/05-admin-cursos.png)

Al dar de alta un tutor se crea a la vez su cuenta, con una contraseña inicial que deberá cambiar al entrar.

![Alta de tutor](docs/img/06-admin-alta-tutor.png)

### 4.2 Dar de alta al alumnado

El tutor abre su panel. Arriba, las cifras del curso; después, lo que requiere su atención (solicitudes sin
responder, procesos sin candidatos, procesos parados más de tres semanas, alumnado sin currículum), sus cursos y el
movimiento reciente del centro.

![Panel del tutor](docs/img/07-tutor-panel.png)

Hay tres vías para dar de alta al alumnado, combinables:

**Importación CSV.** Cada fila errónea se rechaza indicando línea y motivo, sin frenar las demás. Las contraseñas
iniciales se muestran una sola vez y se descargan en un CSV para repartirlas en clase.

![Importación de alumnado](docs/img/09-tutor-importar.png)

**Alta manual**, un alumno suelto con el mismo resultado, y **autorregistro**: el alumno se da de alta él mismo con
el código de su curso, y solo en ese curso.

![Autorregistro del alumnado](docs/img/03-autorregistro.png)

El listado del curso muestra CV, horas pendientes, procesos y situación de cada alumno, y permite restablecer
contraseñas.

![Alumnado del curso](docs/img/08-tutor-alumnado.png)

En la ficha de cada alumno el tutor descarga su CV, le deja comentarios (que el alumno lee en su panel y las
empresas nunca ven), fija su cupo de horas y consulta quién ha descargado su currículum.

![Ficha del alumno](docs/img/13-tutor-ficha-alumno.png)

### 4.3 Mantener la bolsa de empresas

Las empresas son comunes a todos los cursos y tutores: cualquiera puede abrir procesos con ellas. Se crean a mano,
se importan por CSV o se registran ellas mismas desde la portada.

![Empresas](docs/img/14-tutor-empresas.png)

La ficha reúne los datos, el responsable legal, los tutores laborales, todos los procesos del centro con esa empresa
y el histórico de actuaciones. Desde aquí se registra cada llamada, visita o email, y se le da acceso a la
aplicación.

![Ficha de empresa](docs/img/15-tutor-empresa.png)

### 4.4 Abrir un proceso de selección

Un proceso es una empresa, un curso, un puesto y unas plazas. Si ya se han acordado, se anotan también las
condiciones: fechas, horas, jornada y tutor laboral. Nace en estado **Iniciado**.

![Nuevo proceso](docs/img/11-tutor-nuevo-proceso.png)

El registro de procesos es la pantalla que evita las llamadas duplicadas: **todos los tutores del centro ven todos
los procesos**, con su empresa, curso, tutor responsable, estado y plazas cubiertas, y se filtra por cualquiera de
esos campos. Modificar un proceso, en cambio, solo puede hacerlo su tutor responsable o el tutor del curso.

![Registro de procesos](docs/img/10-tutor-procesos.png)

### 4.5 Candidatos: los propone el tutor y también la empresa

En la ficha del proceso, el tutor marca a los alumnos de su curso que se presentan. Junto a cada nombre aparecen las
horas que le quedan y la jornada que puede hacer, que es lo que determina si encaja en ese puesto.

![Ficha del proceso](docs/img/12-tutor-proceso.png)

La empresa, desde su panel, también puede proponer alumnado registrado del curso del proceso. Esas candidaturas
quedan marcadas como «Propuesto por la empresa» y siguen el mismo circuito.

![Proceso visto por la empresa](docs/img/21-empresa-proceso.png)

Cuando la empresa empieza a valorar candidaturas, el tutor pasa el proceso a **Abierto**.

### 4.6 Resultados y cierre

La empresa comunica su decisión al tutor, que la registra en cada candidato: seleccionado, no seleccionado o
retirado. Al seleccionar se pueden ajustar las condiciones de ese alumno si difieren de las del proceso (por
ejemplo, menos horas). Después el proceso pasa a **Cerrado** y queda guardada la fecha.

La empresa consulta en todo momento sus procesos, sus candidatos y el alumnado visible.

![Panel de la empresa](docs/img/20-empresa-panel.png)

![Alumnado visible para la empresa](docs/img/22-empresa-alumnado.png)

### 4.7 Lo que ve el alumno

Su panel abre con su situación. Si ha sido seleccionado: empresa, puesto, tutor laboral, fechas, horas y jornada.
Debajo, sus procesos en marcha y cerrados, su tutor FFE, sus datos, su currículum y los comentarios del tutor.

![Panel del alumno](docs/img/18-alumno-panel.png)

En sus datos indica el teléfono, la jornada que puede hacer y su disponibilidad, que es lo que leen las empresas.

![Datos del alumno](docs/img/19-alumno-datos.png)

### 4.8 Solicitudes de contacto

Una empresa puede pedir el contacto de un alumno antes de seleccionarlo. La petición llega al tutor del curso, que
la acepta o la rechaza. Al seleccionar a un alumno, el contacto se comparte automáticamente.

![Solicitudes de contacto](docs/img/16-tutor-solicitudes.png)

### 4.9 Informes

Seis listados, cada uno en Excel (con filtros y anchos ya puestos) y en PDF (apaisado, con el centro y la fecha de
generación). Todos se limitan al centro del tutor que los descarga.

![Informes](docs/img/17-tutor-informes.png)

| Informe | Para qué sirve |
|---|---|
| Procesos | Estado de la campaña: empresa, curso, tutor, plazas y condiciones |
| Alumnado por proceso | Una fila por alumno y proceso, con resultado y condiciones |
| Alumnado | Contacto, curso, tutor, CV y situación de prácticas |
| Empresas | Datos fiscales, contacto, tutores laborales y actividad con el centro |
| Tutores FFE | Cursos, alumnado y procesos de cada uno |
| Seguimientos | Histórico de contactos con empresas |

La aplicación se usa igual desde el móvil: la barra se reordena y el menú se desliza en horizontal.

![Vista en móvil](docs/img/24-movil-panel.png)

---

## 5. Cupo de horas y disponibilidad

Las horas de FFE no son iguales para todo el mundo: cambian con el ciclo y con las exenciones por experiencia
laboral. Por eso el cupo es un dato de cada alumno, no del proceso:

- **Horas requeridas**: las que debe realizar. Las fija el tutor (por defecto 370).
- **Horas exentas**: convalidadas o ya realizadas.
- **Horas comprometidas**: las que suman los procesos en los que ya ha sido seleccionado.
- **Horas pendientes** = requeridas − exentas − comprometidas. Es la cifra que se muestra en todas las listas.

Junto a ellas, el alumno indica la **jornada** que puede hacer y una línea de **disponibilidad** («tardes a partir
de las 15:30; no puedo los viernes»).

La empresa ve las horas pendientes y la disponibilidad de cada candidato, porque es lo que determina si encaja en el
puesto, pero no ve su email ni su teléfono hasta que lo selecciona o el tutor lo autoriza.

La aplicación no deja comprometer más horas de las pendientes: si el proceso son 370 horas y al alumno le quedan
200, avisa y obliga a ajustar las horas de esa participación. Eso permite, por ejemplo, repartir 370 horas entre dos
empresas dando a cada participación sus propias horas.

---

## 6. Casos de uso implementados

### Administrador

| # | Caso de uso |
|---|---|
| A1 | Dar de alta un centro con su código |
| A2 | Crear cursos con promoción, tutor y código de autorregistro |
| A3 | Abrir o cerrar el autorregistro de un curso |
| A4 | Dar de alta tutores FFE, creando su cuenta |
| A5 | Restablecer la contraseña de un tutor, alumno o empresa |
| A6 | Consultar y corregir cualquier dato del sistema |
| A7 | Consultar la traza de accesos a los currículums (solo lectura) |

### Tutor FFE

| # | Caso de uso |
|---|---|
| T1 | Consultar su panel con tareas pendientes y el pulso del centro |
| T2 | Importar alumnado por CSV con informe de errores y credenciales |
| T3 | Dar de alta un alumno a mano |
| T4 | Consultar el alumnado de un curso |
| T5 | Ver la ficha de un alumno: CV, comentarios, procesos y accesos |
| T6 | Comentar el currículum de un alumno |
| T7 | Fijar el cupo de horas de un alumno |
| T8 | Restablecer la contraseña de un alumno o de una empresa |
| T9 | Crear, importar y editar empresas |
| T10 | Mantener responsable legal y tutores laborales |
| T11 | Dar acceso a la aplicación a una empresa |
| T12 | Registrar actuaciones con una empresa o dentro de un proceso |
| T13 | Abrir un proceso de selección |
| T14 | Añadir candidatos del curso al proceso |
| T15 | Registrar el resultado de cada candidato y sus condiciones |
| T16 | Cambiar el estado del proceso |
| T17 | Consultar y filtrar todos los procesos del centro |
| T18 | Resolver solicitudes de contacto |
| T19 | Descargar los seis informes en Excel y PDF |

### Alumno

| # | Caso de uso |
|---|---|
| E1 | Registrarse con el código de su curso |
| E2 | Cambiar su contraseña; recuperarla a través de su tutor |
| E3 | Consultar su situación y sus condiciones de prácticas |
| E4 | Ver sus procesos en marcha y cerrados |
| E5 | Ver quién es su tutor FFE y cómo contactarle |
| E6 | Actualizar contacto, jornada y disponibilidad |
| E7 | Subir, sustituir o borrar su currículum |
| E8 | Leer los comentarios de su tutor sobre el CV |
| E9 | Descargar todos sus datos en JSON |

### Empresa

| # | Caso de uso |
|---|---|
| M1 | Registrarse desde la portada |
| M2 | Mantener sus datos, responsable legal y tutores laborales |
| M3 | Consultar sus procesos en marcha y cerrados |
| M4 | Ver candidatos con CV, horas pendientes y disponibilidad |
| M5 | Proponer alumnado registrado del curso del proceso |
| M6 | Solicitar el contacto de un alumno |
| M7 | Ver el contacto de quien ha sido seleccionado |

---

## 7. Reglas que la aplicación impide saltarse

Están en los modelos, así que se aplican tanto en la aplicación como en el panel de administración:

1. Un candidato tiene que ser del curso del proceso.
2. Nadie aparece dos veces en el mismo proceso.
3. No se seleccionan más alumnos que plazas tiene el proceso.
4. Un alumno solo puede estar seleccionado en una empresa; si se intenta otra, se indica dónde está ya colocado.
5. No se comprometen más horas de las que le quedan pendientes al alumno.
6. Un proceso con alumnado seleccionado no se cierra sin fecha de inicio y horas.
7. El tutor laboral de un proceso pertenece a la empresa del proceso.
8. El autorregistro exige un código válido y el autorregistro del curso abierto.
9. DNI/NIE, CIF y código de centro se validan con su dígito o letra de control.
10. Un tutor solo abre y modifica procesos de sus cursos, aunque vea todos los del centro.
11. Una empresa solo propone candidatos en sus propios procesos y mientras estén abiertos.
12. No se borra un tutor laboral con alumnado asignado.

---

## 8. Quién ve qué

| Dato | Administrador | Tutor del curso | Otro tutor del centro | Empresa | El propio alumno |
|---|---|---|---|---|---|
| Contacto del alumno | Sí | Sí | Sí | Solo si lo selecciona o si el tutor lo autoriza | Sí |
| Currículum | Sí | Sí | Sí (queda registrado) | Cursos donde tiene procesos (queda registrado) | Sí |
| Horas pendientes y disponibilidad | Sí | Sí | Sí | Sí | Sí |
| Comentarios sobre el CV | Sí | Sí (los escribe) | Los lee | No | Sí |
| Procesos del centro | Sí | Sí | Sí | Solo los suyos | Solo los suyos |
| Modificar un proceso | Sí | Sí | No | No | No |
| Informes del centro | Sí | Sí | Sí | No | No |
| Traza de accesos al CV | Sí | Sí | Sí | No | Sí |

---

## 9. Contraseñas y accesos

Nadie puede leer las contraseñas: se guardan como hash PBKDF2 con sal, y ni el administrador ni la base de datos
permiten recuperarlas. Lo que sí puede hacerse es sustituirlas por otra nueva.

La aplicación no envía correos, así que la recuperación es presencial:

- **Alumnado y empresas**: su tutor FFE les genera una contraseña nueva desde el listado del curso, la ficha del
  alumno o la ficha de la empresa. Se muestra una sola vez y hay que cambiarla al entrar.
- **Profesorado**: la administración usa la acción «Restablecer la contraseña» en el admin.
- **El propio administrador**: `python manage.py changepassword <usuario>`.
- **Cualquiera**: cambia la suya desde el enlace «Contraseña» de la barra superior, indicando la actual.

Salvaguardas de los restablecimientos:

- La contraseña nueva se muestra una sola vez y el usuario **tiene que cambiarla** en su siguiente acceso, así que
  quien la generó deja de conocerla en cuanto la persona entra.
- Cada restablecimiento **queda registrado** (quién, a quién y cuándo) en el registro de acciones del admin, en
  `/admin/admin/logentry/`, que es de solo lectura.
- Un tutor solo puede restablecer las de **su propio alumnado** y las de empresas; nunca las de otros tutores.
- Cambiar la propia contraseña exige la actual, de modo que una sesión abierta y olvidada no basta para
  apropiarse de una cuenta.

---

## 10. Protección de datos

El marco aplicable es el RGPD y la LOPDGDD (Ley Orgánica 3/2018); no existe una «LOPD de 2026». Lo resuelto:

- **Información y consentimiento**: página `/privacidad/` pública, enlazada desde el pie y desde los dos formularios
  de alta, con casilla de confirmación obligatoria cuya fecha se guarda.
- **Minimización**: las empresas ven perfil profesional (curso, CV, horas y disponibilidad); el contacto solo tras
  seleccionar o con autorización del tutor.
- **Trazabilidad**: cada descarga de un CV queda registrada y el registro no se puede editar.
- **Derechos**: descarga de los propios datos en JSON y borrado del CV desde el panel del alumno.
- **Conservación limitada**: `python manage.py purgar_datos --ejecutar` anonimiza al alumnado de cursos terminados
  hace más años de los configurados y borra sus CV, comentarios, solicitudes y trazas, conservando las
  participaciones sin datos identificativos. Sin `--ejecutar` solo simula.
- **Seguridad**: contraseñas con hash y cambio obligatorio de la inicial, permisos por rol, CV fuera de las carpetas
  públicas con nombre aleatorio, HTTPS con HSTS y cabeceras de seguridad al desactivar `DEBUG`.

![Información de protección de datos](docs/img/23-privacidad.png)

Configura `LOPD_RESPONSABLE`, `LOPD_EMAIL`, `LOPD_DPD` y `LOPD_CONSERVACION_ANIOS`: alimentan esa página y el pie.
La plantilla del registro de actividades del art. 30 RGPD está en `docs/registro-actividades-tratamiento.md`.

---

## 11. Formato de los CSV

UTF-8 con cabecera en la primera fila; separador `;` (también se acepta `,`). Hay ejemplos en `ejemplos/`.

- **Alumnado** (el curso se elige al subir): `dni;nombre;apellidos;email;telefono`
- **Empresas**: `cif;nombre;direccion;web;persona_contacto;email;telefono`

Las filas con errores se rechazan una a una, indicando la línea y el motivo, sin impedir importar el resto.

---

## 12. Pruebas

```bash
python manage.py test
```

Cubren las reglas de los procesos, el cupo de horas, la propuesta de candidatos por la empresa, la visibilidad entre
roles y centros, el autorregistro, la importación CSV, las contraseñas, los permisos sobre los CV, la protección de
datos y la generación de los seis informes en ambos formatos.

---

## 13. Producción y despliegue

Para poner la aplicación en un servidor con contenedores, HTTPS automático y despliegue continuo desde GitHub, la
guía completa está en **[`docs/despliegue.md`](docs/despliegue.md)**: preparación del VPS, DNS, `docker compose`,
copias de seguridad y operación diaria. En resumen:

```bash
# En el VPS, una sola vez
bash scripts/instalar-vps.sh practicas
cp .env.example .env && nano .env
docker compose up -d
```

A partir de ahí, cada `git push` a `main` pasa las pruebas, construye la imagen y la despliega solo.

Variables de entorno:

| Variable | Uso |
|---|---|
| `DJANGO_SECRET_KEY` | Clave secreta propia (obligatoria) |
| `DJANGO_DEBUG=0` | Desactiva el modo depuración y activa cookies seguras |
| `DJANGO_ALLOWED_HOSTS` | Dominios separados por comas |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Por ejemplo `https://practicas.miinstituto.es` |
| `DJANGO_DB_PATH` | Ruta de la base de datos |
| `DJANGO_ALMACEN_PRIVADO` | Carpeta de los CV |
| `LOPD_RESPONSABLE`, `LOPD_EMAIL`, `LOPD_DPD`, `LOPD_CONSERVACION_ANIOS` | Datos del responsable del tratamiento |
| `DJANGO_STATIC_MANIFEST=1` | Estáticos con hash en el nombre y caché de un mes (lo activa la imagen) |

Sin contenedores: ejecuta `python manage.py collectstatic` y sirve la aplicación con Gunicorn detrás de Nginx o
Apache, con HTTPS. Los estáticos los sirve WhiteNoise desde la propia aplicación; la carpeta de los CV no debe
publicarse nunca en el servidor web.

Haz copias de seguridad cifradas de `db.sqlite3` y de la carpeta de CV: contienen datos personales.

**Sobre SQLite.** Da de sobra para esto. Un centro maneja cientos de alumnos y unas decenas de empresas al año, con
muy pocas escrituras simultáneas; SQLite en modo WAL soporta lecturas concurrentes sin bloqueos y escribe de una en
una, lo que aquí no se nota. El límite práctico no es el volumen de datos, sino la escritura simultánea intensa, que
en esta aplicación no se da. Si algún día creciera, pasar a PostgreSQL es tocar `DATABASES` y migrar.

---

## 14. Estructura del proyecto

```
config/        configuración del proyecto
cuentas/       usuario con rol, cambio de contraseña obligatorio, control de acceso
practicas/
  models.py            centro, cursos, tutores, alumnado, empresas, procesos y participaciones
  validadores.py       DNI/NIE, CIF, código de centro, teléfono, PDF
  permisos.py          quién ve y quién gestiona cada cosa
  importacion.py       importación CSV
  exportacion.py       informes en Excel y PDF
  views/               vistas por rol, ficha de empresa compartida, privacidad y descargas
  admin.py             panel de administración
  management/commands/ datos_demo y purgar_datos
templates/     plantillas
static/        CSS
ejemplos/      CSV de ejemplo
docs/          guía funcional, despliegue, RAT y capturas de esta documentación
scripts/       arranque del contenedor, copias y preparación del VPS
Dockerfile, compose.yaml, Caddyfile, .env.example
.github/workflows/desplegar.yml
```
