"""Buscador para el listado de prefacturas.

Estrategia en dos pasos:
1. Búsqueda exacta (insensible a mayúsculas y tildes) por substring en
   cliente, NIT, prefactura o factura. Cubre el 95% de los casos y es
   instantánea.
2. Si la búsqueda exacta no encuentra nada, se cae a una búsqueda difusa
   (fuzzy) contra los nombres de cliente, tolerante a errores de tipeo
   (ej. "autometa" con una letra de más/menos, o cambiada de lugar).
"""
import unicodedata

import pandas as pd
from rapidfuzz import fuzz, process

COLUMNAS_BUSCABLES = ['f200_razon_social', 'f200_nit', 'prefactura', 'factura']

UMBRAL_FUZZY = 70  # 0-100. Más alto = más exigente (menos falsos positivos).
MIN_LARGO_FUZZY = 3  # no vale la pena hacer fuzzy con 1-2 caracteres


def _normalizar_texto(texto) -> str:
    """minúsculas + sin tildes/diacríticos, para comparar 'Automata' con 'AUTOMETA'."""
    if pd.isna(texto):
        return ""
    texto = str(texto).lower()
    texto = unicodedata.normalize('NFKD', texto)
    return "".join(c for c in texto if not unicodedata.combining(c))


def buscar(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Devuelve las filas de df que coinciden con la búsqueda."""
    query = (query or "").strip()
    if not query:
        return df

    query_normalizada = _normalizar_texto(query)

    # --- Paso 1: búsqueda exacta (substring) ---------------------------------
    mascara = pd.Series(False, index=df.index)
    for col in COLUMNAS_BUSCABLES:
        columna_normalizada = df[col].apply(_normalizar_texto)
        mascara |= columna_normalizada.str.contains(query_normalizada, na=False, regex=False)

    resultado_exacto = df[mascara]
    if not resultado_exacto.empty:
        return resultado_exacto

    # --- Paso 2: fuzzy sobre nombres de cliente (tolerante a typos) ----------
    if len(query_normalizada) < MIN_LARGO_FUZZY:
        return df.iloc[0:0]  # sin resultados, pero mantiene las columnas

    clientes_unicos = df['f200_razon_social'].dropna().unique()
    clientes_normalizados = {c: _normalizar_texto(c) for c in clientes_unicos}

    coincidencias = process.extract(
        query_normalizada,
        clientes_normalizados,
        scorer=fuzz.partial_ratio,
        limit=10,
    )
    clientes_encontrados = [nombre_original for _, score, nombre_original in coincidencias if score >= UMBRAL_FUZZY]

    if not clientes_encontrados:
        return df.iloc[0:0]

    return df[df['f200_razon_social'].isin(clientes_encontrados)]
