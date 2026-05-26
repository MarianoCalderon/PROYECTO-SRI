import re
import unicodedata


def normalizar_clave(valor: str) -> str:
    """Convierte texto libre en una clave estable para Redis."""
    if not valor:
        return "desconocido"
    texto = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode("ascii")
    texto = texto.lower().strip()
    texto = re.sub(r"[^a-z0-9]+", "_", texto)
    texto = texto.strip("_")
    return texto or "desconocido"
