from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone

from cuentas.decoradores import rol_requerido
from cuentas.models import Rol

from ..forms import AutorregistroAlumnoForm, CVForm, PerfilAlumnoForm

alumno_requerido = rol_requerido(Rol.ALUMNO)


def autorregistro(request):
    """Alta del propio alumno con el código que le da su tutor."""
    if request.user.is_authenticated:
        return redirect("inicio")
    form = AutorregistroAlumnoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        from django.contrib.auth import login
        alumno = form.save()
        login(request, alumno.usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, f"Te has registrado en {alumno.curso}. Sube tu currículum para empezar.")
        return redirect("alumno:panel")
    return render(request, "practicas/alumno/registro.html", {"form": form})


@alumno_requerido
def panel(request):
    alumno = request.user.alumno
    participaciones = alumno.participaciones.select_related("proceso__empresa", "proceso__tutor_laboral")
    return render(request, "practicas/alumno/panel.html", {
        "alumno": alumno, "tutor": alumno.curso.tutor, "practicas": alumno.practicas,
        "comentarios": alumno.comentarios_cv.select_related("tutor"),
        "abiertos": [p for p in participaciones if p.proceso.abierto],
        "cerrados": [p for p in participaciones if not p.proceso.abierto],
        "form_cv": CVForm(instance=alumno),
    })


@alumno_requerido
def perfil(request):
    alumno = request.user.alumno
    form = PerfilAlumnoForm(request.POST or None, instance=alumno)
    if request.method == "POST" and form.is_valid():
        form.save()
        request.user.email = alumno.email
        request.user.save(update_fields=["email"])
        messages.success(request, "Datos de contacto actualizados.")
        return redirect("alumno:panel")
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": "Mis datos de contacto", "boton": "Guardar datos",
    })


@alumno_requerido
def subir_cv(request):
    alumno = request.user.alumno
    anterior = alumno.cv.name if alumno.cv else None
    form = CVForm(request.POST or None, request.FILES or None, instance=alumno)
    if request.method == "POST" and form.is_valid():
        alumno = form.save(commit=False)
        alumno.cv_actualizado = timezone.now()
        alumno.save()
        if anterior and anterior != alumno.cv.name:
            alumno.cv.storage.delete(anterior)
        messages.success(request, "Currículum actualizado.")
        return redirect("alumno:panel")
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": "Subir currículum (PDF, máx. 5 MB)", "boton": "Subir currículum", "multipart": True,
    })
