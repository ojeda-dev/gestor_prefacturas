"""Respaldo automático de la base de datos SQLite.

Se ejecuta como parte de sync.sincronizar(), así que no requiere ningún
paso manual adicional -- cada vez que alguien sincroniza (botón o cron),
de paso se asegura de que exista un respaldo del día. Como está pensado
para correr varias veces al día, solo genera UN respaldo por día
calendario (no uno por cada sincronización), y conserva los últimos 30
días -- suficiente para recuperarse de un archivo corrupto o borrado por
accidente sin acumular espacio indefinidamente.
"""
import shutil
from datetime import datetime
from pathlib import Path

from config import DB_PATH

CARPETA_BACKUPS = DB_PATH.parent / "backups"
DIAS_A_CONSERVAR = 30


def hacer_backup_diario() -> Path | None:
    """Copia la base de datos actual a backups/prefacturas_YYYYMMDD.db,
    si todavía no existe un respaldo de hoy. Devuelve la ruta del
    respaldo creado, o None si no se creó nada (ya existía uno de hoy,
    o la base de datos todavía no existe)."""
    if not DB_PATH.exists():
        return None

    CARPETA_BACKUPS.mkdir(parents=True, exist_ok=True)
    marca_de_hoy = datetime.now().strftime("%Y%m%d")
    destino = CARPETA_BACKUPS / f"prefacturas_{marca_de_hoy}.db"

    if destino.exists():
        _limpiar_backups_viejos()
        return None

    shutil.copy2(DB_PATH, destino)
    _limpiar_backups_viejos()
    return destino


def _limpiar_backups_viejos() -> None:
    respaldos = sorted(CARPETA_BACKUPS.glob("prefacturas_*.db"))
    exceso = len(respaldos) - DIAS_A_CONSERVAR
    for viejo in respaldos[:max(exceso, 0)]:
        viejo.unlink()


def listar_backups() -> list[dict]:
    """Para mostrar en la UI: nombre, fecha y tamaño de cada respaldo."""
    if not CARPETA_BACKUPS.exists():
        return []

    resultado = []
    for archivo in sorted(CARPETA_BACKUPS.glob("prefacturas_*.db"), reverse=True):
        resultado.append({
            "nombre": archivo.name,
            "tamano_mb": round(archivo.stat().st_size / 1024 / 1024, 2),
            "modificado_en": datetime.fromtimestamp(archivo.stat().st_mtime),
        })
    return resultado
