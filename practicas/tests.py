import io
import shutil
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from cuentas.models import Usuario
from practicas.importacion import importar_alumnado, importar_empresas
from practicas.models import (AccesoCV, Alumno, Centro, ComentarioCV, Curso, Empresa, Participacion, Proceso,
                              Seguimiento, SolicitudContacto, TutorFFE, TutorLaboral)
from practicas.validadores import validar_cif, validar_codigo_centro, validar_dni_nie

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
TMP = tempfile.mkdtemp()


class ValidadoresTests(TestCase):
    def test_dni_y_nie(self):
        validar_dni_nie("12345678Z")
        validar_dni_nie("x1234567l")
        with self.assertRaises(ValidationError):
            validar_dni_nie("12345678A")

    def test_cif(self):
        validar_cif("B12345674")
        validar_cif("A58818501")
        with self.assertRaises(ValidationError):
            validar_cif("B12345678")

    def test_codigo_centro(self):
        validar_codigo_centro("19003472")
        with self.assertRaises(ValidationError):
            validar_codigo_centro("1900")


@override_settings(ALMACEN_PRIVADO=TMP)
class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("datos_demo", stdout=io.StringIO())
        cls.centro = Centro.objects.get()
        cls.daw = Curso.objects.get(nombre="2º DAW")
        cls.asir = Curso.objects.get(nombre="2º ASIR")
        cls.tutor_daw = TutorFFE.objects.get(usuario__username="tutor.daw")
        cls.tutor_asir = TutorFFE.objects.get(usuario__username="tutor.asir")
        cls.empresa = Empresa.objects.get(usuario__username="empresa.demo")
        cls.p_cerrado = Proceso.objects.get(estado=Proceso.Estado.CERRADO)
        cls.p_abierto = Proceso.objects.get(estado=Proceso.Estado.ABIERTO)
        cls.p_otro_tutor = Proceso.objects.get(estado=Proceso.Estado.INICIADO)
        cls.seleccionado = cls.p_cerrado.participaciones.filter(resultado="SELECCIONADO").first().alumno
        cls.candidato = cls.p_abierto.participaciones.first().alumno
        cls.alumno_asir = Alumno.objects.filter(curso=cls.asir).first()

    def entrar(self, usuario):
        self.client.force_login(Usuario.objects.get(username=usuario))


class ReglasProcesoTests(Base):
    def test_candidato_debe_ser_del_curso(self):
        p = Participacion(proceso=self.p_abierto, alumno=self.alumno_asir)
        with self.assertRaisesMessage(ValidationError, "no pertenece al curso"):
            p.full_clean()

    def test_no_se_superan_las_plazas(self):
        libre = Alumno.objects.filter(curso=self.daw).exclude(participaciones__proceso=self.p_cerrado).first()
        p = Participacion(proceso=self.p_cerrado, alumno=libre, resultado="SELECCIONADO")
        with self.assertRaisesMessage(ValidationError, "plaza"):
            p.full_clean()

    def test_un_alumno_no_se_selecciona_en_dos_empresas(self):
        p = Participacion.objects.create(proceso=self.p_abierto, alumno=self.seleccionado)
        p.resultado = "SELECCIONADO"
        with self.assertRaisesMessage(ValidationError, "ya está seleccionado"):
            p.full_clean()

    def test_varios_procesos_a_la_vez_si_estan_pendientes(self):
        p = Participacion(proceso=self.p_abierto, alumno=self.p_cerrado.participaciones.filter(
            resultado="DESCARTADO").first().alumno)
        p.full_clean()  # no lanza

    def test_fecha_de_respuesta_automatica(self):
        p = self.p_abierto.participaciones.first()
        self.assertIsNone(p.fecha_respuesta)
        p.resultado = "DESCARTADO"
        p.save()
        self.assertIsNotNone(p.fecha_respuesta)

    def test_condiciones_heredadas_del_proceso(self):
        p = self.p_cerrado.participaciones.filter(resultado="SELECCIONADO").first()
        self.assertEqual(p.condicion_horas, self.p_cerrado.horas)
        p.horas = 200
        p.save()
        self.assertEqual(p.condicion_horas, 200)

    def test_no_cerrar_sin_condiciones(self):
        self.p_abierto.fecha_inicio = None
        self.p_abierto.save()
        part = self.p_abierto.participaciones.first()
        part.resultado = "SELECCIONADO"
        part.save()
        self.p_abierto.estado = Proceso.Estado.CERRADO
        with self.assertRaisesMessage(ValidationError, "fecha de inicio"):
            self.p_abierto.full_clean()

    def test_tutor_laboral_de_otra_empresa(self):
        otro = TutorLaboral.objects.exclude(empresa=self.p_cerrado.empresa).first()
        self.p_cerrado.tutor_laboral = otro
        with self.assertRaisesMessage(ValidationError, "no pertenece a esta empresa"):
            self.p_cerrado.full_clean()


class VisibilidadTests(Base):
    def test_todos_los_tutores_ven_todos_los_procesos(self):
        self.entrar("tutor.daw")
        r = self.client.get(reverse("tutor:procesos"))
        self.assertContains(r, self.p_otro_tutor.empresa.nombre)  # proceso del otro tutor
        self.assertEqual(self.client.get(reverse("tutor:proceso", args=[self.p_otro_tutor.pk])).status_code, 200)

    def test_tutor_no_modifica_proceso_ajeno(self):
        self.entrar("tutor.daw")
        self.assertEqual(self.client.get(reverse("tutor:editar_proceso", args=[self.p_otro_tutor.pk])).status_code, 403)
        r = self.client.post(reverse("tutor:estado_proceso", args=[self.p_otro_tutor.pk]), {"estado": "CERRADO"})
        self.assertEqual(r.status_code, 403)

    def test_tutor_no_gestiona_curso_ajeno(self):
        self.entrar("tutor.daw")
        self.assertEqual(self.client.get(reverse("tutor:alumnos", args=[self.asir.pk])).status_code, 403)

    def test_proceso_de_otro_centro_no_es_visible(self):
        otro_centro = Centro.objects.create(codigo="45000001", nombre="IES Lejano", localidad="Toledo")
        u = Usuario.objects.create_user("tutor.lejano", "l@example.com", "x", rol="TUTOR")
        TutorFFE.objects.create(usuario=u, centro=otro_centro, nombre="Lejano", apellidos="Tutor", email="l@example.com")
        self.client.force_login(u)
        self.assertEqual(self.client.get(reverse("tutor:proceso", args=[self.p_abierto.pk])).status_code, 403)

    def test_alumno_solo_ve_lo_suyo(self):
        self.entrar(self.seleccionado.dni)
        r = self.client.get(reverse("alumno:panel"))
        self.assertContains(r, self.p_cerrado.empresa.nombre)
        self.assertContains(r, self.daw.tutor.nombre_completo)   # su tutor FFE
        self.assertNotContains(r, self.p_otro_tutor.empresa.nombre)
        self.assertEqual(self.client.get(reverse("tutor:procesos")).status_code, 403)

    def test_empresa_solo_ve_sus_procesos(self):
        self.entrar("empresa.demo")
        self.assertEqual(self.client.get(reverse("empresa:proceso", args=[self.p_cerrado.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("empresa:proceso", args=[self.p_abierto.pk])).status_code, 404)

    def test_empresa_ve_contacto_del_seleccionado_y_no_del_resto(self):
        self.entrar("empresa.demo")
        descartado = self.p_cerrado.participaciones.filter(resultado="DESCARTADO").first().alumno
        self.assertContains(self.client.get(reverse("empresa:alumno", args=[self.seleccionado.pk])), self.seleccionado.email)
        self.assertNotContains(self.client.get(reverse("empresa:alumno", args=[descartado.pk])), descartado.email)


class FlujoTutorTests(Base):
    def test_pantallas(self):
        self.entrar("tutor.daw")
        urls = [reverse("tutor:panel"), reverse("tutor:procesos"), reverse("tutor:nuevo_proceso"),
                reverse("tutor:empresas"), reverse("tutor:nueva_empresa"), reverse("tutor:importar_alumnos"),
                reverse("tutor:importar_empresas"), reverse("tutor:alta_alumno"), reverse("tutor:solicitudes"),
                reverse("tutor:informes"), reverse("tutor:alumnos", args=[self.daw.pk]),
                reverse("tutor:proceso", args=[self.p_abierto.pk]),
                reverse("tutor:empresa", args=[self.empresa.pk])]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_crear_proceso_y_resolverlo(self):
        self.entrar("tutor.daw")
        empresa = Empresa.objects.exclude(procesos__curso=self.daw).first()
        r = self.client.post(reverse("tutor:nuevo_proceso"), {
            "empresa": empresa.pk, "curso": self.daw.pk, "puesto": "QA", "plazas": 1,
            "descripcion": "Pruebas automáticas", "fecha_inicio": "2027-03-01", "fecha_fin": "2027-06-15",
            "horas": 370, "jornada": "MANANA",
        })
        proceso = Proceso.objects.get(puesto="QA")
        self.assertRedirects(r, reverse("tutor:proceso", args=[proceso.pk]))
        self.assertEqual(proceso.tutor, self.tutor_daw)

        libres = Alumno.objects.filter(curso=self.daw).exclude(participaciones__resultado="SELECCIONADO")[:2]
        self.client.post(reverse("tutor:anadir_candidatos", args=[proceso.pk]), {"alumnos": [a.pk for a in libres]})
        self.assertEqual(proceso.participaciones.count(), 2)

        part = proceso.participaciones.first()
        self.client.post(reverse("tutor:participacion", args=[proceso.pk, part.pk]), {
            "resultado": "SELECCIONADO", "observaciones": "", "horas": "", "jornada": "",
        })
        part.refresh_from_db()
        self.assertEqual(part.resultado, "SELECCIONADO")

        self.client.post(reverse("tutor:estado_proceso", args=[proceso.pk]), {"estado": "CERRADO"})
        proceso.refresh_from_db()
        self.assertEqual(proceso.estado, "CERRADO")
        self.assertIsNotNone(proceso.cerrado)

        # el alumno ve sus condiciones
        self.entrar(part.alumno.dni)
        r = self.client.get(reverse("alumno:panel"))
        self.assertContains(r, "370")
        self.assertContains(r, "Mañana")

    def test_seleccion_duplicada_avisa(self):
        self.entrar("tutor.daw")
        part = Participacion.objects.create(proceso=self.p_abierto, alumno=self.seleccionado)
        r = self.client.post(reverse("tutor:participacion", args=[self.p_abierto.pk, part.pk]),
                             {"resultado": "SELECCIONADO", "observaciones": ""}, follow=True)
        self.assertContains(r, "ya está seleccionado")

    def test_registrar_seguimiento_en_proceso(self):
        self.entrar("tutor.daw")
        antes = Seguimiento.objects.count()
        self.client.post(reverse("tutor:seguimiento_proceso", args=[self.p_abierto.pk, self.p_abierto.empresa.pk]), {
            "fecha_hora": timezone.localtime().strftime("%Y-%m-%dT%H:%M"), "medio": "EMAIL", "observaciones": "Envío CVs",
        })
        self.assertEqual(Seguimiento.objects.count(), antes + 1)
        self.assertEqual(Seguimiento.objects.latest("id").proceso, self.p_abierto)

    def test_alta_manual_de_alumno(self):
        self.entrar("tutor.daw")
        r = self.client.post(reverse("tutor:alta_alumno"), {
            "dni": "00000023-t", "nombre": "Nuevo", "apellidos": "Alumno", "email": "n@example.com",
            "telefono": "600000000", "curso": self.daw.pk, "horas_requeridas": 370,
        })
        self.assertContains(r, "Contraseña inicial")
        alumno = Alumno.objects.get(dni="00000023T")
        self.assertTrue(alumno.usuario.debe_cambiar_password)


class ImportacionTests(Base):
    def test_importar_alumnado_con_errores(self):
        csv = ("dni;nombre;apellidos;email;telefono\n"
               "12345678Z;Ana;Pérez;ana@example.com;600111222\n"
               "12345678A;Mal;Letra;x@example.com;\n"
               "12345678Z;Dup;Licado;d@example.com;\n").encode("utf-8-sig")
        r = importar_alumnado(SimpleUploadedFile("a.csv", csv), self.daw)
        self.assertEqual(len(r.creados), 1)
        self.assertEqual([e[0] for e in r.errores], [3, 4])
        self.assertTrue(Usuario.objects.get(username="12345678Z").debe_cambiar_password)

    def test_importar_empresas(self):
        csv = ("cif;nombre;direccion;web;persona_contacto;email;telefono\n"
               "A58818501;Nueva SA;C/ Uno 1;nueva.es;Luis;l@example.com;910000000\n"
               "B00000001;Mala;C/ Dos;;Eva;e@example.com;910000000\n").encode()
        r = importar_empresas(SimpleUploadedFile("e.csv", csv))
        self.assertEqual(len(r.creados), 1)
        self.assertEqual(Empresa.objects.get(cif="A58818501").web, "https://nueva.es")


class AutorregistroTests(Base):
    def test_alumno_se_registra_con_el_codigo(self):
        r = self.client.post(reverse("alumno:registro"), {
            "codigo_matricula": "daw-2627", "dni": "00000023T", "nombre": "Auto", "apellidos": "Registrado",
            "email": "auto@example.com", "telefono": "600000000", "informado": "on",
            "password1": "Clave-Segura-2026", "password2": "Clave-Segura-2026",
        })
        self.assertRedirects(r, reverse("alumno:panel"))
        alumno = Alumno.objects.get(dni="00000023T")
        self.assertEqual(alumno.curso, self.daw)
        self.assertIsNotNone(alumno.informado)

    def test_curso_con_autorregistro_cerrado(self):
        r = self.client.post(reverse("alumno:registro"), {
            "codigo_matricula": "ASIR-2627", "dni": "00000023T", "nombre": "Auto", "apellidos": "Registrado",
            "email": "auto@example.com", "informado": "on",
            "password1": "Clave-Segura-2026", "password2": "Clave-Segura-2026",
        })
        self.assertContains(r, "autorregistro de ese curso está cerrado")
        self.assertFalse(Alumno.objects.filter(dni="00000023T").exists())

    def test_hay_que_aceptar_la_informacion_de_privacidad(self):
        r = self.client.post(reverse("alumno:registro"), {
            "codigo_matricula": "DAW-2627", "dni": "00000023T", "nombre": "Auto", "apellidos": "Registrado",
            "email": "auto@example.com", "password1": "Clave-Segura-2026", "password2": "Clave-Segura-2026",
        })
        self.assertContains(r, "protección de datos")
        self.assertFalse(Alumno.objects.filter(dni="00000023T").exists())

    def test_codigo_invalido(self):
        r = self.client.post(reverse("alumno:registro"), {
            "codigo_matricula": "NOEXISTE", "dni": "00000023T", "nombre": "A", "apellidos": "B",
            "email": "a@example.com", "informado": "on",
            "password1": "Clave-Segura-2026", "password2": "Clave-Segura-2026",
        })
        self.assertContains(r, "no corresponde a ningún curso")


class InformesTests(Base):
    def test_descarga_de_todos_los_informes(self):
        self.entrar("tutor.daw")
        for informe in ["procesos", "participaciones", "alumnos", "empresas", "tutores", "seguimientos"]:
            for formato, firma in [("xlsx", b"PK"), ("pdf", b"%PDF")]:
                with self.subTest(informe=informe, formato=formato):
                    r = self.client.get(reverse("tutor:descargar_informe", args=[informe, formato]))
                    self.assertEqual(r.status_code, 200)
                    self.assertTrue(r.content.startswith(firma))
                    self.assertIn("attachment", r["Content-Disposition"])

    def test_informe_desconocido(self):
        self.entrar("tutor.daw")
        self.assertEqual(self.client.get("/tutor/informes/inventado.xlsx").status_code, 404)

    def test_alumno_no_descarga_informes(self):
        self.entrar(self.seleccionado.dni)
        self.assertEqual(self.client.get(reverse("tutor:descargar_informe", args=["alumnos", "xlsx"])).status_code, 403)


class AdminTests(Base):
    def test_pantallas_de_administracion(self):
        self.entrar("admin")
        for modelo in ["centro", "curso", "tutorffe", "alumno", "empresa", "proceso", "participacion"]:
            with self.subTest(modelo=modelo):
                self.assertEqual(self.client.get(f"/admin/practicas/{modelo}/").status_code, 200)

    def test_alta_de_tutor_desde_admin(self):
        self.entrar("admin")
        r = self.client.post("/admin/practicas/tutorffe/add/", {
            "username": "tutor.nuevo", "password": "clave-segura-1", "centro": self.centro.pk,
            "nombre": "Nuevo", "apellidos": "Tutor", "email": "n@example.com", "telefono": "",
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(TutorFFE.objects.get(usuario__username="tutor.nuevo").usuario.rol, "TUTOR")

    def test_alta_de_curso_con_codigo(self):
        self.entrar("admin")
        self.client.post("/admin/practicas/curso/add/", {
            "centro": self.centro.pk, "nombre": "1º DAW", "anio_inicio": 2026, "anio_fin": 2028,
            "tutor": self.tutor_daw.pk, "codigo_matricula": "daw1-2627", "autorregistro": "on",
        })
        self.assertTrue(Curso.objects.filter(codigo_matricula="DAW1-2627").exists())


@override_settings(ALMACEN_PRIVADO=TMP)
class CVTests(Base):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP, ignore_errors=True)

    def subir(self, contenido, usuario):
        from practicas.models import almacen_privado
        almacen_privado.location = TMP
        self.entrar(usuario)
        return self.client.post(reverse("alumno:cv"), {"cv": SimpleUploadedFile("cv.pdf", contenido, "application/pdf")})

    def test_permisos_de_descarga(self):
        self.assertEqual(self.subir(PDF, self.candidato.dni).status_code, 302)
        url = reverse("cv", args=[self.candidato.pk])
        for usuario in [self.candidato.dni, "tutor.daw", "tutor.asir"]:  # cualquier tutor del centro
            self.entrar(usuario)
            with self.subTest(usuario=usuario):
                self.assertEqual(self.client.get(url).status_code, 200)
        # la empresa ve el CV del alumnado del curso donde tiene procesos (queda registrado)
        self.entrar("empresa.demo")
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(AccesoCV.objects.filter(alumno=self.candidato, rol="EMPRESA").exists())
        # pero no el de un curso en el que no tiene ningún proceso
        otro = reverse("cv", args=[self.alumno_asir.pk])
        self.assertEqual(self.client.get(otro).status_code, 403)
        self.entrar(self.alumno_asir.dni)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_cv_que_no_es_pdf(self):
        r = self.subir(b"MZ\x90\x00 ejecutable", self.candidato.dni)
        self.assertContains(r, "no es un PDF")


class CuentasTests(Base):
    def test_inicio_redirige_por_rol(self):
        for usuario, destino in [("admin", "admin:index"), ("tutor.daw", "tutor:panel"),
                                 ("empresa.demo", "empresa:panel"), (self.seleccionado.dni, "alumno:panel")]:
            self.entrar(usuario)
            self.assertRedirects(self.client.get("/"), reverse(destino), fetch_redirect_response=False)

    def test_portada_publica(self):
        r = self.client.get("/")
        self.assertContains(r, "Crear mi cuenta")
        self.assertContains(r, "Registrar empresa")

    def test_cambio_password_obligatorio(self):
        u = Usuario.objects.get(username=self.candidato.dni)
        u.debe_cambiar_password = True
        u.save()
        self.client.force_login(u)
        self.assertRedirects(self.client.get(reverse("alumno:panel")), reverse("cuentas:cambiar_password"))


class InformeCondicionesTests(Base):
    def test_solo_el_seleccionado_lleva_condiciones(self):
        from practicas.views.exportar import _informe_participaciones
        _, cabeceras, filas = _informe_participaciones(self.centro)
        i_res, i_horas = cabeceras.index("Resultado"), cabeceras.index("Horas")
        for fila in filas:
            if fila[i_res] != "Seleccionado":
                self.assertEqual(fila[i_horas], "", fila)
            else:
                self.assertTrue(fila[i_horas])


class ComentariosCVTests(Base):
    def test_el_tutor_comenta_y_el_alumno_lo_ve(self):
        self.entrar("tutor.daw")
        self.client.post(reverse("tutor:comentar_cv", args=[self.candidato.pk]),
                         {"texto": "Añade los proyectos de DWES y ajusta a una página."})
        comentario = ComentarioCV.objects.get()
        self.assertEqual(comentario.tutor, self.tutor_daw)
        self.entrar(self.candidato.dni)
        self.assertContains(self.client.get(reverse("alumno:panel")), "ajusta a una página")

    def test_la_empresa_no_ve_los_comentarios(self):
        ComentarioCV.objects.create(alumno=self.seleccionado, tutor=self.tutor_daw, texto="Comentario interno")
        self.entrar("empresa.demo")
        self.assertNotContains(self.client.get(reverse("empresa:alumno", args=[self.seleccionado.pk])), "Comentario interno")

    def test_solo_comenta_el_tutor_del_curso(self):
        self.entrar("tutor.asir")
        r = self.client.post(reverse("tutor:comentar_cv", args=[self.candidato.pk]), {"texto": "No debería"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(ComentarioCV.objects.exists())

    def test_ficha_de_alumno_visible_para_cualquier_tutor_del_centro(self):
        self.entrar("tutor.asir")
        r = self.client.get(reverse("tutor:alumno", args=[self.candidato.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Guardar comentario")  # no es su curso


@override_settings(ALMACEN_PRIVADO=TMP)
class ProteccionDatosTests(Base):
    def _subir_cv(self):
        from practicas.models import almacen_privado
        almacen_privado.location = TMP
        self.entrar(self.candidato.dni)
        self.client.post(reverse("alumno:cv"), {"cv": SimpleUploadedFile("cv.pdf", PDF, "application/pdf")})

    def test_pagina_de_privacidad_es_publica(self):
        r = self.client.get(reverse("privacidad"))
        self.assertContains(r, "LOPDGDD")
        self.assertContains(r, "Agencia Española")

    def test_se_registra_quien_descarga_un_cv(self):
        self._subir_cv()
        self.entrar("tutor.daw")
        self.client.get(reverse("cv", args=[self.candidato.pk]))
        acceso = AccesoCV.objects.get(alumno=self.candidato)
        self.assertEqual(acceso.rol, "TUTOR")
        self.assertEqual(acceso.descripcion, self.tutor_daw.nombre_completo)
        # el propio alumno no se registra a sí mismo
        self.entrar(self.candidato.dni)
        self.client.get(reverse("cv", args=[self.candidato.pk]))
        self.assertEqual(AccesoCV.objects.filter(alumno=self.candidato).count(), 1)

    def test_el_alumno_descarga_todos_sus_datos(self):
        import json
        ComentarioCV.objects.create(alumno=self.candidato, tutor=self.tutor_daw, texto="Revisa la ortografía")
        self.entrar(self.candidato.dni)
        r = self.client.get(reverse("alumno:mis_datos"))
        self.assertEqual(r.status_code, 200)
        datos = json.loads(r.content)
        self.assertEqual(datos["identificacion"]["dni"], self.candidato.dni)
        self.assertEqual(datos["comentarios_de_mi_tutor"][0]["texto"], "Revisa la ortografía")
        self.assertTrue(datos["procesos"])

    def test_el_alumno_borra_su_cv(self):
        self._subir_cv()
        self.client.post(reverse("alumno:borrar_cv"))
        self.candidato.refresh_from_db()
        self.assertFalse(self.candidato.cv)

    def test_anonimizacion(self):
        self._subir_cv()
        SolicitudContacto.objects.create(empresa=self.empresa, alumno=self.candidato)
        ComentarioCV.objects.create(alumno=self.candidato, tutor=self.tutor_daw, texto="X")
        participaciones = self.candidato.participaciones.count()
        self.candidato.anonimizar()
        self.candidato.refresh_from_db()
        self.assertEqual(self.candidato.apellidos, "anonimizado")
        self.assertEqual(self.candidato.email, "")
        self.assertFalse(self.candidato.cv)
        self.assertFalse(self.candidato.comentarios_cv.exists())
        self.assertFalse(self.candidato.solicitudes.exists())
        self.assertFalse(self.candidato.usuario.is_active)
        # las participaciones se conservan para las estadísticas del centro
        self.assertEqual(self.candidato.participaciones.count(), participaciones)

    def test_comando_de_purga_simula_por_defecto(self):
        Curso.objects.filter(pk=self.daw.pk).update(anio_inicio=1998, anio_fin=2000)
        salida = io.StringIO()
        call_command("purgar_datos", stdout=salida)
        self.assertIn("Simulación", salida.getvalue())
        self.candidato.refresh_from_db()
        self.assertIsNone(self.candidato.anonimizado)
        call_command("purgar_datos", "--ejecutar", stdout=io.StringIO())
        self.candidato.refresh_from_db()
        self.assertIsNotNone(self.candidato.anonimizado)

    def test_el_pie_enlaza_la_informacion(self):
        self.entrar("tutor.daw")
        self.assertContains(self.client.get(reverse("tutor:panel")), reverse("privacidad"))


class EstaticosTests(TestCase):
    """La hoja de estilos debe servirse también con DEBUG desactivado (las pruebas corren con DEBUG=False)."""

    def test_css_disponible(self):
        r = self.client.get("/static/css/app.css")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"--primario", b"".join(r.streaming_content) if r.streaming else r.content)


class ContrasenasTests(Base):
    def test_el_tutor_restablece_la_contrasena_de_su_alumno(self):
        self.entrar("tutor.daw")
        r = self.client.post(reverse("tutor:restablecer_alumno", args=[self.candidato.pk]))
        self.assertContains(r, "Contraseña nueva")
        usuario = Usuario.objects.get(pk=self.candidato.usuario_id)
        self.assertTrue(usuario.debe_cambiar_password)
        # la contraseña mostrada funciona
        password = r.context["password"]
        self.client.logout()
        self.assertTrue(self.client.login(username=self.candidato.dni, password=password))

    def test_no_restablece_la_de_un_curso_ajeno(self):
        self.entrar("tutor.daw")
        r = self.client.post(reverse("tutor:restablecer_alumno", args=[self.alumno_asir.pk]))
        self.assertEqual(r.status_code, 404)

    def test_restablecer_exige_post(self):
        self.entrar("tutor.daw")
        self.assertEqual(self.client.get(reverse("tutor:restablecer_alumno", args=[self.candidato.pk])).status_code, 405)

    def test_restablecer_la_de_una_empresa(self):
        self.entrar("tutor.daw")
        r = self.client.post(reverse("tutor:restablecer_empresa", args=[self.empresa.pk]))
        self.assertContains(r, "Contraseña nueva")
        self.client.logout()
        self.assertTrue(self.client.login(username="empresa.demo", password=r.context["password"]))

    def test_accion_del_admin_para_tutores(self):
        self.entrar("admin")
        r = self.client.post("/admin/practicas/tutorffe/", {
            "action": "restablecer_contrasena", "_selected_action": [self.tutor_asir.pk],
        }, follow=True)
        self.assertContains(r, "contraseña nueva")
        self.assertTrue(Usuario.objects.get(pk=self.tutor_asir.usuario_id).debe_cambiar_password)

    def test_cualquiera_cambia_su_contrasena(self):
        for usuario in ["tutor.daw", self.candidato.dni, "empresa.demo"]:
            with self.subTest(usuario=usuario):
                self.entrar(usuario)
                r = self.client.post(reverse("cuentas:cambiar_password"), {
                    "old_password": "practicas2026", "new_password1": "Nueva-Clave-2026", "new_password2": "Nueva-Clave-2026",
                })
                self.assertRedirects(r, reverse("inicio"), fetch_redirect_response=False)
                self.client.logout()
                self.assertTrue(self.client.login(username=usuario, password="Nueva-Clave-2026"))

    def test_el_login_explica_que_hacer_si_se_olvida(self):
        self.assertContains(self.client.get(reverse("cuentas:login")), "olvidado la contraseña")


class HorasYDisponibilidadTests(Base):
    def test_horas_pendientes_se_calculan(self):
        a = self.candidato
        a.horas_requeridas, a.horas_exentas = 370, 100
        a.save()
        self.assertEqual(a.horas_pendientes, 270)
        self.assertEqual(a.horas_comprometidas, 0)

    def test_al_seleccionar_se_descuentan(self):
        a = self.seleccionado
        self.assertEqual(a.horas_comprometidas, self.p_cerrado.horas)
        self.assertEqual(a.horas_pendientes, max(a.horas_requeridas - a.horas_exentas - self.p_cerrado.horas, 0))

    def test_no_se_asignan_mas_horas_de_las_pendientes(self):
        a = self.candidato
        a.horas_requeridas, a.horas_exentas = 200, 0
        a.save()
        p = self.p_abierto.participaciones.get(alumno=a)
        p.resultado = "SELECCIONADO"  # el proceso son 370 h
        with self.assertRaisesMessage(ValidationError, "horas pendientes"):
            p.full_clean()
        p.horas = 150  # condiciones propias más cortas: ahora sí cabe
        p.full_clean()

    def test_el_tutor_fija_el_cupo(self):
        self.entrar("tutor.daw")
        self.client.post(reverse("tutor:horas_alumno", args=[self.candidato.pk]),
                         {"horas_requeridas": 240, "horas_exentas": 40})
        self.candidato.refresh_from_db()
        self.assertEqual(self.candidato.horas_pendientes, 200)

    def test_el_alumno_indica_su_disponibilidad(self):
        self.entrar(self.candidato.dni)
        self.client.post(reverse("alumno:perfil"), {
            "email": self.candidato.email, "telefono": "600111222",
            "jornada_preferida": "TARDE", "disponibilidad": "Tardes desde las 15:30",
        })
        self.candidato.refresh_from_db()
        self.assertEqual(self.candidato.disponibilidad, "Tardes desde las 15:30")

    def test_la_empresa_ve_horas_y_disponibilidad(self):
        self.candidato.jornada_preferida = "TARDE"
        self.candidato.disponibilidad = "Tardes desde las 15:30"
        self.candidato.save()
        # la empresa del proceso abierto
        empresa = self.p_abierto.empresa
        usuario = Usuario.objects.create_user("otra.empresa", "o@example.com", "x", rol="EMPRESA")
        empresa.usuario = usuario
        empresa.save()
        self.client.force_login(usuario)
        r = self.client.get(reverse("empresa:proceso", args=[self.p_abierto.pk]))
        self.assertContains(r, "Tardes desde las 15:30")
        self.assertContains(r, f"{self.candidato.horas_pendientes} h")


class PropuestaDeLaEmpresaTests(Base):
    def test_la_empresa_propone_candidatos(self):
        # el proceso cerrado es de empresa.demo; abrimos uno nuevo para poder proponer
        proceso = Proceso.objects.create(empresa=self.empresa, curso=self.daw, tutor=self.tutor_daw,
                                         puesto="Soporte", plazas=1, estado=Proceso.Estado.ABIERTO)
        libre = Alumno.objects.filter(curso=self.daw).exclude(participaciones__proceso=proceso).first()
        self.entrar("empresa.demo")
        r = self.client.get(reverse("empresa:candidatos", args=[proceso.pk]))
        self.assertContains(r, libre.nombre_completo)
        self.client.post(reverse("empresa:candidatos", args=[proceso.pk]), {"alumnos": [libre.pk]})
        participacion = Participacion.objects.get(proceso=proceso, alumno=libre)
        self.assertEqual(participacion.origen, "EMPRESA")
        self.assertEqual(participacion.resultado, "PENDIENTE")
        # el tutor lo ve marcado como propuesto por la empresa
        self.entrar("tutor.daw")
        self.assertContains(self.client.get(reverse("tutor:proceso", args=[proceso.pk])), "Propuesto por la empresa")

    def test_no_propone_alumnado_de_otro_curso(self):
        proceso = Proceso.objects.create(empresa=self.empresa, curso=self.daw, tutor=self.tutor_daw,
                                         puesto="Soporte", plazas=1, estado=Proceso.Estado.ABIERTO)
        self.entrar("empresa.demo")
        self.client.post(reverse("empresa:candidatos", args=[proceso.pk]), {"alumnos": [self.alumno_asir.pk]})
        self.assertFalse(Participacion.objects.filter(proceso=proceso, alumno=self.alumno_asir).exists())

    def test_no_propone_en_proceso_cerrado(self):
        self.entrar("empresa.demo")
        libre = Alumno.objects.filter(curso=self.daw).exclude(participaciones__proceso=self.p_cerrado).first()
        self.client.post(reverse("empresa:candidatos", args=[self.p_cerrado.pk]), {"alumnos": [libre.pk]})
        self.assertFalse(Participacion.objects.filter(proceso=self.p_cerrado, alumno=libre).exists())

    def test_no_propone_en_proceso_ajeno(self):
        self.entrar("empresa.demo")
        self.assertEqual(self.client.get(reverse("empresa:candidatos", args=[self.p_abierto.pk])).status_code, 404)


class AuditoriaTests(Base):
    """Restablecer una contraseña permite entrar como esa persona: tiene que quedar traza."""

    def _registros(self):
        from django.contrib.admin.models import LogEntry
        return LogEntry.objects.filter(change_message__startswith="Contraseña restablecida")

    def test_el_restablecimiento_del_tutor_queda_registrado(self):
        self.entrar("tutor.daw")
        self.client.post(reverse("tutor:restablecer_alumno", args=[self.candidato.pk]))
        registro = self._registros().get()
        self.assertEqual(registro.user, self.tutor_daw.usuario)
        self.assertIn(str(self.daw), registro.change_message)

    def test_el_restablecimiento_del_admin_queda_registrado(self):
        self.entrar("admin")
        self.client.post("/admin/practicas/tutorffe/", {
            "action": "restablecer_contrasena", "_selected_action": [self.tutor_asir.pk],
        }, follow=True)
        registro = self._registros().get()
        self.assertEqual(registro.user.username, "admin")

    def test_el_registro_es_solo_lectura(self):
        self.entrar("admin")
        r = self.client.get("/admin/admin/logentry/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.client.get("/admin/admin/logentry/add/").status_code, 403)

    def test_nadie_puede_leer_contrasenas(self):
        usuario = Usuario.objects.get(username="tutor.daw")
        self.assertTrue(usuario.password.startswith("pbkdf2_"))
        self.assertNotIn("practicas2026", usuario.password)
        self.entrar("admin")
        r = self.client.get(f"/admin/cuentas/usuario/{usuario.pk}/change/")
        self.assertNotContains(r, "practicas2026")
