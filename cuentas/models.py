from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Rol(models.TextChoices):
    ADMIN = "ADMIN", "Coordinación"
    TUTOR = "TUTOR", "Tutor FFE"
    ALUMNO = "ALUMNO", "Alumnado"
    EMPRESA = "EMPRESA", "Empresa"


class GestorUsuarios(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra):
        extra.setdefault("rol", Rol.ADMIN)
        return super().create_superuser(username, email, password, **extra)


class Usuario(AbstractUser):
    rol = models.CharField(max_length=10, choices=Rol.choices)
    debe_cambiar_password = models.BooleanField(
        default=False,
        help_text="Si está marcado, el usuario tendrá que cambiar su contraseña al entrar.",
    )

    objects = GestorUsuarios()

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    @property
    def es_admin(self):
        return self.rol == Rol.ADMIN or self.is_superuser

    @property
    def es_tutor(self):
        return self.rol == Rol.TUTOR

    @property
    def es_alumno(self):
        return self.rol == Rol.ALUMNO

    @property
    def es_empresa(self):
        return self.rol == Rol.EMPRESA
