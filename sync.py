"""Sincroniza los datos de Siesa hacia la base de datos local.

Se puede usar de dos formas:
1. Manual: botón "Sincronizar ahora" dentro de la app (ver app.py).
2. Automática: programar este script para correr solo, por ejemplo con
   una tarea de Windows Task Scheduler o un cron de Linux:

       */15 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/python sync.py

   Así los 3 usuarios siempre ven datos frescos sin depender de que alguien
   dé clic en "Sincronizar" manualmente.
"""
import sys

from siesa_client import obtener_todas_las_paginas, SiesaError
from data import normalizar
import db
import backup


def sincronizar() -> dict:
    """Trae todo desde Siesa y reemplaza el contenido local.
    Devuelve un resumen para mostrar en la UI o en logs."""
    registros = obtener_todas_las_paginas()
    df = normalizar(registros)
    db.reemplazar_datos(df)
    db.upsert_clientes(df)  # actualiza datos de Siesa sin tocar campos manuales
    backup.hacer_backup_diario()  # no-op si ya hay respaldo de hoy
    # Inicializar gestiones retroactivas y recalcular todos los estados
    db.inicializar_gestiones_retroactivas()
    db.recalcular_todos_los_estados_gestion()
    return {"total_registros": len(df)}


if __name__ == "__main__":
    try:
        resumen = sincronizar()
        print(f"Sincronización exitosa: {resumen['total_registros']} registros guardados.")
    except SiesaError as e:
        print(f"Error de sincronización: {e}", file=sys.stderr)
        sys.exit(1)
