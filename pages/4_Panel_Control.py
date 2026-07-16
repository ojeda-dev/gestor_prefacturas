from datetime import date

import pandas as pd
import streamlit as st

import auth
import db
from config import COLUMNAS_DISPONIBLES
from gestion import listar_festivos_colombianos

st.set_page_config(page_title="Panel de Control - Gestión", layout="wide")

auth.exigir_sesion()
auth.mostrar_barra_usuario()

st.page_link("app.py", label="⬅️ Volver al listado", icon="⬅️")
st.markdown("### ⚙️ Panel de Control -- Gestión de Prefacturas")

# ---------------------------------------------------------------------------
# Sección 1: Configuración de reglas de gestión
# ---------------------------------------------------------------------------
st.subheader("📋 Configuración de Reglas de Gestión")
st.caption("Los cambios aplican a todos los usuarios de la aplicación.")

config = db.obtener_configuracion_gestion()

with st.form("form_config_gestion"):
    col_plazo, col_recordatorio, col_suspender = st.columns(3)
    with col_plazo:
        plazo = st.number_input(
            "Plazo total (días hábiles)",
            min_value=1, max_value=30,
            value=config['plazo_dias_habiles'],
            help="Número máximo de días hábiles para gestionar una prefactura antes de que se considere vencida.",
        )
    with col_recordatorio:
        recordatorio = st.number_input(
            "Días para Recordatorio",
            min_value=1, max_value=30,
            value=config['dias_recordatorio'],
            help="Días hábiles a partir de los cuales la prefactura cambia a estado 'Recordatorio'.",
        )
    with col_suspender:
        suspender = st.number_input(
            "Días para Suspender",
            min_value=1, max_value=30,
            value=config['dias_suspender'],
            help="Días hábiles a partir de los cuales la prefactura cambia a estado 'Suspender'.",
        )

    guardar = st.form_submit_button("Guardar configuración", use_container_width=True)

    if guardar:
        if recordatorio >= suspender:
            st.error("Los días para 'Recordatorio' deben ser menores a los días para 'Suspender'.")
        else:
            db.guardar_configuracion_gestion(plazo, recordatorio, suspender)
            db.recalcular_todos_los_estados_gestion()
            st.success("Configuración guardada y estados recalculados.")
            st.rerun()

st.markdown("---")

# ---------------------------------------------------------------------------
# Sección 2: Resumen de gestión (KPIs)
# ---------------------------------------------------------------------------
st.subheader("📊 Resumen de Gestión")

gestiones = db.obtener_todas_las_gestiones()

if gestiones.empty:
    st.info("Aún no hay prefacturas en gestión. Los registros se crean automáticamente al enviar el primer correo.")
else:
    total_gestion = len(gestiones)
    pendientes = len(gestiones[gestiones['estado_gestion'] == 'Pendiente'])
    recordatorios = len(gestiones[gestiones['estado_gestion'] == 'Recordatorio'])
    suspendidos = len(gestiones[gestiones['estado_gestion'] == 'Suspender'])

    col_total, col_pend, col_rec, col_susp = st.columns(4)
    with col_total:
        st.metric("Total en gestión", total_gestion)
    with col_pend:
        st.metric("Pendientes", pendientes)
    with col_rec:
        st.metric("Recordatorio", recordatorios)
    with col_susp:
        st.metric("Suspender", suspendidos)

st.markdown("---")

# ---------------------------------------------------------------------------
# Sección 3: Festivos colombianos del año actual
# ---------------------------------------------------------------------------
st.subheader("📅 Festivos Colombianos")

anio_actual = date.today().year
festivos = listar_festivos_colombianos(anio_actual)

with st.expander(f"Festivos {anio_actual} ({len(festivos)} días)", expanded=False):
    for festivo in festivos:
        dia_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][festivo.weekday()]
        st.caption(f"• {festivo.strftime('%d/%m/%Y')} ({dia_semana})")

st.markdown("---")

# ---------------------------------------------------------------------------
# Sección 4: Tabla de prefacturas en gestión
# ---------------------------------------------------------------------------
st.subheader("📋 Prefacturas en Gestión")

if gestiones.empty:
    st.stop()

# Filtro por estado
filtro_estado = st.segmented_control(
    "Filtrar por estado",
    ["Todos", "Pendiente", "Recordatorio", "Suspender"],
    default="Todos",
)

df_gestiones = gestiones.copy()
if filtro_estado != "Todos":
    df_gestiones = df_gestiones[df_gestiones['estado_gestion'] == filtro_estado]

# Cargar prefacturas para traer datos del cliente y valor
prefacturas_df = db.obtener_todas()

if not prefacturas_df.empty:
    df_gestiones = df_gestiones.merge(
        prefacturas_df[['prefactura', 'f200_razon_social', 'f310_vlr_neto', 'f310_id_moneda_docto', 'estado']],
        on='prefactura', how='left',
    )

# Preparar tabla
if not df_gestiones.empty and 'f200_razon_social' in df_gestiones.columns:
    tabla = df_gestiones[[
        'f200_razon_social', 'prefactura', 'f310_vlr_neto', 'f310_id_moneda_docto',
        'estado_gestion', 'fecha_primer_correo', 'dias_habiles_transcurridos',
    ]].copy()

    tabla['fecha_primer_correo'] = pd.to_datetime(tabla['fecha_primer_correo'], errors='coerce')

    tabla = tabla.rename(columns={
        'f200_razon_social': 'Cliente',
        'prefactura': 'Prefactura',
        'f310_vlr_neto': 'Valor',
        'f310_id_moneda_docto': 'Moneda',
        'estado_gestion': 'Estado Gestión',
        'fecha_primer_correo': 'Fecha 1er Correo',
        'dias_habiles_transcurridos': 'Días Hábiles',
    })

    tabla = tabla.sort_values('Días Hábiles', ascending=False)

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Valor": st.column_config.NumberColumn("Valor", format="$ %,.2f"),
            "Fecha 1er Correo": st.column_config.DateColumn("Fecha 1er Correo", format="DD/MM/YYYY"),
        },
    )
else:
    st.warning("No hay datos disponibles para mostrar.")
