import streamlit as st

import db
import auth
from config import CAMPOS_CLIENTE_SIESA

st.set_page_config(page_title="Ficha Cliente", layout="wide")

auth.exigir_sesion()
auth.mostrar_barra_usuario()

nit = st.session_state.get("cliente_nit")

if not nit:
    st.info("No hay ningún cliente seleccionado todavía.")
    st.page_link("app.py", label="⬅️ Volver al listado", icon="⬅️")
    st.stop()

cliente = db.obtener_cliente(nit)

if cliente is None:
    st.warning(
        "Este cliente todavía no está en el catálogo local. "
        "Sincroniza primero desde la vista principal."
    )
    st.page_link("app.py", label="⬅️ Volver al listado", icon="⬅️")
    st.stop()

col_volver, col_historial = st.columns([1, 1])
with col_volver:
    st.page_link("app.py", label="⬅️ Volver al listado", icon="⬅️")
with col_historial:
    st.page_link("pages/1_Historial_Cliente.py", label="📄 Ver historial de prefacturas", icon="📄")

st.markdown(f"### Ficha de cliente: {cliente['razon_social']}")
st.caption(f"NIT: {cliente['nit']}")

st.markdown("---")

# --- Datos que vienen de Siesa (solo lectura) -------------------------------
st.subheader("Datos de Siesa")
st.caption("Estos campos se actualizan automáticamente en cada sincronización y no son editables aquí.")

col1, col2, col3 = st.columns(3)
campos_col = list(CAMPOS_CLIENTE_SIESA.items())
columnas = [col1, col2, col3]
for i, (clave, etiqueta) in enumerate(campos_col):
    with columnas[i % 3]:
        valor = cliente.get(clave) or "—"
        if clave == "email" and valor != "—":
            valor = ", ".join(c.strip() for c in valor.split(";") if c.strip())
        st.text_input(etiqueta, value=valor, disabled=True, key=f"siesa_{clave}")

if cliente.get("actualizado_en_siesa"):
    st.caption(f"Última actualización desde Siesa: {cliente['actualizado_en_siesa'][:19].replace('T', ' ')}")

st.markdown("---")

# --- Campos manuales (editables, nunca los toca la sincronización) --------
st.subheader("Información adicional")
st.caption("Estos campos los administras tú. Sincronizar con Siesa nunca los sobreescribe.")

with st.form("form_datos_manuales"):
    tipo_oc = st.text_input(
        "Tipo de OC",
        value=cliente.get("tipo_oc") or "",
        placeholder="Ej: Física, Digital, Portal, Correo...",
    )
    observaciones = st.text_area(
        "Observaciones",
        value=cliente.get("observaciones") or "",
        placeholder="Notas internas sobre este cliente...",
        height=120,
    )
    links = st.text_area(
        "Links del cliente",
        value=cliente.get("links") or "",
        placeholder="Un link por línea. Ej:\nhttps://portal.cliente.com\nhttps://drive.google.com/...",
        height=100,
    )

    guardado = st.form_submit_button("💾 Guardar cambios", use_container_width=True)

    if guardado:
        db.actualizar_datos_cliente(nit, tipo_oc.strip(), observaciones.strip(), links.strip())
        st.success("Información guardada.")
        st.rerun()

if cliente.get("actualizado_en_usuario"):
    st.caption(f"Última edición manual: {cliente['actualizado_en_usuario'][:19].replace('T', ' ')}")

# Mostrar los links ya guardados como enlaces clicables, no solo como texto
links_guardados = (cliente.get("links") or "").strip()
if links_guardados:
    st.markdown("**Accesos rápidos:**")
    for link in links_guardados.splitlines():
        link = link.strip()
        if link:
            st.markdown(f"- [{link}]({link})")
