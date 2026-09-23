"""Descarga de cualquiera de los listados en Excel o PDF."""
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.utils.text import slugify

from cuentas.decoradores import rol_requerido
from cuentas.models import Rol

from ..exportacion import a_excel, a_pdf
from ..models import Alumno, Empresa, Participacion, Proceso, Seguimiento, TutorFFE


def _informe_procesos(centro):
    cabeceras = ["Empresa", "CIF", "Curso", "Puesto", "Tutor FFE", "Estado", "Plazas", "Candidatos",
                 "Seleccionados", "Inicio", "Fin", "Horas", "Jornada", "Creado"]
    filas = []
    for p in Proceso.objects.filter(curso__centro=centro).select_related("empresa", "curso", "tutor"):
        filas.append([p.empresa.nombre, p.empresa.cif, str(p.curso), p.puesto, p.tutor.nombre_completo,
                      p.get_estado_display(), p.plazas, p.participaciones.count(), p.seleccionados,
                      p.fecha_inicio, p.fecha_fin, p.horas, p.get_jornada_display(), p.creado])
    return "Procesos", cabeceras, filas


def _informe_participaciones(centro):
    cabeceras = ["Alumno", "DNI", "Curso", "Tutor FFE", "Empresa", "Puesto", "Estado del proceso",
                 "Resultado", "Respuesta", "Inicio", "Fin", "Horas", "Jornada"]
    filas = []
    for p in Participacion.objects.filter(proceso__curso__centro=centro).select_related(
            "alumno__curso__tutor", "proceso__empresa"):
        # Las condiciones de prácticas solo aplican a quien ha sido seleccionado.
        elegido = p.resultado == Participacion.Resultado.SELECCIONADO
        filas.append([p.alumno.nombre_completo, p.alumno.dni, str(p.alumno.curso), p.alumno.curso.tutor.nombre_completo,
                      p.proceso.empresa.nombre, p.proceso.puesto, p.proceso.get_estado_display(),
                      p.get_resultado_display(), p.fecha_respuesta,
                      p.condicion_inicio if elegido else "", p.condicion_fin if elegido else "",
                      p.condicion_horas if elegido else "", p.condicion_jornada if elegido else ""])
    return "Participaciones", cabeceras, filas


def _informe_alumnos(centro):
    cabeceras = ["Apellidos, nombre", "DNI", "Email", "Teléfono", "Curso", "Tutor FFE", "CV",
                 "Procesos", "Situación", "Empresa", "Inicio", "Fin", "Horas", "Jornada"]
    filas = []
    for a in Alumno.objects.filter(curso__centro=centro).select_related("curso__tutor"):
        practicas = a.practicas
        filas.append([str(a), a.dni, a.email, a.telefono, str(a.curso), a.curso.tutor.nombre_completo,
                      "Sí" if a.cv else "No", a.participaciones.count(),
                      "Seleccionado" if practicas else "Sin plaza",
                      practicas.proceso.empresa.nombre if practicas else "",
                      practicas.condicion_inicio if practicas else "", practicas.condicion_fin if practicas else "",
                      practicas.condicion_horas if practicas else "", practicas.condicion_jornada if practicas else ""])
    return "Alumnado", cabeceras, filas


def _informe_empresas(centro):
    cabeceras = ["Empresa", "CIF", "Dirección", "Web", "Persona de contacto", "Email", "Teléfono",
                 "Responsable legal", "Tutores laborales", "Procesos en el centro", "Seleccionados"]
    filas = []
    for e in Empresa.objects.all().select_related("responsable_legal").prefetch_related("tutores"):
        procesos = e.procesos.filter(curso__centro=centro)
        filas.append([e.nombre, e.cif, e.direccion, e.web, e.persona_contacto, e.email, e.telefono,
                      getattr(getattr(e, "responsable_legal", None), "nombre", ""),
                      ", ".join(t.nombre for t in e.tutores.all()), procesos.count(),
                      sum(p.seleccionados for p in procesos)])
    return "Empresas", cabeceras, filas


def _informe_tutores(centro):
    cabeceras = ["Apellidos, nombre", "Email", "Teléfono", "Cursos", "Alumnado", "Procesos", "Abiertos"]
    filas = []
    for t in TutorFFE.objects.filter(centro=centro).prefetch_related("cursos"):
        cursos = t.cursos.all()
        filas.append([f"{t.apellidos}, {t.nombre}", t.email, t.telefono,
                      ", ".join(str(c) for c in cursos), sum(c.alumnos.count() for c in cursos),
                      t.procesos.count(), t.procesos.filter(estado__in=["INICIADO", "ABIERTO"]).count()])
    return "Tutores FFE", cabeceras, filas


def _informe_seguimientos(centro):
    cabeceras = ["Fecha y hora", "Empresa", "Proceso", "Curso", "Tutor FFE", "Medio", "Observaciones"]
    filas = []
    for s in Seguimiento.objects.filter(empresa__procesos__curso__centro=centro).distinct().select_related(
            "empresa", "proceso__curso", "tutor"):
        filas.append([s.fecha_hora, s.empresa.nombre, s.proceso.puesto if s.proceso else "",
                      str(s.proceso.curso) if s.proceso else "", s.tutor.nombre_completo if s.tutor else "",
                      s.get_medio_display(), s.observaciones])
    return "Seguimientos", cabeceras, filas


INFORMES = {
    "procesos": _informe_procesos,
    "participaciones": _informe_participaciones,
    "alumnos": _informe_alumnos,
    "empresas": _informe_empresas,
    "tutores": _informe_tutores,
    "seguimientos": _informe_seguimientos,
}

TIPOS = {"xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "pdf": "application/pdf"}


@rol_requerido(Rol.TUTOR)
def descargar(request, informe, formato):
    if informe not in INFORMES or formato not in TIPOS:
        raise Http404("Informe no disponible.")
    centro = request.user.tutor_ffe.centro
    titulo, cabeceras, filas = INFORMES[informe](centro)
    contenido = (a_excel if formato == "xlsx" else a_pdf)(titulo, cabeceras, filas, *([] if formato == "xlsx" else [str(centro)]))
    nombre = f"{slugify(titulo)}-{slugify(centro.codigo)}-{timezone.localdate():%Y%m%d}.{formato}"
    respuesta = HttpResponse(contenido, content_type=TIPOS[formato])
    respuesta["Content-Disposition"] = f'attachment; filename="{nombre}"'
    return respuesta


@rol_requerido(Rol.TUTOR)
def panel_informes(request):
    from django.shortcuts import render
    etiquetas = [
        ("procesos", "Procesos de selección", "Empresa, curso, tutor, estado, plazas y condiciones."),
        ("participaciones", "Alumnado por proceso", "Una fila por alumno y proceso, con su resultado."),
        ("alumnos", "Alumnado", "Datos de contacto, curso, tutor y situación de prácticas."),
        ("empresas", "Empresas", "Datos fiscales, contacto, tutores laborales y actividad."),
        ("tutores", "Tutores FFE", "Cursos, alumnado y procesos de cada tutor."),
        ("seguimientos", "Seguimientos", "Histórico de contactos con empresas."),
    ]
    return render(request, "practicas/tutor/informes.html", {"informes": etiquetas})
