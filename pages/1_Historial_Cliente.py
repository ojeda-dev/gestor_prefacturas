import streamlit as st
import altair as alt

import db
import reportes
import auth
from config import COLUMNAS_VISIBLES

st.set_page_config(page_title="Historial Cliente", layout="wide")

auth.exigir_sesion()
auth.mostrar_barra_usuario()

nit = st.session_state.get("cliente_nit")
razon_social = st.session_state.get("cliente_razon_social")

if not nit:
    st.info("No hay ningún cliente seleccionado todavía.")
    st.page_link("app.py", label="⬅️ Volver al listado", icon="⬅️")
    st.stop()

st.page_link("app.py", label="⬅️ Volver al listado", icon="⬅️")

col_titulo, col_ficha = st.columns([3, 1])
with col_titulo:
    st.markdown(f"### Historial de: {razon_social}")
    st.caption(f"NIT: {nit}")
with col_ficha:
    st.page_link("pages/2_Ficha_Cliente.py", label="📇 Ver / Editar ficha del cliente", icon="📇")

# Esta consulta va directo contra SQLite (índice sobre f200_nit), por eso
# es instantánea sin importar cuántas "páginas" hubiera tenido el cliente
# en la API original -- ese concepto ya no existe para el usuario final.
historial = db.obtener_historial_por_nit(nit)

if historial.empty:
    st.warning("No se encontraron registros para este cliente.")
    st.stop()

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total prefacturas", len(historial))
with col2:
    pendientes = historial[historial['estado'] == "Sin Facturar"]
    st.metric("Pendientes", len(pendientes))
with col3:
    valor_pendiente = pendientes['f310_vlr_neto'].sum()
    st.metric("Valor pendiente", f"${valor_pendiente:,.2f} COP")

st.markdown("---")

# ---------------------------------------------------------------------------
# Gráfico: valor facturado por mes, con filtros de año y mes
# ---------------------------------------------------------------------------
st.subheader("📊 Valor Facturado por Mes")

facturadas_hist = historial[historial['fecha_facturacion'].notna()]

if facturadas_hist.empty:
    st.info("Este cliente todavía no tiene prefacturas facturadas para graficar.")
else:
    anios_disponibles = sorted(facturadas_hist['fecha_facturacion'].dt.year.unique(), reverse=True)

    col_f_anio, col_f_mes = st.columns([1, 2])
    with col_f_anio:
        anios_elegidos = st.multiselect(
            "Año",
            options=anios_disponibles,
            default=anios_disponibles,
        )
    with col_f_mes:
        meses_elegidos_nombres = st.multiselect(
            "Mes",
            options=reportes.MESES,
            default=reportes.MESES,
        )

    meses_elegidos_num = [reportes.MESES.index(m) + 1 for m in meses_elegidos_nombres]

    tabla_grafico = reportes.valor_facturado_por_mes(
        historial,
        anios_seleccionados=anios_elegidos or None,
        meses_seleccionados=meses_elegidos_num or None,
    )

    if tabla_grafico.empty:
        st.info("No hay valor facturado para los filtros seleccionados.")
    else:
        # bar_chart ordena el eje alfabéticamente (Abril, Agosto, Diciembre...),
        # así que usamos altair_chart directamente para forzar Enero -> Diciembre.
        datos_largo = tabla_grafico.reset_index().melt(
            id_vars='Mes', var_name='Año', value_name='Valor'
        )

        grafico = (
            alt.Chart(datos_largo)
            .mark_bar()
            .encode(
                x=alt.X('Mes:N', sort=reportes.MESES, title=None),
                xOffset=alt.XOffset('Año:N'),
                y=alt.Y('Valor:Q', title='Valor Facturado'),
                color=alt.Color('Año:N', title='Año'),
                tooltip=[
                    alt.Tooltip('Mes:N'),
                    alt.Tooltip('Año:N'),
                    alt.Tooltip('Valor:Q', format=',.2f', title='Valor'),
                ],
            )
            .properties(height=350)
        )
        st.altair_chart(grafico, use_container_width=True)

        with st.expander("Ver valores exactos"):
            st.dataframe(
                tabla_grafico.style.format("$ {:,.2f}"),
                use_container_width=True,
            )

st.markdown("---")

tabla_historial = historial[list(COLUMNAS_VISIBLES.keys())].rename(columns=COLUMNAS_VISIBLES)

st.dataframe(
    tabla_historial,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Valor": st.column_config.NumberColumn("Valor", format="$ %,.2f"),
        "Fecha Facturacion": st.column_config.DateColumn("Fecha Facturacion", format="DD/MM/YYYY"),
    },
)
