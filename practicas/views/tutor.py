from django.contrib import messages
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from cuentas.auditoria import registrar_restablecimiento
from cuentas.decoradores import rol_requerido
from cuentas.models import Rol

from ..forms import (AltaAlumnoForm, AnadirCandidatosForm, ComentarioCVForm, EmpresaForm, HorasAlumnoForm,
                     ImportarAlumnadoForm, ParticipacionForm, ProcesoForm, SeguimientoForm, SubidaCSVForm)
from ..importacion import (COLUMNAS_ALUMNADO, COLUMNAS_EMPRESAS, ErrorCSV, generar_password, importar_alumnado,
                           importar_empresas)
from ..models import Alumno, ComentarioCV, Empresa, Participacion, Proceso, Seguimiento, SolicitudContacto
from ..permisos import curso_propio, proceso_gestionable, proceso_visible, puede_gestionar

tutor_requerido = rol_requerido(Rol.TUTOR)


def _tutor(request):
    return request.user.tutor_ffe


def _procesos_del_centro(tutor):
    return Proceso.objects.filter(curso__centro=tutor.centro).select_related("empresa", "curso", "tutor")


@tutor_requerido
def panel(request):
    """Panel del tutor: primero lo que requiere su atención, después sus cursos y el pulso del centro."""
    tutor = _tutor(request)
    cursos = list(tutor.cursos.annotate(
        n_alumnos=Count("alumnos", distinct=True),
        n_procesos=Count("procesos", filter=Q(procesos__estado__in=["INICIADO", "ABIERTO"]), distinct=True),
        sin_cv=Count("alumnos", filter=Q(alumnos__cv=""), distinct=True),
    ))
    mis_alumnos = Alumno.objects.filter(curso__tutor=tutor)
    colocados = Participacion.objects.filter(alumno__curso__tutor=tutor,
                                             resultado=Participacion.Resultado.SELECCIONADO)
    for c in cursos:
        c.n_colocados = colocados.filter(alumno__curso=c).count()

    mis_procesos = _procesos_del_centro(tutor).filter(Q(tutor=tutor) | Q(curso__tutor=tutor))
    en_marcha = mis_procesos.filter(estado__in=["INICIADO", "ABIERTO"])
    pendientes = SolicitudContacto.objects.filter(
        alumno__curso__tutor=tutor, estado=SolicitudContacto.Estado.PENDIENTE
    ).count()

    # Tareas: solo aparecen las que de verdad tocan.
    tareas = []
    if pendientes:
        tareas.append({"texto": f"{pendientes} solicitud(es) de contacto de empresas sin responder",
                       "enlace": reverse("tutor:solicitudes"), "accion": "Revisar", "urgente": True})
    sin_candidatos = en_marcha.annotate(n=Count("participaciones")).filter(n=0)
    for p in sin_candidatos[:3]:
        tareas.append({"texto": f"{p.empresa} · {p.puesto}: proceso sin candidatos",
                       "enlace": reverse("tutor:proceso", args=[p.pk]), "accion": "Añadir", "urgente": True})
    parados = en_marcha.filter(actualizado__lt=timezone.now() - timezone.timedelta(days=21))
    for p in parados[:3]:
        tareas.append({"texto": f"{p.empresa} · {p.puesto}: sin movimiento desde el {p.actualizado:%d/%m}",
                       "enlace": reverse("tutor:proceso", args=[p.pk]), "accion": "Ver", "urgente": False})
    for c in cursos:
        if c.sin_cv:
            tareas.append({"texto": f"{c.nombre}: {c.sin_cv} alumno(s) sin currículum subido",
                           "enlace": reverse("tutor:alumnos", args=[c.pk]), "accion": "Ver curso", "urgente": False})

    return render(request, "practicas/tutor/panel.html", {
        "cursos": cursos, "tareas": tareas, "centro": tutor.centro,
        "total_alumnos": mis_alumnos.count(), "total_colocados": colocados.count(),
        "total_en_marcha": en_marcha.count(), "total_sin_plaza": mis_alumnos.exclude(
            participaciones__resultado=Participacion.Resultado.SELECCIONADO).count(),
        "actividad": _procesos_del_centro(tutor).order_by("-actualizado")[:6],
        "ultimos_seguimientos": Seguimiento.objects.filter(
            empresa__procesos__curso__centro=tutor.centro).distinct().select_related("empresa", "tutor")[:5],
    })


# ---------- Alumnado ----------

@tutor_requerido
def alumnos(request, curso_id):
    curso = curso_propio(request, curso_id)
    lista = curso.alumnos.prefetch_related("participaciones__proceso__empresa")
    return render(request, "practicas/tutor/alumnos.html", {"curso": curso, "alumnos": lista})


@tutor_requerido
def alumno(request, alumno_id):
    """Ficha del alumno: CV, comentarios del tutor y procesos en los que participa."""
    alumno = get_object_or_404(Alumno.objects.select_related("curso__tutor"), pk=alumno_id,
                               curso__centro=_tutor(request).centro)
    gestiono = alumno.curso.tutor_id == _tutor(request).pk
    return render(request, "practicas/tutor/alumno.html", {
        "alumno": alumno, "gestiono": gestiono,
        "form_horas": HorasAlumnoForm(instance=alumno) if gestiono else None,
        "participaciones": alumno.participaciones.select_related("proceso__empresa"),
        "comentarios": alumno.comentarios_cv.select_related("tutor"),
        "form_comentario": ComentarioCVForm() if gestiono else None,
        "accesos": alumno.accesos_cv.all()[:10],
    })


@require_POST
@tutor_requerido
def comentar_cv(request, alumno_id):
    alumno = get_object_or_404(Alumno, pk=alumno_id, curso__tutor=_tutor(request))
    form = ComentarioCVForm(request.POST)
    if form.is_valid():
        comentario = form.save(commit=False)
        comentario.alumno, comentario.tutor = alumno, _tutor(request)
        comentario.version_cv = alumno.cv.name if alumno.cv else ""
        comentario.save()
        messages.success(request, "Comentario guardado. El alumno lo verá en su panel.")
    else:
        messages.error(request, "El comentario no puede estar vacío.")
    return redirect("tutor:alumno", alumno.pk)


@require_POST
@tutor_requerido
def guardar_horas(request, alumno_id):
    alumno = get_object_or_404(Alumno, pk=alumno_id, curso__tutor=_tutor(request))
    form = HorasAlumnoForm(request.POST, instance=alumno)
    if form.is_valid():
        form.save()
        messages.success(request, f"Cupo de horas actualizado: {alumno.horas_pendientes} h pendientes.")
    else:
        messages.error(request, "Revisa las horas indicadas.")
    return redirect("tutor:alumno", alumno.pk)


@require_POST
@tutor_requerido
def restablecer_password_alumno(request, alumno_id):
    """El tutor genera una contraseña nueva para un alumno suyo que la ha olvidado."""
    alumno = get_object_or_404(Alumno, pk=alumno_id, curso__tutor=_tutor(request))
    password = generar_password()
    usuario = alumno.usuario
    usuario.set_password(password)
    usuario.debe_cambiar_password = True
    usuario.is_active = True
    usuario.save()
    registrar_restablecimiento(request.user, usuario, f"alumno de {alumno.curso}")
    return render(request, "practicas/tutor/acceso_creado.html", {
        "titulo": f"Contraseña nueva para {alumno.nombre_completo}", "usuario": alumno.dni, "password": password,
        "volver": reverse("tutor:alumno", args=[alumno.pk]),
    })


@require_POST
@tutor_requerido
def restablecer_password_empresa(request, empresa_id):
    """Igual para una empresa que ha perdido el acceso."""
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    if not empresa.usuario:
        messages.error(request, "Esta empresa todavía no tiene acceso. Créalo primero.")
        return redirect("tutor:empresa", empresa.pk)
    password = generar_password(12)
    usuario = empresa.usuario
    usuario.set_password(password)
    usuario.debe_cambiar_password = True
    usuario.save()
    registrar_restablecimiento(request.user, usuario, f"empresa {empresa}")
    return render(request, "practicas/tutor/acceso_creado.html", {
        "titulo": f"Contraseña nueva para {empresa}", "usuario": usuario.username, "password": password,
        "volver": reverse("tutor:empresa", args=[empresa.pk]),
    })


@require_POST
@tutor_requerido
def borrar_comentario(request, alumno_id, comentario_id):
    comentario = get_object_or_404(ComentarioCV, pk=comentario_id, alumno_id=alumno_id, tutor=_tutor(request))
    comentario.delete()
    messages.success(request, "Comentario eliminado.")
    return redirect("tutor:alumno", alumno_id)


@tutor_requerido
def alta_alumno(request):
    cursos = _tutor(request).cursos.all()
    form = AltaAlumnoForm(request.POST or None, cursos=cursos, initial={"curso": request.GET.get("curso")})
    if request.method == "POST" and form.is_valid():
        password = generar_password()
        with transaction.atomic():
            alumno = form.save(commit=False)
            alumno.usuario = get_user_model().objects.create_user(
                username=alumno.dni, password=password, email=alumno.email, first_name=alumno.nombre,
                last_name=alumno.apellidos, rol=Rol.ALUMNO, debe_cambiar_password=True,
            )
            alumno.save()
        return render(request, "practicas/tutor/acceso_creado.html", {
            "titulo": f"Alumno {alumno.nombre_completo} dado de alta", "usuario": alumno.dni, "password": password,
            "volver": reverse("tutor:alumnos", args=[alumno.curso_id]),
        })
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": "Alta de alumno", "boton": "Dar de alta",
    })


@tutor_requerido
def importar_alumnos(request):
    cursos = _tutor(request).cursos.all()
    form = ImportarAlumnadoForm(request.POST or None, request.FILES or None, cursos=cursos,
                                initial={"curso": request.GET.get("curso")})
    resultado = None
    if request.method == "POST" and form.is_valid():
        try:
            resultado = importar_alumnado(form.cleaned_data["fichero"], form.cleaned_data["curso"])
            messages.success(request, f"{len(resultado.creados)} alumnos importados.")
        except ErrorCSV as e:
            form.add_error("fichero", str(e))
    return render(request, "practicas/tutor/importar.html", {
        "form": form, "resultado": resultado, "titulo": "Importar alumnado",
        "columnas": ";".join(COLUMNAS_ALUMNADO),
        "ejemplo": "12345678Z;Lucía;García Pérez;lucia.garcia@correo.es;600111222",
    })


# ---------- Empresas ----------

@tutor_requerido
def empresas(request):
    q = request.GET.get("q", "").strip()
    tutor = _tutor(request)
    lista = Empresa.objects.annotate(
        n_procesos=Count("procesos", filter=Q(procesos__curso__centro=tutor.centro), distinct=True),
        n_abiertos=Count("procesos", filter=Q(procesos__curso__centro=tutor.centro,
                                              procesos__estado__in=["INICIADO", "ABIERTO"]), distinct=True),
        n_tutores=Count("tutores", distinct=True),
    ).prefetch_related("seguimientos")
    if q:
        lista = lista.filter(Q(nombre__icontains=q) | Q(cif__icontains=q) | Q(persona_contacto__icontains=q))
    return render(request, "practicas/tutor/empresas.html", {"empresas": lista, "q": q})


@tutor_requerido
def nueva_empresa(request):
    form = EmpresaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        empresa = form.save()
        messages.success(request, f"Empresa {empresa} creada. Añade su responsable legal y sus tutores laborales.")
        return redirect("tutor:empresa", empresa.pk)
    return render(request, "practicas/formulario.html", {"form": form, "titulo": "Nueva empresa", "boton": "Crear empresa"})


@tutor_requerido
def importar_empresas_csv(request):
    form = SubidaCSVForm(request.POST or None, request.FILES or None)
    resultado = None
    if request.method == "POST" and form.is_valid():
        try:
            resultado = importar_empresas(form.cleaned_data["fichero"])
            messages.success(request, f"{len(resultado.creados)} empresas importadas.")
        except ErrorCSV as e:
            form.add_error("fichero", str(e))
    return render(request, "practicas/tutor/importar.html", {
        "form": form, "resultado": resultado, "titulo": "Importar empresas",
        "columnas": ";".join(COLUMNAS_EMPRESAS),
        "ejemplo": "B12345674;Soluciones Web SL;C/ Mayor 1, Guadalajara;https://solweb.es;Ana López;rrhh@solweb.es;949000000",
    })


@tutor_requerido
def empresa(request, empresa_id):
    empresa = get_object_or_404(Empresa.objects.select_related("responsable_legal"), pk=empresa_id)
    tutor = _tutor(request)
    return render(request, "practicas/tutor/empresa.html", {
        "empresa": empresa,
        "responsable": getattr(empresa, "responsable_legal", None),
        "tutores": empresa.tutores.all(),
        "procesos": empresa.procesos.filter(curso__centro=tutor.centro).select_related("curso", "tutor"),
        "seguimientos": empresa.seguimientos.select_related("tutor", "proceso"),
        "form_seguimiento": SeguimientoForm(),
    })


@require_POST
@tutor_requerido
def registrar_seguimiento(request, empresa_id, proceso_id=None):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    proceso = proceso_visible(request, proceso_id) if proceso_id else None
    form = SeguimientoForm(request.POST)
    if form.is_valid():
        s = form.save(commit=False)
        s.empresa, s.tutor, s.proceso = empresa, _tutor(request), proceso
        s.save()
        messages.success(request, "Seguimiento registrado.")
    else:
        for errores in form.errors.values():
            messages.error(request, " ".join(errores))
    return redirect("tutor:proceso", proceso.pk) if proceso else redirect("tutor:empresa", empresa.pk)


@require_POST
@tutor_requerido
def crear_acceso_empresa(request, empresa_id):
    empresa = get_object_or_404(Empresa, pk=empresa_id)
    if empresa.usuario:
        messages.error(request, "Esta empresa ya tiene acceso.")
        return redirect("tutor:empresa", empresa.pk)
    usuario, password = f"empresa-{empresa.cif.lower()}", generar_password(12)
    with transaction.atomic():
        empresa.usuario = get_user_model().objects.create_user(
            username=usuario, password=password, email=empresa.email, rol=Rol.EMPRESA, debe_cambiar_password=True,
        )
        empresa.save(update_fields=["usuario"])
    return render(request, "practicas/tutor/acceso_creado.html", {
        "titulo": f"Acceso creado para {empresa}", "usuario": usuario, "password": password,
        "volver": reverse("tutor:empresa", args=[empresa.pk]),
    })


# ---------- Procesos ----------

@tutor_requerido
def procesos(request):
    """Registro de procesos del centro: todos los tutores ven todos."""
    tutor = _tutor(request)
    lista = _procesos_del_centro(tutor).annotate(
        n_candidatos=Count("participaciones", distinct=True),
        n_seleccionados=Count("participaciones", filter=Q(participaciones__resultado="SELECCIONADO"), distinct=True),
    )
    filtros = {"estado": request.GET.get("estado", ""), "curso": request.GET.get("curso", ""),
               "tutor": request.GET.get("tutor", ""), "q": request.GET.get("q", "").strip()}
    if filtros["estado"]:
        lista = lista.filter(estado=filtros["estado"])
    if filtros["curso"]:
        lista = lista.filter(curso_id=filtros["curso"])
    if filtros["tutor"] == "mios":
        lista = lista.filter(Q(tutor=tutor) | Q(curso__tutor=tutor))
    if filtros["q"]:
        lista = lista.filter(Q(empresa__nombre__icontains=filtros["q"]) | Q(puesto__icontains=filtros["q"]))
    return render(request, "practicas/tutor/procesos.html", {
        "procesos": lista, "filtros": filtros, "estados": Proceso.Estado.choices,
        "cursos": tutor.centro.cursos.all(), "centro": tutor.centro,
    })


@tutor_requerido
def nuevo_proceso(request):
    tutor = _tutor(request)
    cursos = tutor.cursos.all()
    form = ProcesoForm(request.POST or None, cursos=cursos,
                       initial={"curso": request.GET.get("curso"), "empresa": request.GET.get("empresa")})
    if request.method == "POST" and form.is_valid():
        proceso = form.save(commit=False)
        proceso.tutor = tutor
        proceso.save()
        messages.success(request, "Proceso creado. Añade ahora los candidatos.")
        return redirect("tutor:proceso", proceso.pk)
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": "Nuevo proceso de selección", "boton": "Crear proceso",
        "ayuda": "Solo puedes abrir procesos para los cursos de los que eres tutor. El resto de tutores podrán verlo.",
    })


@tutor_requerido
def proceso(request, proceso_id):
    proceso = proceso_visible(request, proceso_id)
    tutor = _tutor(request)
    gestiono = puede_gestionar(tutor, proceso)
    participaciones = proceso.participaciones.select_related("alumno")
    return render(request, "practicas/tutor/proceso.html", {
        "proceso": proceso, "participaciones": participaciones, "gestiono": gestiono,
        "form_candidatos": AnadirCandidatosForm(proceso=proceso) if gestiono and proceso.abierto else None,
        "form_seguimiento": SeguimientoForm() if gestiono else None,
        "seguimientos": proceso.seguimientos.select_related("tutor"),
        "estados": Proceso.Estado.choices,
    })


@tutor_requerido
def editar_proceso(request, proceso_id):
    proceso = proceso_gestionable(request, proceso_id)
    form = ProcesoForm(request.POST or None, instance=proceso, cursos=_tutor(request).cursos.all())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Proceso actualizado.")
        return redirect("tutor:proceso", proceso.pk)
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": f"Editar proceso · {proceso.empresa}", "boton": "Guardar proceso",
    })


@require_POST
@tutor_requerido
def cambiar_estado(request, proceso_id):
    proceso = proceso_gestionable(request, proceso_id)
    estado = request.POST.get("estado")
    if estado not in Proceso.Estado.values:
        messages.error(request, "Estado no válido.")
        return redirect("tutor:proceso", proceso.pk)
    anterior, proceso.estado = proceso.estado, estado
    try:
        proceso.full_clean()
        proceso.save()
        messages.success(request, f"Proceso {proceso.get_estado_display().lower()}.")
    except Exception as e:
        proceso.estado = anterior
        messages.error(request, " ".join(getattr(e, "messages", [str(e)])))
    return redirect("tutor:proceso", proceso.pk)


@require_POST
@tutor_requerido
def anadir_candidatos(request, proceso_id):
    proceso = proceso_gestionable(request, proceso_id)
    form = AnadirCandidatosForm(request.POST, proceso=proceso)
    if form.is_valid():
        for alumno in form.cleaned_data["alumnos"]:
            Participacion.objects.create(proceso=proceso, alumno=alumno)
        messages.success(request, f"{len(form.cleaned_data['alumnos'])} candidato(s) añadidos.")
    else:
        messages.error(request, "Elige al menos un alumno.")
    return redirect("tutor:proceso", proceso.pk)


@tutor_requerido
def participacion(request, proceso_id, participacion_id):
    proceso = proceso_gestionable(request, proceso_id)
    p = get_object_or_404(Participacion, pk=participacion_id, proceso=proceso)
    form = ParticipacionForm(request.POST or None, instance=p)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{p.alumno.nombre_completo}: {p.get_resultado_display().lower()}.")
        return redirect("tutor:proceso", proceso.pk)
    return render(request, "practicas/formulario.html", {
        "form": form, "titulo": f"{p.alumno.nombre_completo} en {proceso.empresa}", "boton": "Guardar resultado",
        "ayuda": "Las condiciones en blanco se heredan del proceso.",
    })


@require_POST
@tutor_requerido
def quitar_candidato(request, proceso_id, participacion_id):
    proceso = proceso_gestionable(request, proceso_id)
    p = get_object_or_404(Participacion, pk=participacion_id, proceso=proceso)
    p.delete()
    messages.success(request, f"{p.alumno.nombre_completo} ya no participa en este proceso.")
    return redirect("tutor:proceso", proceso.pk)


# ---------- Solicitudes de contacto ----------

@tutor_requerido
def solicitudes(request):
    lista = SolicitudContacto.objects.filter(alumno__curso__tutor=_tutor(request)).select_related(
        "empresa", "alumno__curso", "resuelta_por"
    )
    return render(request, "practicas/tutor/solicitudes.html", {
        "pendientes": [s for s in lista if s.estado == SolicitudContacto.Estado.PENDIENTE],
        "resueltas": [s for s in lista if s.estado != SolicitudContacto.Estado.PENDIENTE],
    })


@require_POST
@tutor_requerido
def resolver_solicitud(request, solicitud_id):
    s = get_object_or_404(SolicitudContacto, pk=solicitud_id, alumno__curso__tutor=_tutor(request),
                          estado=SolicitudContacto.Estado.PENDIENTE)
    decision = request.POST.get("decision")
    if decision not in ("aceptar", "rechazar"):
        messages.error(request, "Decisión no válida.")
        return redirect("tutor:solicitudes")
    s.estado = SolicitudContacto.Estado.ACEPTADA if decision == "aceptar" else SolicitudContacto.Estado.RECHAZADA
    s.resuelta_por, s.fecha_resolucion = _tutor(request), timezone.now()
    s.save()
    messages.success(request, f"Solicitud de {s.empresa} {s.get_estado_display().lower()}.")
    return redirect("tutor:solicitudes")
