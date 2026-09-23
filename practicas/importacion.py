"""Importación masiva de alumnado y empresas desde CSV."""
import base64
import csv
import io
import secrets
import string
from dataclasses import dataclass, field

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction

from cuentas.models import Rol

from .models import Alumno, Empresa
from .validadores import normalizar_documento, validar_cif, validar_dni_nie, validar_telefono

COLUMNAS_ALUMNADO = ["dni", "nombre", "apellidos", "email", "telefono"]
COLUMNAS_EMPRESAS = ["cif", "nombre", "direccion", "web", "persona_contacto", "email", "telefono"]


class ErrorCSV(Exception):
    pass


@dataclass
class Resultado:
    creados: list = field(default_factory=list)
    errores: list = field(default_factory=list)  # (número de línea, datos, motivo)
    credenciales: list = field(default_factory=list)  # (usuario, contraseña, nombre)

    def credenciales_csv_base64(self):
        salida = io.StringIO()
        escritor = csv.writer(salida, delimiter=";")
        escritor.writerow(["usuario", "contrasena_inicial", "nombre"])
        escritor.writerows(self.credenciales)
        return base64.b64encode(("\ufeff" + salida.getvalue()).encode("utf-8")).decode()


def generar_password(longitud=10):
    alfabeto = string.ascii_letters + string.digits
    alfabeto = "".join(c for c in alfabeto if c not in "0OoIl1")
    return "".join(secrets.choice(alfabeto) for _ in range(longitud))


def leer_csv(fichero, columnas):
    try:
        texto = fichero.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ErrorCSV("El fichero no está en UTF-8. Guárdalo como «CSV UTF-8» desde la hoja de cálculo.")
    muestra = texto[:2048]
    separador = ";" if muestra.count(";") >= muestra.count(",") else ","
    lector = csv.DictReader(io.StringIO(texto), delimiter=separador)
    cabecera = [(c or "").strip().lower() for c in (lector.fieldnames or [])]
    faltan = [c for c in columnas if c not in cabecera]
    if faltan:
        raise ErrorCSV(f"Faltan columnas en la cabecera: {', '.join(faltan)}. Se esperan: {';'.join(columnas)}")
    lector.fieldnames = cabecera
    for numero, fila in enumerate(lector, start=2):
        limpia = {k: (v or "").strip() for k, v in fila.items() if k}
        if any(limpia.values()):
            yield numero, limpia


def _mensaje(error):
    if hasattr(error, "message_dict"):
        return "; ".join(f"{k}: {' '.join(v)}" for k, v in error.message_dict.items())
    return " ".join(error.messages)


def importar_alumnado(fichero, curso):
    Usuario = get_user_model()
    resultado = Resultado()
    for linea, fila in leer_csv(fichero, COLUMNAS_ALUMNADO):
        try:
            dni = normalizar_documento(fila["dni"])
            validar_dni_nie(dni)
            if not fila["nombre"] or not fila["apellidos"]:
                raise ValidationError("Nombre y apellidos son obligatorios.")
            validate_email(fila["email"])
            if fila["telefono"]:
                validar_telefono(fila["telefono"])
            if Alumno.objects.filter(dni=dni).exists() or Usuario.objects.filter(username=dni).exists():
                raise ValidationError(f"Ya existe un alumno o usuario con DNI {dni}.")
            password = generar_password()
            with transaction.atomic():
                usuario = Usuario.objects.create_user(
                    username=dni, password=password, email=fila["email"], first_name=fila["nombre"],
                    last_name=fila["apellidos"], rol=Rol.ALUMNO, debe_cambiar_password=True,
                )
                alumno = Alumno(
                    usuario=usuario, dni=dni, nombre=fila["nombre"], apellidos=fila["apellidos"],
                    email=fila["email"], telefono=fila["telefono"], curso=curso,
                )
                alumno.full_clean(exclude=["usuario", "cv"])
                alumno.save()
            resultado.creados.append(alumno)
            resultado.credenciales.append((dni, password, alumno.nombre_completo))
        except ValidationError as e:
            resultado.errores.append((linea, fila.get("dni", ""), _mensaje(e)))
        except IntegrityError:
            resultado.errores.append((linea, fila.get("dni", ""), "Registro duplicado."))
    return resultado


def importar_empresas(fichero):
    resultado = Resultado()
    for linea, fila in leer_csv(fichero, COLUMNAS_EMPRESAS):
        try:
            cif = normalizar_documento(fila["cif"])
            validar_cif(cif)
            if Empresa.objects.filter(cif=cif).exists():
                raise ValidationError(f"Ya existe una empresa con CIF {cif}.")
            web = fila["web"]
            if web and not web.startswith(("http://", "https://")):
                web = "https://" + web
            empresa = Empresa(
                cif=cif, nombre=fila["nombre"], direccion=fila["direccion"], web=web,
                persona_contacto=fila["persona_contacto"], email=fila["email"], telefono=fila["telefono"],
            )
            empresa.full_clean(exclude=["usuario"])
            empresa.save()
            resultado.creados.append(empresa)
        except ValidationError as e:
            resultado.errores.append((linea, fila.get("cif", ""), _mensaje(e)))
        except IntegrityError:
            resultado.errores.append((linea, fila.get("cif", ""), "Registro duplicado."))
    return resultado
