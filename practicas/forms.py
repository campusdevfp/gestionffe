from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.utils import timezone

from cuentas.models import Rol

from .models import (Alumno, ComentarioCV, Curso, Empresa, Participacion, Proceso, ResponsableLegal, Seguimiento,
                     SolicitudContacto, TutorLaboral)
from .validadores import normalizar_documento, validar_dni_nie


class SubidaCSVForm(forms.Form):
    fichero = forms.FileField(label="Fichero CSV", widget=forms.ClearableFileInput(attrs={"accept": ".csv,text/csv"}))

    def clean_fichero(self):
        f = self.cleaned_data["fichero"]
        if f.size > 2 * 1024 * 1024:
            raise forms.ValidationError("El CSV no puede superar 2 MB.")
        return f


class ImportarAlumnadoForm(SubidaCSVForm):
    curso = forms.ModelChoiceField(queryset=Curso.objects.none(), label="Curso")

    def __init__(self, *args, cursos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["curso"].queryset = cursos
        self.fields["curso"].empty_label = "Elige un curso"
        self.order_fields(["curso", "fichero"])


class DocumentoMixin:
    """Normaliza el DNI/CIF antes de validarlo (quita espacios, guiones, pasa a mayúsculas)."""

    campos_documento = ()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.core.validators import MaxLengthValidator
        for campo in self.campos_documento:
            f = self.fields[campo]
            # Se admite "12345678-Z" o "B 1234567 4": la longitud se comprueba tras normalizar.
            f.max_length = f.widget.attrs["maxlength"] = 15
            f.validators = [v for v in f.validators if not isinstance(v, MaxLengthValidator)]

    def _post_clean(self):
        for campo in self.campos_documento:
            if campo in self.cleaned_data:
                self.cleaned_data[campo] = normalizar_documento(self.cleaned_data[campo])
                setattr(self.instance, campo, self.cleaned_data[campo])
        super()._post_clean()


class EmpresaForm(DocumentoMixin, forms.ModelForm):
    campos_documento = ("cif",)

    class Meta:
        model = Empresa
        fields = ["nombre", "cif", "direccion", "web", "persona_contacto", "email", "telefono"]


class ResponsableLegalForm(DocumentoMixin, forms.ModelForm):
    campos_documento = ("dni",)

    class Meta:
        model = ResponsableLegal
        fields = ["nombre", "dni"]


class TutorLaboralForm(DocumentoMixin, forms.ModelForm):
    campos_documento = ("dni",)

    class Meta:
        model = TutorLaboral
        fields = ["nombre", "dni", "telefono", "email"]

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        if empresa is not None:
            self.instance.empresa = empresa


class AltaAlumnoForm(DocumentoMixin, forms.ModelForm):
    """Alta manual de un alumno por parte del tutor."""

    campos_documento = ("dni",)

    class Meta:
        model = Alumno
        fields = ["dni", "nombre", "apellidos", "email", "telefono", "curso", "horas_requeridas"]

    def __init__(self, *args, cursos=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cursos is not None:
            self.fields["curso"].queryset = cursos
            self.fields["curso"].empty_label = "Elige un curso"


class PerfilAlumnoForm(forms.ModelForm):
    class Meta:
        model = Alumno
        fields = ["email", "telefono", "jornada_preferida", "disponibilidad"]
        labels = {"jornada_preferida": "Jornada que puedes hacer"}
        help_texts = {"disponibilidad": "Las empresas lo ven al valorar tu candidatura. Por ejemplo: "
                                        "tardes a partir de las 15:30; no puedo los viernes."}


class HorasAlumnoForm(forms.ModelForm):
    """El cupo de horas es un dato académico: lo fija el tutor."""

    class Meta:
        model = Alumno
        fields = ["horas_requeridas", "horas_exentas"]


class CVForm(forms.ModelForm):
    class Meta:
        model = Alumno
        fields = ["cv"]
        widgets = {"cv": forms.FileInput(attrs={"accept": "application/pdf"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cv"].required = True


class AutorregistroAlumnoForm(forms.Form):
    """Alta del propio alumno usando el código del curso que le da su tutor."""

    codigo_matricula = forms.CharField(label="Código del curso", max_length=20)
    dni = forms.CharField(label="DNI/NIE", max_length=15, validators=[validar_dni_nie])
    nombre = forms.CharField(max_length=80)
    apellidos = forms.CharField(max_length=120)
    email = forms.EmailField()
    telefono = forms.CharField(label="Teléfono", max_length=16, required=False)
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput)
    informado = forms.BooleanField(
        label="He leído la información sobre el tratamiento de mis datos personales",
        error_messages={"required": "Debes confirmar que has leído la información de protección de datos."},
    )

    def clean_codigo_matricula(self):
        codigo = self.cleaned_data["codigo_matricula"].strip().upper()
        curso = Curso.objects.filter(codigo_matricula=codigo).first()
        if curso is None:
            raise forms.ValidationError("Ese código no corresponde a ningún curso. Pídeselo a tu tutor.")
        if not curso.autorregistro:
            raise forms.ValidationError("El autorregistro de ese curso está cerrado. Habla con tu tutor.")
        self.curso = curso
        return codigo

    def clean_dni(self):
        dni = normalizar_documento(self.cleaned_data["dni"])
        if Alumno.objects.filter(dni=dni).exists() or get_user_model().objects.filter(username=dni).exists():
            raise forms.ValidationError("Ya hay un alumno registrado con ese DNI. Entra con tu usuario o avisa a tu tutor.")
        return dni

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return datos

    def save(self):
        usuario = get_user_model().objects.create_user(
            username=self.cleaned_data["dni"], password=self.cleaned_data["password1"],
            email=self.cleaned_data["email"], first_name=self.cleaned_data["nombre"],
            last_name=self.cleaned_data["apellidos"], rol=Rol.ALUMNO,
        )
        from django.utils import timezone as tz
        return Alumno.objects.create(
            usuario=usuario, dni=self.cleaned_data["dni"], nombre=self.cleaned_data["nombre"],
            apellidos=self.cleaned_data["apellidos"], email=self.cleaned_data["email"],
            telefono=self.cleaned_data["telefono"], curso=self.curso, informado=tz.now(),
        )


class ProcesoForm(forms.ModelForm):
    class Meta:
        model = Proceso
        fields = ["empresa", "curso", "puesto", "plazas", "descripcion", "tutor_laboral",
                  "fecha_inicio", "fecha_fin", "horas", "jornada"]
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }

    def __init__(self, *args, cursos=None, **kwargs):
        super().__init__(*args, **kwargs)
        if cursos is not None:
            self.fields["curso"].queryset = cursos
        self.fields["curso"].empty_label = "Elige un curso"
        self.fields["empresa"].empty_label = "Elige una empresa"
        if self.instance.pk:
            self.fields["tutor_laboral"].queryset = self.instance.empresa.tutores.all()
            self.fields["empresa"].disabled = True
            self.fields["curso"].disabled = True
        else:
            self.fields["tutor_laboral"].queryset = TutorLaboral.objects.none()
            self.fields["tutor_laboral"].help_text = "Podrás elegirlo al editar el proceso, una vez creado."


class ParticipacionForm(forms.ModelForm):
    class Meta:
        model = Participacion
        fields = ["resultado", "observaciones", "fecha_inicio", "fecha_fin", "horas", "jornada"]
        widgets = {
            "observaciones": forms.Textarea(attrs={"rows": 2}),
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        }
        help_texts = {"fecha_inicio": "En blanco: se usan las condiciones del proceso."}


class AnadirCandidatosForm(forms.Form):
    alumnos = forms.ModelMultipleChoiceField(
        queryset=Alumno.objects.none(), widget=forms.CheckboxSelectMultiple, label="Alumnado del curso",
    )

    def __init__(self, *args, proceso=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["alumnos"].queryset = Alumno.objects.filter(curso=proceso.curso).exclude(
            participaciones__proceso=proceso
        )
        self.fields["alumnos"].label_from_instance = lambda a: (
            f"{a.apellidos}, {a.nombre} · {a.horas_pendientes} h pendientes"
        )


class ComentarioCVForm(forms.ModelForm):
    class Meta:
        model = ComentarioCV
        fields = ["texto"]
        labels = {"texto": "Comentario sobre el currículum"}
        widgets = {"texto": forms.Textarea(attrs={
            "rows": 3, "placeholder": "Por ejemplo: añade los proyectos del módulo de DWES y ajusta el CV a una página.",
        })}


class SeguimientoForm(forms.ModelForm):
    class Meta:
        model = Seguimiento
        fields = ["fecha_hora", "medio", "observaciones"]
        widgets = {
            "fecha_hora": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "observaciones": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk:
            self.initial["fecha_hora"] = timezone.localtime().strftime("%Y-%m-%dT%H:%M")

    def clean_fecha_hora(self):
        fecha = self.cleaned_data["fecha_hora"]
        if fecha > timezone.now() + timezone.timedelta(minutes=5):
            raise forms.ValidationError("El seguimiento no puede tener fecha futura.")
        return fecha


class SolicitudContactoForm(forms.ModelForm):
    class Meta:
        model = SolicitudContacto
        fields = ["motivo"]
        widgets = {"motivo": forms.Textarea(attrs={"rows": 3, "placeholder": "Por ejemplo: queremos concertar una entrevista."})}


class RegistroEmpresaForm(EmpresaForm):
    """Alta pública de una empresa: datos, responsable legal y acceso."""

    responsable_nombre = forms.CharField(label="Nombre del responsable legal", max_length=160)
    responsable_dni = forms.CharField(label="DNI/NIE del responsable legal", max_length=15)
    usuario = forms.CharField(label="Nombre de usuario", max_length=150)
    password1 = forms.CharField(label="Contraseña", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput)
    informada = forms.BooleanField(
        label="He leído la información sobre el tratamiento de datos y me comprometo a usar los datos del alumnado solo para el proceso de selección",
        error_messages={"required": "Debes confirmar que has leído la información de protección de datos."},
    )

    def clean_usuario(self):
        usuario = self.cleaned_data["usuario"]
        if get_user_model().objects.filter(username__iexact=usuario).exists():
            raise forms.ValidationError("Ese nombre de usuario ya existe.")
        return usuario

    def clean_cif(self):
        cif = normalizar_documento(self.cleaned_data["cif"])
        if Empresa.objects.filter(cif=cif).exists():
            raise forms.ValidationError(
                "Esta empresa ya está dada de alta. Pide el acceso al tutor FFE con el que trabajáis."
            )
        return cif

    def clean(self):
        datos = super().clean()
        p1, p2 = datos.get("password1"), datos.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Las contraseñas no coinciden.")
        elif p1:
            try:
                password_validation.validate_password(p1)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        responsable = ResponsableLegal(nombre=datos.get("responsable_nombre", ""),
                                       dni=normalizar_documento(datos.get("responsable_dni", "")))
        try:
            responsable.full_clean(exclude=["empresa"])
        except forms.ValidationError as e:
            for campo, errores in e.message_dict.items():
                self.add_error("responsable_dni" if campo == "dni" else "responsable_nombre", errores)
        return datos

    def save(self, commit=True):
        Usuario = get_user_model()
        usuario = Usuario.objects.create_user(
            username=self.cleaned_data["usuario"], password=self.cleaned_data["password1"],
            email=self.cleaned_data["email"], rol=Rol.EMPRESA,
        )
        from django.utils import timezone as tz
        empresa = super().save(commit=False)
        empresa.usuario = usuario
        empresa.informada = tz.now()
        empresa.save()
        ResponsableLegal.objects.create(
            empresa=empresa, nombre=self.cleaned_data["responsable_nombre"], dni=self.cleaned_data["responsable_dni"],
        )
        return empresa
