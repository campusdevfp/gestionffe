from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ("username", "first_name", "last_name", "rol", "is_active", "last_login")
    list_filter = ("rol", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("Rol en la aplicación", {"fields": ("rol", "debe_cambiar_password")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Rol en la aplicación", {"fields": ("rol",)}),)


@admin.register(LogEntry)
class RegistroAccionesAdmin(admin.ModelAdmin):
    """Quién ha hecho qué: altas, cambios y restablecimientos de contraseña. Solo lectura."""

    list_display = ("action_time", "user", "content_type", "object_repr", "change_message")
    list_filter = ("action_flag", "content_type", "user")
    search_fields = ("object_repr", "change_message")
    date_hierarchy = "action_time"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
