"""Carga datos de demostración. Uso: python manage.py datos_demo"""
import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from cuentas.models import Rol
from practicas.models import (Alumno, Centro, Curso, Empresa, Jornada, Participacion, Proceso, ResponsableLegal,
                              Seguimiento, TutorFFE, TutorLaboral)
from practicas.validadores import LETRAS_DNI

PASSWORD = "practicas2026"


def dni(n):
    return f"{n:08d}{LETRAS_DNI[n % 23]}"


def cif(letra, n):
    cifras = f"{n:07d}"
    pares = sum(int(c) for c in cifras[1::2])
    impares = sum(sum(divmod(int(c) * 2, 10)) for c in cifras[0::2])
    return f"{letra}{cifras}{(10 - (pares + impares) % 10) % 10}"


NOMBRES = ["Lucía", "Hugo", "Martina", "Mateo", "Sofía", "Leo", "Valeria", "Daniel", "Julia", "Pablo", "Carla",
           "Álvaro", "Noa", "Adrián", "Irene", "Marco"]
APELLIDOS = ["García Pérez", "Martín López", "Sánchez Ruiz", "Gómez Díaz", "Fernández Moreno", "Jiménez Álvarez",
             "Romero Navarro", "Torres Gil", "Ramos Serrano", "Castro Molina", "Ortega Delgado", "Rubio Marín",
             "Sanz Iglesias", "Núñez Medina", "Prieto Garrido", "Vidal Cortés"]
EMPRESAS = [
    ("Soluciones Web Henares SL", "C/ Mayor 12, Guadalajara", "https://example.com/solweb", "Ana López"),
    ("Datos y Nube Alcarria SL", "Av. del Ejército 4, Guadalajara", "https://example.com/datosnube", "Jorge Pastor"),
    ("Taller Digital Tajo SA", "C/ Toledo 30, Madrid", "https://example.com/tallerdigital", "Marta Cabello"),
    ("Sistemas Castilla Informática SL", "Pol. Ind. El Henares, parcela 8, Guadalajara", "", "Raúl Benito"),
]


class Command(BaseCommand):
    help = "Crea centro, cursos, tutores, alumnado, empresas y procesos de ejemplo."

    def add_arguments(self, parser):
        parser.add_argument("--forzar", action="store_true", help="Crear aunque ya existan datos.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        if Centro.objects.exists() and not opciones["forzar"]:
            raise CommandError("Ya hay datos. Usa --forzar si quieres añadir los de demostración igualmente.")
        random.seed(7)
        U = get_user_model()
        hoy = timezone.localdate()

        if not U.objects.filter(username="admin").exists():
            U.objects.create_superuser("admin", "admin@example.com", PASSWORD, first_name="Administración")

        centro = Centro.objects.create(codigo="19003472", nombre="IES Ejemplo", localidad="Guadalajara",
                                       provincia="Guadalajara", email="secretaria@example.com", telefono="949000000")

        tutores = []
        for usuario, nombre, apellidos in [("tutor.daw", "Elena", "Muñoz Herrero"), ("tutor.asir", "Tomás", "Calvo Rey")]:
            u = U.objects.create_user(usuario, f"{usuario}@example.com", PASSWORD, rol=Rol.TUTOR,
                                      first_name=nombre, last_name=apellidos)
            tutores.append(TutorFFE.objects.create(usuario=u, centro=centro, nombre=nombre, apellidos=apellidos,
                                                   email=u.email, telefono="949111222"))

        daw = Curso.objects.create(centro=centro, nombre="2º DAW", anio_inicio=hoy.year - 1, anio_fin=hoy.year + 1,
                                   tutor=tutores[0], codigo_matricula="DAW-2627", autorregistro=True)
        asir = Curso.objects.create(centro=centro, nombre="2º ASIR", anio_inicio=hoy.year - 1, anio_fin=hoy.year + 1,
                                    tutor=tutores[1], codigo_matricula="ASIR-2627", autorregistro=False)

        alumnos = []
        for i in range(16):
            curso = daw if i < 10 else asir
            documento = dni(51000000 + i * 7919)
            email = f"alumno{i + 1}@example.com"
            u = U.objects.create_user(documento, email, PASSWORD, rol=Rol.ALUMNO,
                                      first_name=NOMBRES[i], last_name=APELLIDOS[i])
            # Cupos variables: lo normal son 370 h, pero hay exenciones parciales y ciclos distintos.
            requeridas = 370 if i % 5 else 240
            exentas = 120 if i % 7 == 0 else 0
            jornada = [Jornada.MANANA, Jornada.TARDE, Jornada.FLEXIBLE][i % 3]
            disponibilidad = ["Mañanas de 8:00 a 14:00", "Tardes a partir de las 15:30",
                              "Flexible, salvo los viernes por la tarde"][i % 3]
            alumnos.append(Alumno.objects.create(usuario=u, dni=documento, nombre=NOMBRES[i], apellidos=APELLIDOS[i],
                                                 email=email, telefono=f"6{random.randint(10000000, 99999999)}",
                                                 curso=curso, horas_requeridas=requeridas, horas_exentas=exentas,
                                                 jornada_preferida=jornada, disponibilidad=disponibilidad))

        empresas = []
        for i, (nombre, direccion, web, contacto) in enumerate(EMPRESAS):
            e = Empresa.objects.create(cif=cif("B", 1234560 + i * 1111), nombre=nombre, direccion=direccion, web=web,
                                       persona_contacto=contacto, email=f"rrhh{i + 1}@example.com",
                                       telefono=f"9{random.randint(10000000, 99999999)}")
            ResponsableLegal.objects.create(empresa=e, nombre=f"Responsable de {nombre.split()[0]}", dni=dni(70000000 + i * 131))
            for j in range(1 if i == 3 else 2):
                TutorLaboral.objects.create(empresa=e, nombre=f"{random.choice(NOMBRES)} {random.choice(APELLIDOS)}",
                                            dni=dni(80000000 + i * 100 + j), telefono=f"6{random.randint(10000000, 99999999)}",
                                            email=f"tutor{i + 1}{j + 1}@example.com")
            Seguimiento.objects.create(empresa=e, tutor=tutores[i % 2], fecha_hora=timezone.now() - timedelta(days=20 - i),
                                       medio="TELEFONO", observaciones="Primer contacto del curso. Confirman interés.")
            empresas.append(e)

        # Proceso cerrado con alumnado seleccionado
        p1 = Proceso.objects.create(empresa=empresas[0], curso=daw, tutor=tutores[0], puesto="Desarrollo backend",
                                    plazas=2, estado=Proceso.Estado.CERRADO, descripcion="Spring Boot y API REST.",
                                    tutor_laboral=empresas[0].tutores.first(),
                                    fecha_inicio=hoy + timedelta(days=30), fecha_fin=hoy + timedelta(days=120),
                                    horas=370, jornada=Jornada.MANANA)
        for alumno, resultado in [(alumnos[0], "SELECCIONADO"), (alumnos[1], "SELECCIONADO"), (alumnos[2], "DESCARTADO")]:
            if resultado == "SELECCIONADO" and alumno.horas_pendientes < p1.horas:
                alumno.horas_requeridas = p1.horas + alumno.horas_exentas
                alumno.save()
            Participacion.objects.create(proceso=p1, alumno=alumno, resultado=resultado)
        Seguimiento.objects.create(empresa=empresas[0], proceso=p1, tutor=tutores[0],
                                   fecha_hora=timezone.now() - timedelta(days=5), medio="ENTREVISTA",
                                   observaciones="Entrevistan a tres candidatos; eligen a dos.")

        # Proceso abierto con candidatos pendientes
        p2 = Proceso.objects.create(empresa=empresas[1], curso=daw, tutor=tutores[0], puesto="Frontend y accesibilidad",
                                    plazas=1, estado=Proceso.Estado.ABIERTO, horas=370, jornada=Jornada.TARDE,
                                    fecha_inicio=hoy + timedelta(days=30))
        for alumno in alumnos[3:6]:
            Participacion.objects.create(proceso=p2, alumno=alumno)
        # Una candidatura propuesta por la propia empresa
        Participacion.objects.create(proceso=p2, alumno=alumnos[6], origen=Participacion.Origen.EMPRESA)

        # Proceso de otro tutor, visible para todos
        p3 = Proceso.objects.create(empresa=empresas[2], curso=asir, tutor=tutores[1], puesto="Administración de sistemas",
                                    plazas=2, estado=Proceso.Estado.INICIADO)
        for alumno in alumnos[10:13]:
            Participacion.objects.create(proceso=p3, alumno=alumno)

        # Una empresa con acceso a la aplicación
        empresas[0].usuario = U.objects.create_user("empresa.demo", empresas[0].email, PASSWORD, rol=Rol.EMPRESA)
        empresas[0].save()

        self.stdout.write(self.style.SUCCESS("Datos de demostración creados."))
        self.stdout.write(f"Contraseña de todos los usuarios: {PASSWORD}")
        self.stdout.write("  admin         → administración (centro, cursos, tutores)")
        self.stdout.write("  tutor.daw     → tutora FFE de 2º DAW")
        self.stdout.write("  tutor.asir    → tutor FFE de 2º ASIR")
        self.stdout.write(f"  {alumnos[0].dni}     → alumno seleccionado (entra con su DNI)")
        self.stdout.write(f"  {alumnos[3].dni}     → alumno en proceso abierto")
        self.stdout.write("  empresa.demo  → empresa Soluciones Web Henares")
        self.stdout.write("Código de autorregistro de 2º DAW: DAW-2627")
