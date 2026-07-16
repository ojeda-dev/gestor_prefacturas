import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Control Prefacturas", layout="wide")

URL_API = "https://apiqa.siesacloud.com/connekta/siesa/dinamico/consulta/v3.0.1"
TOTAL_PAGINAS_FALLBACK = 13  # Solo se usa si por algún motivo la API no informa el total

COLUMNAS_ESPERADAS = [
    'f200_razon_social', 'f200_nit', 'prefactura', 'f310_vlr_neto',
    'fecha_facturacion', 'factura', 'fecha_anulado', 'f015_email',
]

COLUMNAS_VISIBLES = {
    'f200_razon_social': 'Cliente',
    'prefactura': 'Prefactura',
    'f310_vlr_neto': 'Valor',
    'Estado': 'Estado',
    'fecha_facturacion': 'Fecha Facturacion',
    'factura': 'Factura',
}


def _headers():
    return {
        "client_id": st.secrets["siesa"]["client_id"],
        "ConniKey": st.secrets["siesa"]["ConniKey"],
        "ConniToken": st.secrets["siesa"]["ConniToken"],
    }


def _determinar_estado(row):
    if pd.notna(row.get('fecha_anulado')):
        return "Anulada"
    elif pd.notna(row.get('factura')):
        return "Facturada"
    else:
        return "Sin Facturar"


def _normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Garantiza que existan todas las columnas esperadas y que los tipos sean correctos."""
    if df.empty:
        return df

    for col in COLUMNAS_ESPERADAS:
        if col not in df.columns:
            df[col] = pd.NA

    df['f310_vlr_neto'] = pd.to_numeric(df['f310_vlr_neto'], errors='coerce')

    for col in ('fecha_facturacion', 'fecha_anulado'):
        df[col] = pd.to_datetime(df[col], errors='coerce')

    df['Estado'] = df.apply(_determinar_estado, axis=1)
    return df


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_pagina_raw(numero_pagina: int):
    """Trae el JSON crudo de una página. Devuelve None si algo falló
    (el error ya se le muestra al usuario aquí mismo)."""
    query_params = {
        "idCompania": "7661",
        "descripcion": "cloudfleet_Control_Prefacturas",
        "paginacion": f"numPag={numero_pagina}|tamPag=100",
    }

    try:
        response = requests.get(URL_API, params=query_params, headers=_headers(), timeout=15)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        st.error("La consulta a Siesa tardó demasiado en responder (timeout).")
        return None
    except requests.exceptions.HTTPError:
        st.error(f"Error al conectarse a Siesa. Código de estado: {response.status_code}")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"No se pudo establecer la conexión con el servidor: {e}")
        return None

    payload = response.json()
    if payload.get("codigo") != 0:
        st.error(f"Siesa respondió con error: {payload.get('mensaje', 'sin mensaje')}")
        return None

    return payload


def cargar_pagina(numero_pagina: int) -> pd.DataFrame:
    """Trae una página y la devuelve como DataFrame normalizado."""
    payload = _fetch_pagina_raw(numero_pagina)
    if payload is None:
        return pd.DataFrame()

    datos = payload.get("detalle", {}).get("Datos")
    if not datos:
        return pd.DataFrame()

    return _normalizar(pd.DataFrame(datos))


def obtener_metadata() -> dict:
    """Lee tamaño_página / total_páginas / total_registros desde la página 1.
    Se reutiliza el cache de _fetch_pagina_raw, así que no implica una llamada extra."""
    payload = _fetch_pagina_raw(1)
    if payload is None:
        return {"total_páginas": TOTAL_PAGINAS_FALLBACK, "total_registros": None}

    detalle = payload.get("detalle", {})
    return {
        "total_páginas": detalle.get("total_páginas", TOTAL_PAGINAS_FALLBACK),
        "total_registros": detalle.get("total_registros"),
    }


@st.cache_data(ttl=300, show_spinner=False)
def cargar_todas_las_paginas(max_paginas: int) -> pd.DataFrame:
    """Trae todas las páginas y las concatena. Se usa bajo demanda para
    búsquedas de historial que deben cubrir a un cliente en cualquier página."""
    bloques = []
    for pagina in range(1, max_paginas + 1):
        df_pagina = cargar_pagina(pagina)
        if df_pagina.empty:
            break
        bloques.append(df_pagina)

    if not bloques:
        return pd.DataFrame()
    return pd.concat(bloques, ignore_index=True)


def emails_para_mailto(valor_crudo: str) -> str:
    """La API separa varios correos con ';', pero el estándar mailto: usa ','."""
    correos = [c.strip() for c in str(valor_crudo).split(';') if c.strip()]
    return ",".join(correos)


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------

metadata = obtener_metadata()
total_paginas = metadata["total_páginas"]

st.markdown("### Navegación de Registros")
if metadata["total_registros"] is not None:
    st.caption(f"Total de registros en Siesa: {metadata['total_registros']:,}")

col_pag, col_filtro, col_kpi_cant, col_kpi_cop, col_kpi_usd = st.columns([1, 1.5, 1, 1.2, 1.2])

with col_pag:
    pagina_actual = st.selectbox(
        "Ver Página",
        options=list(range(1, total_paginas + 1)),
        index=0,
        key="selector_pagina",
    )

with col_filtro:
    filtro_estado = st.selectbox(
        "Filtrar por Estado",
        ["Todos", "Sin Facturar", "Facturadas", "Anuladas"],
    )

with st.spinner(f"Cargando página {pagina_actual}..."):
    df = cargar_pagina(pagina_actual)

if df.empty:
    st.warning(f"⚠️ No hay datos devueltos por Siesa para la Página {pagina_actual}.")
    st.stop()

df_filtrado = df.copy()
if filtro_estado != "Todos":
    mapa_filtro = {"Sin Facturar": "Sin Facturar", "Facturadas": "Facturada", "Anuladas": "Anulada"}
    df_filtrado = df[df['Estado'] == mapa_filtro[filtro_estado]]

df_sin_facturar = df[df['Estado'] == "Sin Facturar"]

with col_kpi_cant:
    st.metric(label="Cant. Sin Facturar", value=len(df_sin_facturar))

with col_kpi_cop:
    valor_cop = df_sin_facturar[df_sin_facturar['f310_id_moneda_docto'] == 'COP']['f310_vlr_neto'].sum()
    valor_cop = 0 if pd.isna(valor_cop) else valor_cop
    st.metric(label="Sin Facturar (COP)", value=f"${valor_cop:,.2f}")

with col_kpi_usd:
    valor_usd = df_sin_facturar[df_sin_facturar['f310_id_moneda_docto'] == 'USD']['f310_vlr_neto'].sum()
    valor_usd = 0 if pd.isna(valor_usd) else valor_usd
    st.metric(label="Sin Facturar (USD)", value=f"${valor_usd:,.2f}")

st.markdown("---")

# Tabla principal
st.subheader(f"Listado de prefacturas - Página {pagina_actual} de {total_paginas}")

tabla = df_filtrado[list(COLUMNAS_VISIBLES.keys())].rename(columns=COLUMNAS_VISIBLES)
st.dataframe(
    tabla,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Valor": st.column_config.NumberColumn("Valor", format="$ %,.2f"),
        "Fecha Facturacion": st.column_config.DateColumn("Fecha Facturacion", format="DD/MM/YYYY"),
    },
)

st.markdown("---")

# ---------------------------------------------------------------------------
# Acciones
# ---------------------------------------------------------------------------
st.subheader("Acciones Rápidas")

prefactura_seleccionada = st.selectbox(
    "Seleccionar una PF para gestionar",
    df_filtrado['prefactura'].unique(),
    key="pf_seleccionada",
)

if prefactura_seleccionada:
    registro = df[df['prefactura'] == prefactura_seleccionada].iloc[0]

    col1, col2 = st.columns(2)

    with col1:
        st.info(f"**Gestión para:** {registro['f200_razon_social']} ({prefactura_seleccionada})")

        destinatario_crudo = registro.get('f015_email')

        if pd.isna(destinatario_crudo) or not str(destinatario_crudo).strip():
            st.warning("⚠️ Este cliente no tiene un email registrado. No se puede generar el correo.")
        else:
            destinatarios = emails_para_mailto(destinatario_crudo)
            asunto = f"Prefactura {registro['prefactura']} pendiente de OC - {registro['f200_razon_social']}"
            cuerpo = (
                f"Hola {registro['f200_razon_social']},\n\n"
                f"Adjuntamos la prefactura {registro['prefactura']} por valor de "
                f"${registro['f310_vlr_neto']:,.2f} para su revisión.\n\n"
                f"Quedamos atentos a la Orden de Compra para proceder con la facturación.\n\n"
                f"Saludos cordiales."
            )
            mailto_url = f"mailto:{destinatarios}?subject={asunto}&body={cuerpo}"
            st.link_button("✉️ Enviar Correo al Cliente", mailto_url)
            st.caption(f"Destinatarios: {destinatarios}")

    with col2:
        buscar_todas = st.checkbox(
            "Buscar en TODAS las páginas",
            value=False,
            help="Por defecto solo busca en la página actual. Actívalo para ver "
                 "el historial completo del cliente sin importar en qué página esté.",
        )

        if st.button("Ver Historial"):
            if buscar_todas:
                with st.spinner("Consultando todas las páginas, puede tardar unos segundos..."):
                    df_completo = cargar_todas_las_paginas(total_paginas)
                fuente = df_completo if not df_completo.empty else df
                alcance = "todas las páginas"
            else:
                fuente = df
                alcance = f"página {pagina_actual}"

            historial_cliente = fuente[fuente['f200_nit'] == registro['f200_nit']]

            st.write(f"### Historial para: {registro['f200_razon_social']} ({alcance})")
            if historial_cliente.empty:
                st.info("No se encontraron más registros para este cliente en el alcance seleccionado.")
            else:
                tabla_hist = historial_cliente[list(COLUMNAS_VISIBLES.keys())].rename(columns=COLUMNAS_VISIBLES)
                st.dataframe(
                    tabla_hist,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Valor": st.column_config.NumberColumn("Valor", format="$ %,.2f"),
                        "Fecha Facturacion": st.column_config.DateColumn("Fecha Facturacion", format="DD/MM/YYYY"),
                    },
                )
