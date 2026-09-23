from django.shortcuts import redirect
from django.urls import reverse


class CambioPasswordObligatorioMiddleware:
    """Obliga a cambiar la contraseña inicial antes de usar la aplicación."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        usuario = getattr(request, "user", None)
        if usuario and usuario.is_authenticated and usuario.debe_cambiar_password:
            permitidas = {reverse("cuentas:cambiar_password"), reverse("cuentas:logout")}
            if request.path not in permitidas and not request.path.startswith("/static/"):
                return redirect("cuentas:cambiar_password")
        return self.get_response(request)
