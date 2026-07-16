"""Agregaciones para los gráficos y reportes de la app.
Mantiene la lógica de cómputo separada de la UI (Streamlit)."""
import pandas as pd

MESES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]
NUMERO_A_MES = dict(enumerate(MESES, start=1))


def valor_facturado_por_mes(
    historial: pd.DataFrame,
    anios_seleccionados: list[int] | None = None,
    meses_seleccionados: list[int] | None = None,
) -> pd.DataFrame:
    """Agrupa el valor neto facturado por año, mes y moneda, a partir de
    'fecha_facturacion'. Solo considera prefacturas que ya tienen fecha
    de facturación (es decir, ignora las que están 'Sin Facturar').

    Devuelve un DataFrame pivotado: filas = mes (en orden Enero-Diciembre,
    solo los meses presentes en la selección), columnas = "MONEDA-AÑO" (ej.
    "COP-2025", "USD-2026"), valores = suma de f310_vlr_neto. Los huecos se
    rellenan con 0 para que el gráfico no tenga barras faltantes.
    """
    facturadas = historial[historial['fecha_facturacion'].notna()].copy()

    if facturadas.empty:
        return pd.DataFrame()

    facturadas['anio'] = facturadas['fecha_facturacion'].dt.year
    facturadas['mes_num'] = facturadas['fecha_facturacion'].dt.month

    if anios_seleccionados:
        facturadas = facturadas[facturadas['anio'].isin(anios_seleccionados)]
    if meses_seleccionados:
        facturadas = facturadas[facturadas['mes_num'].isin(meses_seleccionados)]

    if facturadas.empty:
        return pd.DataFrame()

    agrupado = (
        facturadas.groupby(['anio', 'mes_num', 'f310_id_moneda_docto'])['f310_vlr_neto']
        .sum()
        .reset_index()
    )
    agrupado['moneda_anio'] = agrupado['f310_id_moneda_docto'] + '-' + agrupado['anio'].astype(str)

    tabla = agrupado.pivot(index='mes_num', columns='moneda_anio', values='f310_vlr_neto').fillna(0)

    meses_a_mostrar = sorted(meses_seleccionados) if meses_seleccionados else list(range(1, 13))
    tabla = tabla.reindex(meses_a_mostrar, fill_value=0)
    tabla.index = pd.Index([NUMERO_A_MES[m] for m in tabla.index], name='Mes')

    return tabla