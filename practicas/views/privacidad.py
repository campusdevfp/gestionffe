"""Páginas y acciones de protección de datos (RGPD + LOPDGDD)."""
import json

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from cuentas.decoradores import rol_requerido
from cuentas.models import Rol


def informacion(request):
    """Información sobre el tratamiento de datos, accesible sin iniciar sesión."""
    return render(request, "practicas/privacidad.html")


@rol_requerido(Rol.ALUMNO)
def mis_datos(request):
    """Derecho de acceso y portabilidad (arts. 15 y 20 RGPD): todo en un JSON."""
    a = request.user.alumno
    datos = {
        "generado": timezone.localtime().isoformat(),
        "identificacion": {"dni": a.dni, "nombre": a.nombre, "apellidos": a.apellidos,
                           "email": a.email, "telefono": a.telefono, "alta": a.alta.isoformat()},
        "formacion": {"centro": str(a.curso.centro), "curso": str(a.curso), "tutor": a.curso.tutor.nombre_completo},
        "curriculum": {"subido": bool(a.cv), "actualizado": a.cv_actualizado.isoformat() if a.cv_actualizado else None},
        "comentarios_de_mi_tutor": [
            {"fecha": c.fecha.isoformat(), "tutor": str(c.tutor), "texto": c.texto} for c in a.comentarios_cv.all()
        ],
        "procesos": [{
            "empresa": p.proceso.empresa.nombre, "puesto": p.proceso.puesto,
            "estado_del_proceso": p.proceso.get_estado_display(), "mi_resultado": p.get_resultado_display(),
            "fecha_respuesta": p.fecha_respuesta.isoformat() if p.fecha_respuesta else None,
            "inicio": str(p.condicion_inicio or ""), "fin": str(p.condicion_fin or ""),
            "horas": p.condicion_horas, "jornada": p.condicion_jornada,
        } for p in a.participaciones.select_related("proceso__empresa")],
        "solicitudes_de_contacto_de_empresas": [
            {"empresa": s.empresa.nombre, "fecha": s.fecha.isoformat(), "estado": s.get_estado_display()}
            for s in a.solicitudes.all()
        ],
        "accesos_a_mi_cv": [
            {"fecha": x.fecha.isoformat(), "quien": x.descripcion, "rol": x.rol} for x in a.accesos_cv.all()
        ],
    }
    respuesta = HttpResponse(json.dumps(datos, ensure_ascii=False, indent=2), content_type="application/json")
    respuesta["Content-Disposition"] = f'attachment; filename="mis-datos-{a.dni}.json"'
    return respuesta


@require_POST
@rol_requerido(Rol.ALUMNO)
def borrar_cv(request):
    """Supresión del currículum a petición del alumno (art. 17 RGPD)."""
    a = request.user.alumno
    if a.cv:
        a.cv.delete(save=False)
        a.cv, a.cv_actualizado = "", None
        a.save(update_fields=["cv", "cv_actualizado"])
        messages.success(request, "Currículum eliminado. Puedes subir otro cuando quieras.")
    return redirect("alumno:panel")
