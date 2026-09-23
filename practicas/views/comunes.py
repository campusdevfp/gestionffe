from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from ..models import AccesoCV, Alumno
from ..permisos import puede_descargar_cv


def _describir(usuario):
    if usuario.es_empresa and hasattr(usuario, "empresa"):
        return str(usuario.empresa)
    if usuario.es_tutor and hasattr(usuario, "tutor_ffe"):
        return usuario.tutor_ffe.nombre_completo
    return usuario.get_full_name() or usuario.username


def salud(request):
    """Comprobación de vida para el contenedor: responde si la base de datos contesta."""
    from django.db import connection
    from django.http import JsonResponse
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return JsonResponse({"estado": "ok"})


def portada(request):
    """Pantalla de entrada para quien no ha iniciado sesión."""
    if request.user.is_authenticated:
        return inicio(request)
    return render(request, "practicas/portada.html")


@login_required
def inicio(request):
    u = request.user
    if u.es_admin:
        return redirect("admin:index")
    if u.es_tutor and hasattr(u, "tutor_ffe"):
        return redirect("tutor:panel")
    if u.es_alumno and hasattr(u, "alumno"):
        return redirect("alumno:panel")
    if u.es_empresa and hasattr(u, "empresa"):
        return redirect("empresa:panel")
    raise PermissionDenied("Tu usuario no tiene un perfil asociado. Contacta con el centro.")


@login_required
def descargar_cv(request, alumno_id):
    alumno = get_object_or_404(Alumno, pk=alumno_id)
    if not puede_descargar_cv(request.user, alumno):
        raise PermissionDenied
    if not alumno.cv:
        raise Http404("Este alumno no ha subido su currículum.")
    if request.user.pk != alumno.usuario_id:  # el propio alumno no se registra a sí mismo
        AccesoCV.objects.create(alumno=alumno, usuario=request.user, rol=request.user.rol,
                                descripcion=_describir(request.user))
    nombre = f"CV_{alumno.apellidos}_{alumno.nombre}.pdf".replace(" ", "_")
    return FileResponse(alumno.cv.open("rb"), content_type="application/pdf", filename=nombre)
