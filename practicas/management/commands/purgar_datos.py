"""Conservación limitada de datos (art. 5.1.e RGPD).

Anonimiza al alumnado de cursos terminados hace más de N años y elimina los CV que queden,
las solicitudes de contacto y la traza de accesos. Los procesos se conservan sin datos
identificativos, para poder seguir sacando estadísticas del centro.

Uso:  python manage.py purgar_datos            (simulación)
      python manage.py purgar_datos --ejecutar
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from practicas.models import AccesoCV, Alumno


class Command(BaseCommand):
    help = "Anonimiza alumnado de cursos antiguos según el plazo de conservación configurado."

    def add_arguments(self, parser):
        parser.add_argument("--anios", type=int, default=settings.RESPONSABLE["conservacion_anios"],
                            help="Años desde el fin del curso (por defecto, LOPD_CONSERVACION_ANIOS).")
        parser.add_argument("--ejecutar", action="store_true", help="Sin esta opción solo se simula.")
        parser.add_argument("--accesos-dias", type=int, default=365,
                            help="Días que se conserva la traza de accesos a los CV.")

    @transaction.atomic
    def handle(self, *args, **opciones):
        limite = timezone.localdate().year - opciones["anios"]
        candidatos = Alumno.objects.filter(curso__anio_fin__lt=limite, anonimizado__isnull=True)
        self.stdout.write(f"Cursos terminados antes de {limite}: {candidatos.count()} alumnos a anonimizar.")
        for alumno in candidatos:
            self.stdout.write(f"  {alumno.dni} · {alumno.nombre_completo} · {alumno.curso}")
            if opciones["ejecutar"]:
                alumno.anonimizar()

        corte = timezone.now() - timezone.timedelta(days=opciones["accesos_dias"])
        accesos = AccesoCV.objects.filter(fecha__lt=corte)
        self.stdout.write(f"Accesos a CV anteriores a {corte:%d/%m/%Y}: {accesos.count()}.")
        if opciones["ejecutar"]:
            accesos.delete()
            self.stdout.write(self.style.SUCCESS("Purga realizada."))
        else:
            self.stdout.write(self.style.WARNING("Simulación: no se ha modificado nada. Añade --ejecutar."))
