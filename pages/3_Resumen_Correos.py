import pandas as pd
import streamlit as st

import auth
import db

st.set_page_config(page_title="Resumen de Correos", layout="wide")

auth.exigir_sesion()
auth.mostrar_barra_usuario()

st.page_link("app.py", label="⬅️ Volver al listado", icon="⬅️")
st.markdown("### 📧 Resumen de Correos Enviados")

envios = db.obtener_todos_los_envios()

if envios.empty:
    st.info("Todavía no se ha enviado ningún correo desde la app.")
    st.stop()

prefacturas = db.obtener_todas()

# ---------------------------------------------------------------------------
# KPIs generales
# ---------------------------------------------------------------------------
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total de correos enviados", len(envios))
with col2:
    hace_7_dias = pd.Timestamp.now() - pd.Timedelta(days=7)
    enviados_ultima_semana = envios[envios['enviado_en'] >= hace_7_dias]
    st.metric("Enviados en los últimos 7 días", len(enviados_ultima_semana))
with col3:
    st.metric("Prefacturas contactadas al menos una vez", envios['prefactura'].nunique())

st.markdown("---")

# ---------------------------------------------------------------------------
# Correos por usuario
# ---------------------------------------------------------------------------
st.subheader("Correos enviados por usuario")
por_usuario = (
    envios.groupby('username').size().reset_index(name='Cantidad')
    .sort_values('Cantidad', ascending=False).set_index('username')
)
st.bar_chart(por_usuario)

st.markdown("---")

# ---------------------------------------------------------------------------
# Prefacturas sin facturar que nunca han recibido correo -- la vista más
# accionable: a quién todavía no se le ha escrito.
# ---------------------------------------------------------------------------
st.subheader("⚠️ Sin Facturar y sin ningún correo enviado")

if not prefacturas.empty:
    sin_facturar = prefacturas[prefacturas['estado'] == "Sin Facturar"]
    prefacturas_contactadas = set(envios['prefactura'].unique())
    nunca_contactadas = sin_facturar[~sin_facturar['prefactura'].isin(prefacturas_contactadas)]

    if nunca_contactadas.empty:
        st.success("Todas las prefacturas sin facturar ya recibieron al menos un correo. 🎉")
    else:
        st.caption(f"{len(nunca_contactadas)} prefactura(s) sin facturar que nunca se les ha escrito.")
        tabla_pendientes = nunca_contactadas[
            ['f200_razon_social', 'prefactura', 'f310_vlr_neto', 'fecha_creacion']
        ].rename(columns={
            'f200_razon_social': 'Cliente', 'prefactura': 'Prefactura',
            'f310_vlr_neto': 'Valor', 'fecha_creacion': 'Fecha Creación',
        }).sort_values('Fecha Creación')

        st.dataframe(
            tabla_pendientes,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Valor": st.column_config.NumberColumn("Valor", format="$ %,.2f"),
                "Fecha Creación": st.column_config.DateColumn("Fecha Creación", format="DD/MM/YYYY"),
            },
        )

st.markdown("---")

# ---------------------------------------------------------------------------
# Historial reciente de envíos
# ---------------------------------------------------------------------------
st.subheader("Envíos recientes")

if not prefacturas.empty:
    envios_con_cliente = envios.merge(
        prefacturas[['prefactura', 'f200_razon_social']].drop_duplicates('prefactura'),
        on='prefactura', how='left',
    )
else:
    envios_con_cliente = envios.copy()
    envios_con_cliente['f200_razon_social'] = None

tabla_envios = envios_con_cliente[[
    'enviado_en', 'username', 'f200_razon_social', 'prefactura',
    'destinatario_to', 'destinatarios_cc', 'adjuntos',
]].rename(columns={
    'enviado_en': 'Fecha', 'username': 'Usuario', 'f200_razon_social': 'Cliente',
    'prefactura': 'Prefactura', 'destinatario_to': 'Para', 'destinatarios_cc': 'CC',
    'adjuntos': 'Adjuntos',
})

st.dataframe(
    tabla_envios.head(200),
    use_container_width=True,
    hide_index=True,
    column_config={
        "Fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
    },
)
if len(tabla_envios) > 200:
    st.caption(f"Mostrando los 200 envíos más recientes de {len(tabla_envios)} en total.")
