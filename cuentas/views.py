from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.shortcuts import redirect, render


@login_required
def cambiar_password(request):
    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        usuario.debe_cambiar_password = False
        usuario.save(update_fields=["debe_cambiar_password"])
        update_session_auth_hash(request, usuario)
        messages.success(request, "Contraseña cambiada.")
        return redirect("inicio")
    return render(request, "cuentas/cambiar_password.html", {"form": form})
