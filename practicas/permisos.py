"""Reglas de quién puede ver qué.

Los tutores ven TODOS los procesos de su centro (esa es la idea: que todos tengan constancia),
pero solo gestionan los cursos de los que son tutores.
"""
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Alumno, Curso, Participacion, Proceso, SolicitudContacto  # noqa: F401


def curso_propio(request, curso_id):
    """Curso del que el usuario es tutor. Si no lo es, 403."""
    curso = get_object_or_404(Curso, pk=curso_id)
    if curso.tutor_id != request.user.tutor_ffe.pk:
        raise PermissionDenied
    return curso


def proceso_visible(request, proceso_id):
    """Cualquier tutor del centro puede consultar el proceso."""
    proceso = get_object_or_404(Proceso.objects.select_related("empresa", "curso", "tutor"), pk=proceso_id)
    if proceso.curso.centro_id != request.user.tutor_ffe.centro_id:
        raise PermissionDenied
    return proceso


def puede_gestionar(tutor, proceso):
    """Solo el tutor responsable o el del curso modifican el proceso."""
    return tutor.pk in {proceso.tutor_id, proceso.curso.tutor_id}


def proceso_gestionable(request, proceso_id):
    proceso = proceso_visible(request, proceso_id)
    if not puede_gestionar(request.user.tutor_ffe, proceso):
        raise PermissionDenied
    return proceso


def alumnos_visibles_para_empresa(empresa):
    """La empresa ve al alumnado de los cursos en los que tiene algún proceso.

    Necesita verlo para poder proponer candidatos; de cada alumno solo accede a su perfil
    profesional (curso, currículum, horas pendientes y disponibilidad), nunca a su contacto.
    """
    cursos = Proceso.objects.filter(empresa=empresa).values("curso")
    return Alumno.objects.filter(curso__in=cursos).select_related("curso").distinct()


def empresa_ve_contacto(empresa, alumno):
    if Participacion.objects.filter(
        proceso__empresa=empresa, alumno=alumno, resultado=Participacion.Resultado.SELECCIONADO
    ).exists():
        return True
    return SolicitudContacto.objects.filter(
        empresa=empresa, alumno=alumno, estado=SolicitudContacto.Estado.ACEPTADA
    ).exists()


def puede_descargar_cv(usuario, alumno):
    if usuario.es_admin:
        return True
    if usuario.es_alumno:
        return usuario.alumno.pk == alumno.pk
    if usuario.es_tutor and hasattr(usuario, "tutor_ffe"):
        return usuario.tutor_ffe.centro_id == alumno.curso.centro_id
    if usuario.es_empresa and hasattr(usuario, "empresa"):
        return alumnos_visibles_para_empresa(usuario.empresa).filter(pk=alumno.pk).exists()
    return False
