import re

from django.core.exceptions import ValidationError

LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


def normalizar_documento(valor):
    return re.sub(r"[\s\-.]", "", (valor or "")).upper()


def validar_dni_nie(valor):
    """Valida un DNI (12345678Z) o NIE (X1234567L) comprobando la letra de control."""
    doc = normalizar_documento(valor)
    if re.fullmatch(r"\d{8}[A-Z]", doc):
        numero = doc[:8]
    elif re.fullmatch(r"[XYZ]\d{7}[A-Z]", doc):
        numero = str("XYZ".index(doc[0])) + doc[1:8]
    else:
        raise ValidationError("Formato no válido. Usa 8 cifras y letra (DNI) o X/Y/Z, 7 cifras y letra (NIE).")
    if LETRAS_DNI[int(numero) % 23] != doc[-1]:
        raise ValidationError("La letra de control no coincide.")


def validar_cif(valor):
    """Valida un CIF (B12345678) o, para autónomos, un DNI/NIE."""
    doc = normalizar_documento(valor)
    if re.fullmatch(r"\d{8}[A-Z]|[XYZ]\d{7}[A-Z]", doc):
        return validar_dni_nie(doc)
    if not re.fullmatch(r"[ABCDEFGHJNPQRSUVW]\d{7}[0-9A-J]", doc):
        raise ValidationError("Formato de CIF no válido (letra, 7 cifras y carácter de control).")
    cifras = doc[1:8]
    pares = sum(int(c) for c in cifras[1::2])
    impares = sum(sum(divmod(int(c) * 2, 10)) for c in cifras[0::2])
    control = (10 - (pares + impares) % 10) % 10
    esperado_num, esperado_letra = str(control), "JABCDEFGHI"[control]
    letra_org = doc[0]
    final = doc[-1]
    if letra_org in "PQRSNW":
        validos = {esperado_letra}
    elif letra_org in "ABEH":
        validos = {esperado_num}
    else:
        validos = {esperado_num, esperado_letra}
    if final not in validos:
        raise ValidationError("El carácter de control del CIF no es correcto.")


def validar_codigo_centro(valor):
    """Código de centro educativo: 8 cifras (por ejemplo 19003472)."""
    if not re.fullmatch(r"\d{8}", (valor or "").strip()):
        raise ValidationError("El código de centro son 8 cifras.")


def validar_telefono(valor):
    tel = re.sub(r"[\s\-.()]", "", valor or "")
    if not re.fullmatch(r"(\+\d{1,3})?\d{9}", tel):
        raise ValidationError("Teléfono no válido (9 cifras, con prefijo internacional opcional).")


def validar_pdf(fichero):
    from django.conf import settings

    if fichero.size > settings.CV_TAMANO_MAXIMO:
        raise ValidationError("El PDF no puede superar 5 MB.")
    inicio = fichero.read(5)
    fichero.seek(0)
    if inicio != b"%PDF-":
        raise ValidationError("El fichero no es un PDF válido.")
