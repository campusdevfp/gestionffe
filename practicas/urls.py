from django.urls import include, path

from .views import alumno, comunes, empresa, exportar, fichas_empresa, privacidad, tutor

tutor_urls = ([
    path("", tutor.panel, name="panel"),
    path("cursos/<int:curso_id>/alumnos/", tutor.alumnos, name="alumnos"),
    path("alumnos/<int:alumno_id>/", tutor.alumno, name="alumno"),
    path("alumnos/<int:alumno_id>/contrasena/", tutor.restablecer_password_alumno, name="restablecer_alumno"),
    path("alumnos/<int:alumno_id>/horas/", tutor.guardar_horas, name="horas_alumno"),
    path("alumnos/<int:alumno_id>/comentario/", tutor.comentar_cv, name="comentar_cv"),
    path("alumnos/<int:alumno_id>/comentario/<int:comentario_id>/borrar/", tutor.borrar_comentario, name="borrar_comentario"),
    path("alumnos/nuevo/", tutor.alta_alumno, name="alta_alumno"),
    path("alumnos/importar/", tutor.importar_alumnos, name="importar_alumnos"),
    path("empresas/", tutor.empresas, name="empresas"),
    path("empresas/nueva/", tutor.nueva_empresa, name="nueva_empresa"),
    path("empresas/importar/", tutor.importar_empresas_csv, name="importar_empresas"),
    path("empresas/<int:empresa_id>/", tutor.empresa, name="empresa"),
    path("empresas/<int:empresa_id>/seguimiento/", tutor.registrar_seguimiento, name="seguimiento"),
    path("empresas/<int:empresa_id>/acceso/", tutor.crear_acceso_empresa, name="crear_acceso"),
    path("empresas/<int:empresa_id>/contrasena/", tutor.restablecer_password_empresa, name="restablecer_empresa"),
    path("procesos/", tutor.procesos, name="procesos"),
    path("procesos/nuevo/", tutor.nuevo_proceso, name="nuevo_proceso"),
    path("procesos/<int:proceso_id>/", tutor.proceso, name="proceso"),
    path("procesos/<int:proceso_id>/editar/", tutor.editar_proceso, name="editar_proceso"),
    path("procesos/<int:proceso_id>/estado/", tutor.cambiar_estado, name="estado_proceso"),
    path("procesos/<int:proceso_id>/candidatos/", tutor.anadir_candidatos, name="anadir_candidatos"),
    path("procesos/<int:proceso_id>/seguimiento/<int:empresa_id>/", tutor.registrar_seguimiento, name="seguimiento_proceso"),
    path("procesos/<int:proceso_id>/candidatos/<int:participacion_id>/", tutor.participacion, name="participacion"),
    path("procesos/<int:proceso_id>/candidatos/<int:participacion_id>/quitar/", tutor.quitar_candidato, name="quitar_candidato"),
    path("solicitudes/", tutor.solicitudes, name="solicitudes"),
    path("solicitudes/<int:solicitud_id>/resolver/", tutor.resolver_solicitud, name="resolver"),
    path("informes/", exportar.panel_informes, name="informes"),
    path("informes/<str:informe>.<str:formato>", exportar.descargar, name="descargar_informe"),
], "tutor")

alumno_urls = ([
    path("", alumno.panel, name="panel"),
    path("alta/", alumno.autorregistro, name="registro"),
    path("datos/", alumno.perfil, name="perfil"),
    path("cv/", alumno.subir_cv, name="cv"),
    path("cv/borrar/", privacidad.borrar_cv, name="borrar_cv"),
    path("mis-datos.json", privacidad.mis_datos, name="mis_datos"),
], "alumno")

empresa_urls = ([
    path("", empresa.panel, name="panel"),
    path("alta/", empresa.registro, name="registro"),
    path("procesos/<int:proceso_id>/", empresa.proceso, name="proceso"),
    path("procesos/<int:proceso_id>/candidatos/", empresa.candidatos_posibles, name="candidatos"),
    path("alumnado/", empresa.alumnos, name="alumnos"),
    path("alumnado/<int:alumno_id>/", empresa.alumno, name="alumno"),
], "empresa")

ficha_urls = ([
    path("<int:empresa_id>/datos/", fichas_empresa.editar_empresa, name="editar"),
    path("<int:empresa_id>/responsable/", fichas_empresa.editar_responsable, name="responsable"),
    path("<int:empresa_id>/tutores/nuevo/", fichas_empresa.tutor, name="tutor_nuevo"),
    path("<int:empresa_id>/tutores/<int:tutor_id>/", fichas_empresa.tutor, name="tutor"),
    path("<int:empresa_id>/tutores/<int:tutor_id>/borrar/", fichas_empresa.borrar_tutor, name="tutor_borrar"),
], "ficha")

urlpatterns = [
    path("", comunes.portada, name="inicio"),
    path("cv/<int:alumno_id>/", comunes.descargar_cv, name="cv"),
    path("privacidad/", privacidad.informacion, name="privacidad"),
    path("salud/", comunes.salud, name="salud"),
    path("tutor/", include(tutor_urls)),
    path("alumnado/", include(alumno_urls)),
    path("empresa/", include(empresa_urls)),
    path("fichas/", include(ficha_urls)),
]
