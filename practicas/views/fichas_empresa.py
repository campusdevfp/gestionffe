"""Gestión de la ficha de empresa, compartida por profesorado y por la propia empresa."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from cuentas.decoradores import rol_requerido
from cuentas.models import Rol

from ..forms import EmpresaForm, ResponsableLegalForm, TutorLaboralForm
from ..models import Empresa, ResponsableLegal, TutorLaboral

GESTORES = (Rol.TUTOR, Rol.EMPRESA)


def empresa_gestionable(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    if request.user.es_empresa and getattr(request.user, "empresa", None) != empresa:
        raise PermissionDenied
    return empresa


def volver(request, empresa):
    if request.user.es_empresa:
        return redirect("empresa:panel")
    return redirect("tutor:empresa", empresa.pk)


@rol_requerido(*GESTORES)
def editar_empresa(request, empresa_id):
    empresa = empresa_gestionable(request, empresa_id)
    form = EmpresaForm(request.POST or None, instance=empresa)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Datos de la empresa guardados.")
        return volver(request, empresa)
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": f"Datos de {empresa}", "boton": "Guardar datos", "empresa": empresa,
    })


@rol_requerido(*GESTORES)
def editar_responsable(request, empresa_id):
    empresa = empresa_gestionable(request, empresa_id)
    instancia = ResponsableLegal.objects.filter(empresa=empresa).first() or ResponsableLegal(empresa=empresa)
    form = ResponsableLegalForm(request.POST or None, instance=instancia)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Responsable legal guardado.")
        return volver(request, empresa)
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": f"Responsable legal de {empresa}", "boton": "Guardar responsable", "empresa": empresa,
    })


@rol_requerido(*GESTORES)
def tutor(request, empresa_id, tutor_id=None):
    empresa = empresa_gestionable(request, empresa_id)
    instancia = get_object_or_404(TutorLaboral, pk=tutor_id, empresa=empresa) if tutor_id else None
    form = TutorLaboralForm(request.POST or None, instance=instancia, empresa=empresa)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Tutor laboral guardado.")
        return volver(request, empresa)
    titulo = f"Editar tutor laboral de {empresa}" if instancia else f"Nuevo tutor laboral en {empresa}"
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": titulo, "boton": "Guardar tutor", "empresa": empresa,
    })


@require_POST
@rol_requerido(*GESTORES)
def borrar_tutor(request, empresa_id, tutor_id):
    empresa = empresa_gestionable(request, empresa_id)
    t = get_object_or_404(TutorLaboral, pk=tutor_id, empresa=empresa)
    try:
        t.delete()
        messages.success(request, f"Tutor {t.nombre} eliminado.")
    except ProtectedError:
        messages.error(request, f"{t.nombre} tutoriza a alumnado asignado. Cambia antes esas asignaciones.")
    return volver(request, empresa)
