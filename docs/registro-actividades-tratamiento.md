# Registro de actividades de tratamiento (art. 30 RGPD)

Plantilla para adjuntar al RAT del centro. Sustituye lo que está entre corchetes y consulta la ficha con el
delegado de protección de datos antes de poner la aplicación en producción.

| Apartado | Contenido |
|---|---|
| **Denominación del tratamiento** | Gestión de la formación en centros de trabajo (FFE/FCT) |
| **Responsable** | [Nombre del centro] · [CIF] · [dirección] · [email] |
| **Delegado de protección de datos** | [Email del DPD de la consejería o del centro] |
| **Finalidad** | Gestión de la asignación del alumnado a empresas para el periodo de prácticas: matrícula en el curso, currículum, procesos de selección, resultados y condiciones (fechas, horas y jornada) |
| **Base jurídica** | Alumnado: art. 6.1.e RGPD (misión de interés público en el ámbito educativo), en relación con la normativa de formación profesional. Empresas y tutores laborales: art. 6.1.b RGPD (ejecución del convenio de colaboración) |
| **Colectivos** | Alumnado del centro, profesorado tutor de FFE, personas de contacto, responsables legales y tutores laborales de las empresas colaboradoras |
| **Categorías de datos** | Identificativos (DNI/NIE, nombre, apellidos), de contacto (email, teléfono), académicos (centro, curso, tutor), currículum aportado por el alumnado, comentarios del tutor sobre el currículum, participación y resultado en procesos de selección, registro de accesos a los currículums |
| **Categorías especiales** | Ninguna |
| **Decisiones automatizadas** | Ninguna. La selección la deciden la empresa y el tutor |
| **Cesiones** | A las empresas colaboradoras, limitadas al alumnado que participa en sus procesos. Sin otras cesiones salvo obligación legal |
| **Transferencias internacionales** | No se realizan |
| **Plazo de conservación** | Duración de la relación académica y [4] años desde el fin del curso. Después, anonimización mediante `python manage.py purgar_datos --ejecutar` |
| **Encargados del tratamiento** | [Proveedor de alojamiento, si lo hay]. Formalizar contrato del art. 28 RGPD |
| **Medidas de seguridad** | Autenticación individual con cambio obligatorio de contraseña inicial; contraseñas con hash; control de acceso por rol; currículums fuera de las carpetas públicas y servidos con verificación de permisos; registro de accesos a currículums; HTTPS con HSTS; copias de seguridad cifradas |

## Antes de poner la aplicación en producción

1. Rellenar las variables `LOPD_RESPONSABLE`, `LOPD_EMAIL`, `LOPD_DPD` y `LOPD_CONSERVACION_ANIOS`, que alimentan la
   página `/privacidad/` y el pie de la aplicación.
2. Revisar el texto de `/privacidad/` con el DPD y añadir la referencia al RAT del centro.
3. Incluir este tratamiento en el RAT y comprobar si procede una evaluación de impacto (en principio no: no hay
   tratamiento a gran escala ni categorías especiales).
4. Servir siempre por HTTPS, con `DJANGO_DEBUG=0` y `DJANGO_SECRET_KEY` propia.
5. Programar la purga anual, por ejemplo con cron:
   `0 3 1 9 * cd /ruta/app && .venv/bin/python manage.py purgar_datos --ejecutar`
6. Guardar las copias de seguridad cifradas y con acceso restringido: contienen currículums.
