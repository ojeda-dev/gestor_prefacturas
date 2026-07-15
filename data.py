"""Transforma datos crudos de Siesa en algo consistente para guardar en BD."""
import pandas as pd

from config import COLUMNAS_ESPERADAS


_VALORES_VACIOS = {"", "-", "--", "n/a", "na", "null", "none", "nan", "s/n"}


def _tiene_valor(valor) -> bool:
    """pd.notna() no detecta como 'sin valor' varios placeholders que
    Siesa usa en vez de null cuando un campo no aplica: cadenas vacías,
    solo espacios, o literalmente un guión '-'. Esto causaba que
    prefacturas sin número de factura real (mostrando '-' en la columna
    Factura) quedaran marcadas como 'Facturada' solo porque el campo
    técnicamente no era NaN."""
    if pd.isna(valor):
        return False
    if isinstance(valor, str) and valor.strip().lower() in _VALORES_VACIOS:
        return False
    return True


def _determinar_estado(row) -> str:
    if _tiene_valor(row.get('fecha_anulado')):
        return "Anulada"
    elif _tiene_valor(row.get('factura')):
        return "Facturada"
    else:
        return "Sin Facturar"


def normalizar(registros: list[dict]) -> pd.DataFrame:
    """Convierte la lista de registros crudos de la API en un DataFrame
    con tipos correctos y la columna 'estado' calculada, listo para
    guardar en la base de datos."""
    df = pd.DataFrame(registros)

    if df.empty:
        return df

    for col in COLUMNAS_ESPERADAS:
        if col not in df.columns:
            df[col] = pd.NA

    df['f310_vlr_neto'] = pd.to_numeric(df['f310_vlr_neto'], errors='coerce')
    df['f310_vlr_bruto'] = pd.to_numeric(df['f310_vlr_bruto'], errors='coerce')
    df['f310_vlr_dscto'] = pd.to_numeric(df['f310_vlr_dscto'], errors='coerce')
    df['f310_vlr_imp'] = pd.to_numeric(df['f310_vlr_imp'], errors='coerce')

    for col in ('fecha_creacion', 'fecha_aprovacion', 'fecha_facturacion', 'fecha_anulado'):
        df[col] = pd.to_datetime(df[col], errors='coerce')

    df['estado'] = df.apply(_determinar_estado, axis=1)
    return df