# Guía funcional · Prácticas en empresa (FFE)

Qué hace la aplicación, quién hace cada cosa y en qué orden, sin capturas. Para la versión ilustrada, con las
pantallas de cada paso, mira el `README.md` del proyecto.

---

## 1. Para qué sirve

Gestiona todo el ciclo de la formación en centros de trabajo de un instituto:

1. El centro y sus cursos existen en la aplicación, cada uno con su tutor FFE.
2. El tutor da de alta a su alumnado y mantiene la bolsa de empresas colaboradoras.
3. Con cada empresa se abre un **proceso de selección** para un curso concreto.
4. Los alumnos que el tutor propone entran como candidatos del proceso.
5. La empresa valora las candidaturas; el tutor registra el resultado de cada alumno.
6. Al cerrar el proceso, quien ha sido seleccionado conoce su empresa, su tutor laboral, las fechas, las horas y la
   jornada.

Todo lo que ocurre queda registrado y es visible para el resto de tutores del centro, que es el problema que suele
haber cuando varios profesores llaman a las mismas empresas.

---

## 2. Los cuatro roles

| Rol | Quién es | Dónde trabaja |
|---|---|---|
| **Administrador** | Jefatura de estudios o quien gestione la FFE en el centro | Panel de administración (`/admin/`) |
| **Tutor FFE** | Profesor responsable de las prácticas de uno o varios cursos | Aplicación (`/tutor/`) |
| **Alumno** | Alumnado de un curso concreto | Aplicación (`/alumnado/`) |
| **Empresa** | Persona de contacto de la empresa colaboradora | Aplicación (`/empresa/`) |

Cada usuario tiene exactamente un rol. Al entrar, la aplicación le lleva a su panel; si intenta abrir una dirección
de otro rol recibe un error 403.

---

## 3. El modelo de datos en una frase cada uno

- **Centro**: el IES, con su código de 8 cifras. Puede haber más de uno.
- **Curso**: pertenece a un centro, tiene promoción (año de inicio y fin), **un** tutor FFE y un código de
  autorregistro.
- **Tutor FFE**: profesor de un centro; puede tutorizar varios cursos.
- **Alumno**: pertenece a un curso; tiene DNI/NIE, contacto, cupo de horas, disponibilidad y, opcionalmente,
  currículum en PDF.
- **Empresa**: **común a todos los cursos y centros**; tiene un responsable legal y N tutores laborales.
- **Proceso**: una empresa + un curso + un puesto + un número de plazas, llevado por un tutor.
- **Participación**: un alumno dentro de un proceso, con su resultado y, si es seleccionado, sus condiciones.
- **Seguimiento**: una actuación (llamada, email, visita, entrevista) con una empresa, ligada o no a un proceso.
- **Solicitud de contacto**: petición de una empresa para ver los datos de contacto de un alumno.
- **Comentario sobre el CV**: observación del tutor sobre el currículum de un alumno.
- **Acceso a CV**: traza de quién ha descargado cada currículum.

---

## 4. El proceso completo, paso a paso

### Paso 1 · Puesta en marcha (administrador)

1. Entra en `/admin/` y crea el **centro** con su código.
2. Crea los **tutores FFE**: en el mismo formulario se indica el usuario y la contraseña inicial, y la aplicación
   crea la cuenta con rol de tutor y marca que debe cambiar la contraseña al entrar.
3. Crea los **cursos**: nombre (por ejemplo «2º DAW»), promoción, centro, tutor y **código de autorregistro** (por
   ejemplo `DAW-2627`). Decide si el autorregistro está abierto.

Esto es lo único que hace el administrador de forma habitual. Como superusuario puede además consultar y corregir
cualquier dato.

### Paso 2 · Alumnado (tutor FFE)

Tres vías, que pueden combinarse:

- **Importación CSV**: `dni;nombre;apellidos;email;telefono`. Cada fila errónea se rechaza indicando línea y motivo,
  sin frenar las demás. Se genera una contraseña inicial por alumno, que se muestra una sola vez y se puede
  descargar en un CSV para repartirla en clase.
- **Alta manual**: un formulario para un alumno suelto, con el mismo resultado.
- **Autorregistro**: el tutor da el código del curso a su grupo; cada alumno se registra él mismo desde la portada.
  Solo puede registrarse en el curso de ese código, y solo si el tutor tiene el autorregistro abierto. Al registrarse
  debe confirmar que ha leído la información de protección de datos.

En los tres casos el alumno entra con su **DNI como usuario**.

### Paso 3 · Empresas (tutor FFE)

- Se crean a mano, se importan por CSV (`cif;nombre;direccion;web;persona_contacto;email;telefono`) o se registran
  ellas mismas desde la portada.
- En su ficha se mantienen el responsable legal (1) y los tutores laborales (N), y se ve todo su historial.
- El tutor puede **dar acceso** a una empresa importada: la aplicación genera usuario y contraseña inicial.
- Las empresas son comunes: cualquier tutor del centro puede abrir procesos con cualquiera de ellas.

### Paso 4 · Abrir un proceso (tutor FFE)

El tutor crea el proceso indicando empresa, curso, puesto, número de plazas y, si ya se han hablado, las condiciones
(fechas, horas, jornada y tutor laboral). El proceso nace en estado **Iniciado**.

### Paso 5 · Candidatos

Desde la ficha del proceso, el tutor marca a los alumnos del curso que se presentan, viendo junto a cada nombre las
horas que le quedan pendientes. La empresa también puede proponer alumnado registrado del curso desde su panel; esas
candidaturas quedan marcadas como propuestas por la empresa. Un alumno puede estar en varios procesos a la vez, y
cada candidato entra como **Pendiente**.

Cuando la empresa empieza a valorar candidaturas, el tutor pasa el proceso a **Abierto**. La empresa ve entonces, en
su panel, la lista de candidatos y sus currículums.

### Paso 6 · Resultados

La empresa comunica su decisión al tutor (por teléfono, entrevista o email; queda registrado como seguimiento) y el
tutor anota el resultado de cada candidato: **Seleccionado**, **No seleccionado** o **Retirado**. Al seleccionar
puede ajustar las condiciones de ese alumno si difieren de las del proceso.

### Paso 7 · Cerrar

El tutor pasa el proceso a **Cerrado**, y la aplicación guarda la fecha de cierre. A partir de ahí, cada alumno ve
en su panel su resultado definitivo y, si ha sido elegido, sus condiciones de prácticas. Si la empresa se cae, el
proceso se marca como **Cancelado**.

---

## 5. Casos de uso implementados

### Administrador

| # | Caso de uso | Detalle |
|---|---|---|
| A1 | Dar de alta un centro | Código de 8 cifras, validado |
| A2 | Crear cursos | Con promoción, tutor y código de autorregistro |
| A3 | Abrir o cerrar el autorregistro de un curso | Casilla en el curso |
| A4 | Dar de alta tutores FFE | Crea la cuenta con contraseña inicial obligatoria de cambiar |
| A5 | Restablecer la contraseña de un tutor, alumno o empresa | Acción del listado; la nueva se muestra una vez y queda registrado quién la restableció |
| A6 | Consultar y corregir cualquier dato | Alumnado, empresas, procesos, participaciones, seguimientos |
| A7 | Consultar la traza de accesos a los currículums | Solo lectura, no se puede editar ni borrar |

### Tutor FFE

| # | Caso de uso | Detalle |
|---|---|---|
| T1 | Ver su panel | Cifras del curso, tareas pendientes, sus cursos y el movimiento del centro |
| T2 | Importar alumnado por CSV | Con informe de filas rechazadas y credenciales descargables |
| T3 | Dar de alta un alumno a mano | Muestra la contraseña inicial una sola vez |
| T4 | Consultar el alumnado de un curso | Con su CV, procesos y situación |
| T5 | Ver la ficha de un alumno | CV, comentarios, procesos, accesos al CV |
| T6 | Restablecer la contraseña de un alumno suyo o de una empresa | Desde el listado del curso, la ficha del alumno o la ficha de la empresa |
| T6b | Comentar el currículum de un alumno | El alumno lo ve; las empresas no |
| T7 | Crear, importar y editar empresas | Comunes a todo el centro |
| T8 | Mantener responsable legal y tutores laborales | Con validación de DNI |
| T9 | Dar acceso a la aplicación a una empresa | Genera usuario y contraseña inicial |
| T10 | Registrar actuaciones con una empresa | Fecha, hora, medio y observaciones |
| T11 | Abrir un proceso de selección | Empresa + curso + puesto + plazas + condiciones |
| T12 | Añadir candidatos al proceso | Solo alumnado del curso del proceso |
| T13 | Registrar el resultado de cada candidato | Con condiciones propias si hace falta |
| T14 | Cambiar el estado del proceso | Iniciado → Abierto → Cerrado, o Cancelado |
| T15 | Consultar todos los procesos del centro | Filtros por estado, curso, tutor y texto |
| T16 | Resolver solicitudes de contacto de empresas | Aceptar o rechazar |
| T17 | Descargar informes | Seis listados, en Excel y en PDF |

### Alumno

| # | Caso de uso | Detalle |
|---|---|---|
| E1 | Registrarse con el código de su curso | Solo en ese curso y si está abierto |
| E2 | Cambiar su contraseña | Obligatorio en el primer acceso; después, desde «Contraseña» o su panel |
| E2b | Recuperar el acceso si la olvida | Su tutor FFE le genera una nueva |
| E3 | Consultar su situación | Seleccionado (con empresa, tutor laboral, fechas, horas y jornada) o sin plaza |
| E4 | Ver sus procesos | En marcha y cerrados, con su resultado en cada uno |
| E5 | Ver quién es su tutor FFE | Nombre, email y teléfono |
| E6 | Actualizar su email y teléfono | El DNI, nombre y curso no los edita |
| E7 | Subir o sustituir su CV | PDF de hasta 5 MB, validado |
| E8 | Leer los comentarios de su tutor sobre el CV | En su panel |
| E9 | Descargar todos sus datos | JSON, incluida la traza de accesos a su CV |
| E10 | Borrar su currículum | Deja de estar disponible para las empresas |

### Empresa

| # | Caso de uso | Detalle |
|---|---|---|
| M1 | Registrarse desde la portada | Con responsable legal y aceptación de la información de privacidad |
| M2 | Mantener sus datos y sus tutores laborales | Desde su panel |
| M3 | Consultar sus procesos | En marcha y cerrados, con el tutor FFE de contacto |
| M4 | Ver los candidatos de un proceso | Nombre, curso, currículum, horas pendientes y disponibilidad |
| M5 | Proponer alumnado registrado del curso | Solo en sus procesos y mientras estén abiertos |
| M5b | Solicitar el contacto de un alumno | Va al tutor del curso, que decide |
| M6 | Ver el contacto de quien ha seleccionado | Automático al ser seleccionado |

---

## 6. Reglas que la aplicación impide saltarse

Están en los modelos, así que se aplican tanto en la aplicación como en el panel de administración:

1. Un candidato tiene que ser del curso del proceso.
2. Un alumno no puede aparecer dos veces en el mismo proceso.
3. No se pueden seleccionar más alumnos que plazas tiene el proceso.
3b. No se comprometen más horas de las que le quedan pendientes al alumno.
4. Un alumno solo puede estar seleccionado en una empresa; si se intenta una segunda, la aplicación dice dónde está
   ya colocado.
5. Un proceso con alumnado seleccionado no se cierra sin fecha de inicio y horas.
6. El tutor laboral de un proceso tiene que ser de la empresa del proceso.
7. El autorregistro solo funciona con un código válido y con el autorregistro del curso abierto.
8. DNI/NIE, CIF y código de centro se validan con su dígito o letra de control.
9. Un tutor solo abre y modifica procesos de sus cursos, aunque vea todos los del centro.
10. No se borra un tutor laboral con alumnado asignado.

---

## 7. Quién ve qué

| Dato | Administrador | Tutor del curso | Otro tutor del centro | Empresa | El propio alumno |
|---|---|---|---|---|---|
| Datos de contacto del alumno | Sí | Sí | Sí | Solo si lo selecciona o si el tutor lo autoriza | Sí |
| Currículum | Sí | Sí | Sí (queda registrado) | Si participa en su proceso (queda registrado) | Sí |
| Comentarios sobre el CV | Sí | Sí (los escribe) | Los lee | No | Sí |
| Procesos del centro | Sí | Sí | Sí | Solo los suyos | Solo los suyos |
| Modificar un proceso | Sí | Sí | No | No | No |
| Informes del centro | Sí | Sí | Sí | No | No |
| Traza de accesos al CV | Sí | Sí | Sí | No | Sí (en su descarga de datos) |

---

## 8. Informes

Desde «Informes», cada listado se descarga en Excel (con filtros y anchos de columna ya puestos) o en PDF (apaisado,
con el nombre del centro y la fecha de generación). Todos se limitan al centro del tutor que los descarga.

| Informe | Para qué sirve |
|---|---|
| Procesos | Estado de la campaña: empresa, curso, tutor, plazas y condiciones |
| Alumnado por proceso | Una fila por alumno y proceso, con resultado y condiciones |
| Alumnado | Contacto, curso, tutor, CV y situación de prácticas |
| Empresas | Datos fiscales, contacto, tutores laborales y actividad con el centro |
| Tutores FFE | Cursos, alumnado y procesos de cada uno |
| Seguimientos | Histórico de contactos con empresas |

---

## 9. Protección de datos

El marco aplicable es el RGPD y la LOPDGDD (Ley Orgánica 3/2018); no existe una «LOPD de 2026». Lo resuelto:

- Información de privacidad pública en `/privacidad/`, enlazada desde el pie y desde los dos formularios de alta,
  con casilla de confirmación obligatoria cuya fecha se guarda.
- Minimización: las empresas ven nombre, curso y CV; el contacto solo tras seleccionar o con autorización.
- Trazabilidad: cada descarga de un CV queda registrada y el registro no se puede editar.
- Derechos: descarga de los propios datos en JSON y borrado del CV desde el panel del alumno.
- Conservación limitada: `python manage.py purgar_datos --ejecutar` anonimiza al alumnado de cursos terminados hace
  más años de los configurados, borra sus CV, comentarios, solicitudes y trazas, y conserva las participaciones sin
  datos identificativos para las estadísticas.
- Seguridad: contraseñas con hash y cambio obligatorio de la inicial, permisos por rol, CV fuera de las carpetas
  públicas con nombre aleatorio, HTTPS con HSTS y cabeceras de seguridad al desactivar `DEBUG`.

La plantilla del registro de actividades de tratamiento (art. 30 RGPD) está en
`docs/registro-actividades-tratamiento.md`.

---

## 10. Una campaña típica de un curso

| Cuándo | Quién | Qué hace |
|---|---|---|
| Septiembre | Administrador | Crea los cursos del año y asigna tutores |
| Septiembre | Tutor | Importa el alumnado y reparte credenciales, o abre el autorregistro |
| Septiembre–octubre | Alumnado | Sube el CV; el tutor lo revisa y comenta |
| Octubre–noviembre | Tutor | Llama a empresas, registra cada actuación y abre procesos |
| Noviembre–diciembre | Empresa | Revisa candidatos y entrevista |
| Diciembre | Tutor | Registra resultados, fija condiciones y cierra procesos |
| Enero | Tutor | Descarga los informes para jefatura y para el convenio |
| Marzo (año +N) | Administrador | Ejecuta la purga de datos de promociones antiguas |
