"""Traza de las acciones sensibles sobre las cuentas.

Se apoya en el registro de acciones de Django (admin.LogEntry), que ya guarda quién hizo qué y cuándo,
y se consulta en /admin/admin/logentry/. Restablecer una contraseña permite entrar como esa persona,
así que tiene que quedar constancia de quién lo hizo.
"""
from django.contrib.admin.models import CHANGE, LogEntry


def registrar_restablecimiento(actor, usuario, detalle=""):
    """Anota que `actor` ha restablecido la contraseña de `usuario`."""
    mensaje = "Contraseña restablecida" + (f" · {detalle}" if detalle else "")
    LogEntry.objects.log_actions(
        user_id=actor.pk,
        queryset=[usuario],
        action_flag=CHANGE,
        change_message=mensaje,
        single_object=True,
    )
