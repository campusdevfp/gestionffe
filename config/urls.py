from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as servir_estatico
from django.urls import include, path, re_path
from django.views.decorators.cache import cache_control

admin.site.site_header = "Prácticas en empresa · Administración"
admin.site.site_title = "Prácticas en empresa"
admin.site.index_title = "Centros, cursos y tutores FFE"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("cuenta/", include("cuentas.urls")),
    path("", include("practicas.urls")),
]

# Con DEBUG=0 Django deja de servir los ficheros estáticos y la aplicación se vería sin estilos.
# Esta ruta los sirve igualmente, para que funcione tal cual en el ordenador del centro.
# En un despliegue con Nginx o Apache, el servidor web interceptará /static/ antes que Django.
if not settings.DEBUG:
    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", cache_control(max_age=3600)(servir_estatico), {"insecure": True}),
    ]
