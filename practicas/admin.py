from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.db import transaction

from cuentas.auditoria import registrar_restablecimiento
from cuentas.models import Rol

from .models import (AccesoCV, Alumno, Centro, ComentarioCV, Curso, Empresa, Participacion, Proceso,
                     ResponsableLegal, Seguimiento, SolicitudContacto, TutorFFE, TutorLaboral)


@admin.action(description="Restablecer la contraseña (se muestra una sola vez)")
def restablecer_contrasena(modeladmin, request, queryset):
    from practicas.importacion import generar_password
    for objeto in queryset:
        usuario = objeto.usuario if hasattr(objeto, "usuario") else objeto
        if usuario is None:
            modeladmin.message_user(request, f"{objeto} no tiene usuario asociado.", level=messages.WARNING)
            continue
        password = generar_password(12)
        usuario.set_password(password)
        usuario.debe_cambiar_password = True
        usuario.save()
        registrar_restablecimiento(request.user, usuario, f"desde {modeladmin.model._meta.verbose_name}")
        modeladmin.message_user(
            request, f"{usuario.username}: contraseña nueva «{password}». Anótala ahora; no volverá a mostrarse.",
            level=messages.SUCCESS,
        )


@admin.register(Centro)
class CentroAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "localidad", "n_cursos", "n_tutores")
    search_fields = ("nombre", "codigo", "localidad")

    @admin.display(description="Cursos")
    def n_cursos(self, obj):
        return obj.cursos.count()

    @admin.display(description="Tutores")
    def n_tutores(self, obj):
        return obj.tutores.count()


class TutorAdminForm(forms.ModelForm):
    username = forms.CharField(label="Usuario de acceso", max_length=150, required=False)
    password = forms.CharField(label="Contraseña inicial", required=False, widget=forms.PasswordInput(render_value=False),
                               help_text="Se le pedirá cambiarla en su primer acceso.")

    class Meta:
        model = TutorFFE
        fields = ["centro", "nombre", "apellidos", "email", "telefono"]

    def clean(self):
        datos = super().clean()
        if not self.instance.pk:
            if not datos.get("username") or not datos.get("password"):
                raise forms.ValidationError("Indica usuario y contraseña inicial para el nuevo tutor.")
            if get_user_model().objects.filter(username__iexact=datos["username"]).exists():
                self.add_error("username", "Ese usuario ya existe.")
        return datos


@admin.register(TutorFFE)
class TutorFFEAdmin(admin.ModelAdmin):
    form = TutorAdminForm
    list_display = ("apellidos", "nombre", "centro", "email", "lista_cursos", "usuario")
    list_filter = ("centro",)
    search_fields = ("nombre", "apellidos", "email", "usuario__username")
    actions = [restablecer_contrasena]

    def get_fields(self, request, obj=None):
        base = ["centro", "nombre", "apellidos", "email", "telefono"]
        return base if obj else ["username", "password"] + base

    @admin.display(description="Cursos que tutoriza")
    def lista_cursos(self, obj):
        return ", ".join(str(c) for c in obj.cursos.all()) or "—"

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not change:
            obj.usuario = get_user_model().objects.create_user(
                username=form.cleaned_data["username"], password=form.cleaned_data["password"], email=obj.email,
                first_name=obj.nombre, last_name=obj.apellidos, rol=Rol.TUTOR, debe_cambiar_password=True,
            )
        super().save_model(request, obj, form, change)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "centro", "anio_inicio", "anio_fin", "tutor", "codigo_matricula", "autorregistro", "n_alumnos")
    list_filter = ("centro", "autorregistro", "tutor")
    search_fields = ("nombre", "codigo_matricula")
    fieldsets = (
        (None, {"fields": ("centro", "nombre", ("anio_inicio", "anio_fin"), "tutor")}),
        ("Autorregistro del alumnado", {
            "fields": ("codigo_matricula", "autorregistro"),
            "description": "El alumnado puede darse de alta solo con este código, y solo en este curso.",
        }),
    )

    @admin.display(description="Alumnos")
    def n_alumnos(self, obj):
        return obj.alumnos.count()


@admin.register(Alumno)
class AlumnoAdmin(admin.ModelAdmin):
    list_display = ("apellidos", "nombre", "dni", "curso", "email", "tiene_cv")
    list_filter = ("curso__centro", "curso")
    search_fields = ("nombre", "apellidos", "dni", "email")
    readonly_fields = ("usuario", "cv", "cv_actualizado", "alta")
    actions = [restablecer_contrasena]

    @admin.display(boolean=True, description="CV")
    def tiene_cv(self, obj):
        return bool(obj.cv)

    def has_add_permission(self, request):
        return False  # El alumnado se da de alta desde la aplicación (CSV, alta manual o autorregistro).


class ResponsableInline(admin.StackedInline):
    model = ResponsableLegal
    can_delete = False


class TutorLaboralInline(admin.TabularInline):
    model = TutorLaboral
    extra = 0


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cif", "persona_contacto", "telefono", "email", "usuario")
    search_fields = ("nombre", "cif", "persona_contacto")
    inlines = [ResponsableInline, TutorLaboralInline]
    readonly_fields = ("creada",)
    actions = [restablecer_contrasena]


class ParticipacionInline(admin.TabularInline):
    model = Participacion
    extra = 0
    autocomplete_fields = ("alumno",)


@admin.register(Proceso)
class ProcesoAdmin(admin.ModelAdmin):
    list_display = ("empresa", "puesto", "curso", "tutor", "estado", "plazas", "n_seleccionados", "creado")
    list_filter = ("estado", "curso__centro", "curso", "tutor")
    search_fields = ("empresa__nombre", "puesto")
    inlines = [ParticipacionInline]
    readonly_fields = ("creado", "actualizado", "cerrado")

    @admin.display(description="Seleccionados")
    def n_seleccionados(self, obj):
        return obj.seleccionados


@admin.register(Participacion)
class ParticipacionAdmin(admin.ModelAdmin):
    list_display = ("alumno", "proceso", "resultado", "fecha_respuesta")
    list_filter = ("resultado", "proceso__curso")
    search_fields = ("alumno__nombre", "alumno__apellidos", "proceso__empresa__nombre")


@admin.register(Seguimiento)
class SeguimientoAdmin(admin.ModelAdmin):
    list_display = ("empresa", "fecha_hora", "medio", "tutor", "proceso")
    list_filter = ("medio", "tutor")
    date_hierarchy = "fecha_hora"


@admin.register(SolicitudContacto)
class SolicitudAdmin(admin.ModelAdmin):
    list_display = ("empresa", "alumno", "estado", "fecha", "resuelta_por")
    list_filter = ("estado",)


@admin.register(ComentarioCV)
class ComentarioCVAdmin(admin.ModelAdmin):
    list_display = ("alumno", "tutor", "fecha")
    list_filter = ("tutor",)
    search_fields = ("alumno__nombre", "alumno__apellidos")


@admin.register(AccesoCV)
class AccesoCVAdmin(admin.ModelAdmin):
    """Traza de accesos: solo consulta, no se edita."""

    list_display = ("fecha", "alumno", "descripcion", "rol")
    list_filter = ("rol",)
    date_hierarchy = "fecha"
    search_fields = ("alumno__nombre", "alumno__apellidos", "descripcion")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
