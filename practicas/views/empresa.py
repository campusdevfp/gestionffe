from django.contrib import messages
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render

from cuentas.decoradores import rol_requerido
from cuentas.models import Rol

from ..forms import RegistroEmpresaForm, SolicitudContactoForm
from ..models import Alumno, Participacion, Proceso, SolicitudContacto
from ..permisos import alumnos_visibles_para_empresa, empresa_ve_contacto

empresa_requerida = rol_requerido(Rol.EMPRESA)


def registro(request):
    if request.user.is_authenticated:
        return redirect("inicio")
    form = RegistroEmpresaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            empresa = form.save()
        login(request, empresa.usuario, backend="django.contrib.auth.backends.ModelBackend")
        messages.success(request, "Empresa registrada. Añade ahora a tus tutores laborales.")
        return redirect("empresa:panel")
    return render(request, "practicas/empresa/registro.html", {"form": form})


@empresa_requerida
def panel(request):
    empresa = request.user.empresa
    procesos = empresa.procesos.select_related("curso__centro", "tutor").prefetch_related("participaciones__alumno")
    return render(request, "practicas/empresa/panel.html", {
        "empresa": empresa,
        "responsable": getattr(empresa, "responsable_legal", None),
        "tutores": empresa.tutores.all(),
        "abiertos": [p for p in procesos if p.abierto],
        "cerrados": [p for p in procesos if not p.abierto],
    })


@empresa_requerida
def proceso(request, proceso_id):
    empresa = request.user.empresa
    proceso = get_object_or_404(Proceso.objects.select_related("curso__centro", "tutor"), pk=proceso_id, empresa=empresa)
    participaciones = proceso.participaciones.select_related("alumno")
    solicitudes = {s.alumno_id: s for s in empresa.solicitudes.all()}
    for p in participaciones:
        p.solicitud = solicitudes.get(p.alumno_id)
    return render(request, "practicas/empresa/proceso.html", {"proceso": proceso, "participaciones": participaciones})


@empresa_requerida
def candidatos_posibles(request, proceso_id):
    """La empresa puede proponer alumnado registrado del curso del proceso."""
    empresa = request.user.empresa
    proceso = get_object_or_404(Proceso, pk=proceso_id, empresa=empresa)
    disponibles = Alumno.objects.filter(curso=proceso.curso).exclude(participaciones__proceso=proceso)
    if request.method == "POST":
        if not proceso.abierto:
            messages.error(request, "El proceso está cerrado; habla con el tutor FFE.")
            return redirect("empresa:proceso", proceso.pk)
        elegidos = disponibles.filter(pk__in=request.POST.getlist("alumnos"))
        for alumno in elegidos:
            Participacion.objects.get_or_create(
                proceso=proceso, alumno=alumno, defaults={"origen": Participacion.Origen.EMPRESA},
            )
        if elegidos:
            messages.success(request, f"{len(elegidos)} candidato(s) añadidos. El tutor FFE lo verá en el proceso.")
        return redirect("empresa:proceso", proceso.pk)
    return render(request, "practicas/empresa/candidatos.html", {"proceso": proceso, "alumnos": disponibles})


@empresa_requerida
def alumnos(request):
    empresa = request.user.empresa
    lista = alumnos_visibles_para_empresa(empresa)
    solicitudes = {s.alumno_id: s for s in empresa.solicitudes.all()}
    for a in lista:
        a.solicitud = solicitudes.get(a.pk)
    return render(request, "practicas/empresa/alumnos.html", {"alumnos": lista})


@empresa_requerida
def alumno(request, alumno_id):
    empresa = request.user.empresa
    a = get_object_or_404(alumnos_visibles_para_empresa(empresa), pk=alumno_id)
    solicitud = SolicitudContacto.objects.filter(empresa=empresa, alumno=a).first()
    form = SolicitudContactoForm(request.POST or None)
    if request.method == "POST" and solicitud is None and form.is_valid():
        s = form.save(commit=False)
        s.empresa, s.alumno = empresa, a
        try:
            s.save()
            messages.success(request, "Solicitud enviada al tutor FFE del curso.")
        except IntegrityError:
            messages.error(request, "Ya habías solicitado contactar con este alumno.")
        return redirect("empresa:alumno", a.pk)
    return render(request, "practicas/empresa/alumno.html", {
        "alumno": a, "solicitud": solicitud, "form": form, "ve_contacto": empresa_ve_contacto(empresa, a),
        "participaciones": a.participaciones.filter(proceso__empresa=empresa).select_related("proceso"),
    })
