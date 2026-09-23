from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "cuentas"

urlpatterns = [
    path("entrar/", auth_views.LoginView.as_view(template_name="cuentas/login.html", redirect_authenticated_user=True), name="login"),
    path("salir/", auth_views.LogoutView.as_view(), name="logout"),
    path("contrasena/", views.cambiar_password, name="cambiar_password"),
]
