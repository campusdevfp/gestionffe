import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils import timezone
from django.utils.functional import cached_property

from .validadores import (normalizar_documento, validar_cif, validar_codigo_centro, validar_dni_nie,
                          validar_pdf, validar_telefono)

almacen_privado = FileSystemStorage(location=settings.ALMACEN_PRIVADO)


def ruta_cv(instancia, nombre):
    # Nombre aleatorio: no revela el DNI ni permite adivinar rutas.
    return f"cv/{uuid.uuid4().hex}.pdf"


class Jornada(models.TextChoices):
    MANANA = "MANANA", "Mañana"
    TARDE = "TARDE", "Tarde"
    PARTIDA = "PARTIDA", "Partida"
    FLEXIBLE = "FLEXIBLE", "Flexible"


class Centro(models.Model):
    codigo = models.CharField("código de centro", max_length=8, unique=True, validators=[validar_codigo_centro])
    nombre = models.CharField(max_length=160)
    localidad = models.CharField(max_length=120)
    provincia = models.CharField(max_length=120, blank=True)
    direccion = models.CharField("dirección", max_length=255, blank=True)
    telefono = models.CharField("teléfono", max_length=16, blank=True, validators=[validar_telefono])
    email = models.EmailField(blank=True)

    class Meta:
        verbose_name = "centro"
        verbose_name_plural = "centros"
        ordering = ["nombre"]

    def __str__(self):
        return f"{self.nombre} ({self.codigo})"


class TutorFFE(models.Model):
    """Profesor responsable de la FCT/FFE de uno o varios cursos."""

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tutor_ffe")
    centro = models.ForeignKey(Centro, on_delete=models.PROTECT, related_name="tutores")
    nombre = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=120)
    email = models.EmailField()
    telefono = models.CharField("teléfono", max_length=16, blank=True, validators=[validar_telefono])

    class Meta:
        verbose_name = "tutor FFE"
        verbose_name_plural = "tutores FFE"
        ordering = ["apellidos", "nombre"]

    def __str__(self):
        return f"{self.nombre} {self.apellidos}"

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"


class Curso(models.Model):
    centro = models.ForeignKey(Centro, on_delete=models.PROTECT, related_name="cursos")
    nombre = models.CharField(max_length=120, help_text="Por ejemplo: 2º DAW")
    anio_inicio = models.PositiveSmallIntegerField("año de inicio")
    anio_fin = models.PositiveSmallIntegerField("año de fin")
    tutor = models.ForeignKey(TutorFFE, on_delete=models.PROTECT, related_name="cursos", verbose_name="tutor FFE")
    codigo_matricula = models.CharField(
        "código de autorregistro", max_length=20, unique=True,
        help_text="El alumnado lo usa para registrarse en este curso. Compártelo solo con tu grupo.",
    )
    autorregistro = models.BooleanField(
        "autorregistro abierto", default=False,
        help_text="Si está desactivado, solo el tutor puede dar de alta alumnado.",
    )

    class Meta:
        ordering = ["-anio_inicio", "nombre"]
        constraints = [
            models.UniqueConstraint(fields=["centro", "nombre", "anio_inicio"], name="curso_unico_por_promocion"),
            models.CheckConstraint(condition=models.Q(anio_fin__gte=models.F("anio_inicio")), name="curso_anios_coherentes"),
        ]

    def __str__(self):
        return f"{self.nombre} {self.anio_inicio}-{self.anio_fin}"

    def clean(self):
        if self.anio_inicio and self.anio_fin and self.anio_fin < self.anio_inicio:
            raise ValidationError({"anio_fin": "El año de fin no puede ser anterior al de inicio."})
        if self.tutor_id and self.centro_id and self.tutor.centro_id != self.centro_id:
            raise ValidationError({"tutor": "El tutor pertenece a otro centro."})

    def save(self, *args, **kwargs):
        self.codigo_matricula = (self.codigo_matricula or "").strip().upper()
        super().save(*args, **kwargs)


class Alumno(models.Model):
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="alumno")
    dni = models.CharField("DNI/NIE", max_length=9, unique=True, validators=[validar_dni_nie])
    nombre = models.CharField(max_length=80)
    apellidos = models.CharField(max_length=120)
    email = models.EmailField()
    telefono = models.CharField("teléfono", max_length=16, blank=True, validators=[validar_telefono])
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="alumnos")
    horas_requeridas = models.PositiveSmallIntegerField(
        "horas de FFE que debe realizar", default=370,
        help_text="Varía según el ciclo y la situación del alumno.",
    )
    horas_exentas = models.PositiveSmallIntegerField(
        "horas exentas o convalidadas", default=0,
        help_text="Por experiencia laboral, exención parcial u horas ya realizadas.",
    )
    jornada_preferida = models.CharField("jornada que puede hacer", max_length=10, choices=Jornada.choices, blank=True)
    disponibilidad = models.CharField(
        max_length=200, blank=True,
        help_text="Por ejemplo: tardes a partir de las 15:30; no puedo los viernes.",
    )
    cv = models.FileField("currículum", storage=almacen_privado, upload_to=ruta_cv, blank=True, validators=[validar_pdf])
    cv_actualizado = models.DateTimeField(null=True, blank=True)
    alta = models.DateTimeField(auto_now_add=True)
    informado = models.DateTimeField(
        "información de protección de datos aceptada", null=True, blank=True,
        help_text="Fecha en que se le informó del tratamiento de sus datos.",
    )
    anonimizado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["apellidos", "nombre"]

    def __str__(self):
        return f"{self.apellidos}, {self.nombre}"

    def save(self, *args, **kwargs):
        self.dni = normalizar_documento(self.dni)
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellidos}"

    @property
    def tutor(self):
        return self.curso.tutor

    @property
    def horas_comprometidas(self):
        """Horas ya cubiertas por los procesos en los que ha sido seleccionado."""
        return sum(p.condicion_horas or 0 for p in self.participaciones.filter(
            resultado=Participacion.Resultado.SELECCIONADO).select_related("proceso"))

    @property
    def horas_pendientes(self):
        """Lo que le queda por cubrir. Es el dato que mira una empresa antes de ofrecerle plaza."""
        return max(self.horas_requeridas - self.horas_exentas - self.horas_comprometidas, 0)

    @property
    def jornada_preferida_display(self):
        return dict(Jornada.choices).get(self.jornada_preferida, "")

    def anonimizar(self):
        """Suprime los datos identificativos conservando las estadísticas del curso (art. 17 RGPD)."""
        from django.utils.crypto import get_random_string
        if self.cv:
            self.cv.delete(save=False)
        self.solicitudes.all().delete()
        self.comentarios_cv.all().delete()
        self.accesos_cv.all().delete()
        self.nombre, self.apellidos = "Alumno", "anonimizado"
        self.email, self.telefono = "", ""
        self.dni = "ANON" + get_random_string(5).upper()
        self.anonimizado = timezone.now()
        self.save()
        usuario = self.usuario
        usuario.is_active = False
        usuario.username = f"anon-{self.pk}-{get_random_string(6)}"
        usuario.first_name = usuario.last_name = usuario.email = ""
        usuario.set_unusable_password()
        usuario.save()

    @cached_property
    def practicas(self):
        """Participación en la que ha sido seleccionado, si la hay."""
        return self.participaciones.filter(resultado=Participacion.Resultado.SELECCIONADO).select_related(
            "proceso__empresa"
        ).first()


class Empresa(models.Model):
    """Las empresas son comunes a todos los cursos y centros."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="empresa"
    )
    cif = models.CharField("CIF/NIF", max_length=9, unique=True, validators=[validar_cif])
    nombre = models.CharField(max_length=160)
    direccion = models.CharField("dirección", max_length=255)
    web = models.URLField(blank=True)
    persona_contacto = models.CharField("persona de contacto", max_length=160)
    email = models.EmailField()
    telefono = models.CharField("teléfono", max_length=16, validators=[validar_telefono])
    creada = models.DateTimeField(auto_now_add=True)
    informada = models.DateTimeField("información de protección de datos aceptada", null=True, blank=True)

    class Meta:
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.cif = normalizar_documento(self.cif)
        super().save(*args, **kwargs)


class ResponsableLegal(models.Model):
    empresa = models.OneToOneField(Empresa, on_delete=models.CASCADE, related_name="responsable_legal")
    nombre = models.CharField("nombre completo", max_length=160)
    dni = models.CharField("DNI/NIE", max_length=9, validators=[validar_dni_nie])

    class Meta:
        verbose_name = "responsable legal"
        verbose_name_plural = "responsables legales"

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.dni = normalizar_documento(self.dni)
        super().save(*args, **kwargs)


class TutorLaboral(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="tutores")
    nombre = models.CharField("nombre completo", max_length=160)
    dni = models.CharField("DNI/NIE", max_length=9, validators=[validar_dni_nie])
    telefono = models.CharField("teléfono", max_length=16, validators=[validar_telefono])
    email = models.EmailField(blank=True)

    class Meta:
        verbose_name = "tutor laboral"
        verbose_name_plural = "tutores laborales"
        ordering = ["nombre"]
        constraints = [models.UniqueConstraint(fields=["empresa", "dni"], name="tutor_unico_por_empresa")]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.dni = normalizar_documento(self.dni)
        super().save(*args, **kwargs)


class Proceso(models.Model):
    """Proceso de selección entre una empresa y el alumnado de un curso.

    Lo lleva el tutor del curso, pero es visible para todos los tutores del centro.
    """

    class Estado(models.TextChoices):
        INICIADO = "INICIADO", "Iniciado"      # contacto hecho, condiciones sin cerrar
        ABIERTO = "ABIERTO", "Abierto"         # la empresa ya valora candidaturas
        CERRADO = "CERRADO", "Cerrado"         # resuelto, con o sin seleccionados
        CANCELADO = "CANCELADO", "Cancelado"

    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="procesos")
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="procesos")
    tutor = models.ForeignKey(TutorFFE, on_delete=models.PROTECT, related_name="procesos",
                              verbose_name="tutor responsable")
    puesto = models.CharField(max_length=160, help_text="Por ejemplo: desarrollo backend")
    plazas = models.PositiveSmallIntegerField(default=1)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.INICIADO)
    descripcion = models.TextField("descripción", blank=True)
    tutor_laboral = models.ForeignKey(TutorLaboral, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name="procesos", verbose_name="tutor laboral")
    fecha_inicio = models.DateField("inicio de las prácticas", null=True, blank=True)
    fecha_fin = models.DateField("fin de las prácticas", null=True, blank=True)
    horas = models.PositiveSmallIntegerField("horas estipuladas", null=True, blank=True)
    jornada = models.CharField(max_length=10, choices=Jornada.choices, blank=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    cerrado = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado"]
        verbose_name = "proceso"
        verbose_name_plural = "procesos"

    def __str__(self):
        return f"{self.empresa} · {self.puesto} ({self.curso})"

    def clean(self):
        if self.curso_id and self.tutor_id and self.tutor.centro_id != self.curso.centro_id:
            raise ValidationError({"tutor": "El tutor pertenece a otro centro."})
        if self.tutor_laboral_id and self.empresa_id and self.tutor_laboral.empresa_id != self.empresa_id:
            raise ValidationError({"tutor_laboral": "El tutor laboral no pertenece a esta empresa."})
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin es anterior a la de inicio."})
        if self.estado == self.Estado.CERRADO and self.pk and self.seleccionados and not (self.fecha_inicio and self.horas):
            raise ValidationError("Para cerrar un proceso con alumnado seleccionado indica al menos la fecha de inicio y las horas.")

    def save(self, *args, **kwargs):
        if self.estado == self.Estado.CERRADO and self.cerrado is None:
            self.cerrado = timezone.now()
        if self.estado != self.Estado.CERRADO:
            self.cerrado = None
        super().save(*args, **kwargs)

    @property
    def seleccionados(self):
        return self.participaciones.filter(resultado=Participacion.Resultado.SELECCIONADO).count()

    @property
    def abierto(self):
        return self.estado in (self.Estado.INICIADO, self.Estado.ABIERTO)


class Participacion(models.Model):
    """Un alumno dentro de un proceso. Un alumno puede estar en varios a la vez."""

    class Resultado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        SELECCIONADO = "SELECCIONADO", "Seleccionado"
        DESCARTADO = "DESCARTADO", "No seleccionado"
        RETIRADO = "RETIRADO", "Retirado"

    class Origen(models.TextChoices):
        TUTOR = "TUTOR", "Propuesto por el tutor"
        EMPRESA = "EMPRESA", "Propuesto por la empresa"

    proceso = models.ForeignKey(Proceso, on_delete=models.CASCADE, related_name="participaciones")
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name="participaciones")
    origen = models.CharField(max_length=8, choices=Origen.choices, default=Origen.TUTOR)
    resultado = models.CharField(max_length=12, choices=Resultado.choices, default=Resultado.PENDIENTE)
    observaciones = models.TextField(blank=True)
    fecha_alta = models.DateTimeField(auto_now_add=True)
    fecha_respuesta = models.DateTimeField(null=True, blank=True)
    # Condiciones propias; si se dejan en blanco valen las del proceso.
    fecha_inicio = models.DateField("inicio de las prácticas", null=True, blank=True)
    fecha_fin = models.DateField("fin de las prácticas", null=True, blank=True)
    horas = models.PositiveSmallIntegerField("horas estipuladas", null=True, blank=True)
    jornada = models.CharField(max_length=10, choices=Jornada.choices, blank=True)

    class Meta:
        verbose_name = "participación"
        verbose_name_plural = "participaciones"
        ordering = ["alumno__apellidos", "alumno__nombre"]
        constraints = [models.UniqueConstraint(fields=["proceso", "alumno"], name="alumno_una_vez_por_proceso")]

    def __str__(self):
        return f"{self.alumno} en {self.proceso.empresa}"

    def clean(self):
        if self.alumno_id and self.proceso_id and self.alumno.curso_id != self.proceso.curso_id:
            raise ValidationError({"alumno": "El alumno no pertenece al curso de este proceso."})
        if self.resultado == self.Resultado.SELECCIONADO and self.proceso_id:
            otros = self.proceso.participaciones.filter(resultado=self.Resultado.SELECCIONADO).exclude(pk=self.pk).count()
            if otros >= self.proceso.plazas:
                raise ValidationError(f"El proceso solo tiene {self.proceso.plazas} plaza(s) y ya están cubiertas.")
            if self.alumno_id:
                en_otro = Participacion.objects.filter(
                    alumno_id=self.alumno_id, resultado=self.Resultado.SELECCIONADO
                ).exclude(pk=self.pk).exclude(proceso_id=self.proceso_id).select_related("proceso__empresa").first()
                if en_otro:
                    raise ValidationError(f"{self.alumno.nombre_completo} ya está seleccionado en {en_otro.proceso.empresa}.")
                horas = self.horas or self.proceso.horas
                if horas:
                    otras = sum(p.condicion_horas or 0 for p in Participacion.objects.filter(
                        alumno_id=self.alumno_id, resultado=self.Resultado.SELECCIONADO
                    ).exclude(pk=self.pk).select_related("proceso"))
                    disponibles = self.alumno.horas_requeridas - self.alumno.horas_exentas - otras
                    if horas > disponibles:
                        raise ValidationError(
                            f"{self.alumno.nombre_completo} solo tiene {max(disponibles, 0)} horas pendientes y este "
                            f"proceso son {horas}. Ajusta las horas de esta participación."
                        )
        if self.fecha_inicio and self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha de fin es anterior a la de inicio."})

    def save(self, *args, **kwargs):
        if self.resultado != self.Resultado.PENDIENTE and self.fecha_respuesta is None:
            self.fecha_respuesta = timezone.now()
        if self.resultado == self.Resultado.PENDIENTE:
            self.fecha_respuesta = None
        super().save(*args, **kwargs)

    # Condiciones efectivas: las propias o, en su defecto, las del proceso.
    @property
    def condicion_inicio(self):
        return self.fecha_inicio or self.proceso.fecha_inicio

    @property
    def condicion_fin(self):
        return self.fecha_fin or self.proceso.fecha_fin

    @property
    def condicion_horas(self):
        return self.horas or self.proceso.horas

    @property
    def condicion_jornada(self):
        valor = self.jornada or self.proceso.jornada
        return dict(Jornada.choices).get(valor, "")


class ComentarioCV(models.Model):
    """Comentario del tutor sobre el currículum de un alumno.

    El alumno lo ve (derecho de acceso del RGPD y, sobre todo, para que le sirva de algo);
    las empresas no acceden nunca a estos comentarios.
    """

    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name="comentarios_cv")
    tutor = models.ForeignKey(TutorFFE, on_delete=models.SET_NULL, null=True, related_name="comentarios_cv")
    texto = models.TextField("comentario")
    fecha = models.DateTimeField(auto_now_add=True)
    version_cv = models.CharField(max_length=64, blank=True, help_text="CV sobre el que se comentó.")

    class Meta:
        verbose_name = "comentario sobre el CV"
        verbose_name_plural = "comentarios sobre el CV"
        ordering = ["-fecha"]

    def __str__(self):
        return f"Comentario sobre el CV de {self.alumno}"


class AccesoCV(models.Model):
    """Traza de quién descarga cada currículum (art. 5.1.f RGPD: integridad y confidencialidad)."""

    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name="accesos_cv")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    rol = models.CharField(max_length=10)
    descripcion = models.CharField(max_length=160, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "acceso a un CV"
        verbose_name_plural = "accesos a los CV"
        ordering = ["-fecha"]

    def __str__(self):
        return f"{self.descripcion} descargó el CV de {self.alumno}"


class Seguimiento(models.Model):
    """Actuación de un tutor con una empresa; puede ir ligada a un proceso concreto."""

    class Medio(models.TextChoices):
        TELEFONO = "TELEFONO", "Teléfono"
        EMAIL = "EMAIL", "Email"
        VISITA = "VISITA", "Visita"
        ENTREVISTA = "ENTREVISTA", "Entrevista con alumnado"
        OTRO = "OTRO", "Otro"

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="seguimientos")
    proceso = models.ForeignKey(Proceso, on_delete=models.CASCADE, null=True, blank=True, related_name="seguimientos")
    tutor = models.ForeignKey(TutorFFE, on_delete=models.SET_NULL, null=True, related_name="seguimientos")
    fecha_hora = models.DateTimeField("fecha y hora")
    medio = models.CharField(max_length=12, choices=Medio.choices, default=Medio.TELEFONO)
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ["-fecha_hora"]
        verbose_name = "seguimiento"
        verbose_name_plural = "seguimientos"

    def __str__(self):
        return f"{self.empresa} · {self.fecha_hora:%d/%m/%Y %H:%M}"

    def clean(self):
        if self.proceso_id and self.empresa_id and self.proceso.empresa_id != self.empresa_id:
            raise ValidationError({"proceso": "Ese proceso es de otra empresa."})


class SolicitudContacto(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        ACEPTADA = "ACEPTADA", "Aceptada"
        RECHAZADA = "RECHAZADA", "Rechazada"

    empresa = models.ForeignKey(Empresa, on_delete=models.CASCADE, related_name="solicitudes")
    alumno = models.ForeignKey(Alumno, on_delete=models.CASCADE, related_name="solicitudes")
    motivo = models.TextField(blank=True)
    estado = models.CharField(max_length=10, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha = models.DateTimeField(auto_now_add=True)
    resuelta_por = models.ForeignKey(TutorFFE, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_resolucion = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "solicitud de contacto"
        verbose_name_plural = "solicitudes de contacto"
        ordering = ["-fecha"]
        constraints = [models.UniqueConstraint(fields=["empresa", "alumno"], name="una_solicitud_por_alumno")]

    def __str__(self):
        return f"{self.empresa} → {self.alumno} ({self.get_estado_display()})"
