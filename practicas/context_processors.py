def navegacion(request):
    """Enlaces del menú según el rol del usuario."""
    u = getattr(request, "user", None)
    if not u or not u.is_authenticated or u.debe_cambiar_password:
        return {"menu": []}
    menu = []
    if u.es_admin:
        menu = [("Administración", "admin:index")]
    elif u.es_tutor:
        menu = [("Inicio", "tutor:panel"), ("Procesos", "tutor:procesos"), ("Empresas", "tutor:empresas"),
                ("Solicitudes", "tutor:solicitudes"), ("Informes", "tutor:informes")]
    elif u.es_alumno:
        menu = [("Mis prácticas", "alumno:panel"), ("Mis datos", "alumno:perfil")]
    elif u.es_empresa:
        menu = [("Mi empresa", "empresa:panel"), ("Alumnado", "empresa:alumnos")]
    return {"menu": menu}


def responsable(request):
    """Datos del responsable del tratamiento para las páginas de privacidad."""
    from django.conf import settings
    return {"responsable": settings.RESPONSABLE}
