"""Lógica de gestión de prefacturas: cálculo de días hábiles
(excluyendo fines de semana y festivos colombianos) y determinación
de estados de seguimiento (Pendiente, Recordatorio, Suspender)."""
from datetime import date, timedelta

from holidays import Colombia


def es_dia_habil(fecha: date) -> bool:
    """True si la fecha es lunes-viernes y no es festivo colombiano."""
    if fecha.weekday() >= 5:
        return False
    return fecha not in Colombia(years=fecha.year)


def contar_dias_habiles(fecha_inicio: date, fecha_fin: date) -> int:
    """Cuenta los días hábiles entre fecha_inicio y fecha_fin (ambas incluidas)."""
    if fecha_inicio > fecha_fin:
        return 0
    dias = 0
    actual = fecha_inicio
    while actual <= fecha_fin:
        if es_dia_habil(actual):
            dias += 1
        actual += timedelta(days=1)
    return dias


def calcular_estado_gestion(
    fecha_primer_correo: date,
    hoy: date,
    dias_recordatorio: int,
    dias_suspender: int,
) -> tuple[str, int]:
    """Determina el estado de gestión y los días hábiles transcurridos.

    Retorna (estado, dias_habiles) donde estado es uno de:
    'Pendiente', 'Recordatorio' o 'Suspender'."""
    dias = contar_dias_habiles(fecha_primer_correo, hoy)
    if dias >= dias_suspender:
        estado = "Suspender"
    elif dias >= dias_recordatorio:
        estado = "Recordatorio"
    else:
        estado = "Pendiente"
    return estado, dias


def listar_festivos_colombianos(anio: int) -> list[date]:
    """Retorna los festivos colombianos del año dado, ordenados cronológicamente."""
    co = Colombia(years=anio)
    return sorted(co.keys())
