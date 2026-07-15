import json

import streamlit as st
import pandas as pd

import db
import search
import auth
import reportes
import gmail_client
import backup
from sync import sincronizar
from siesa_client import SiesaError
from config import (
    COLUMNAS_DISPONIBLES, COLUMNAS_DEFAULT, COLUMNAS_MONEDA, COLUMNAS_FECHA,
    agrupar_columnas_por_categoria,
)

st.set_page_config(page_title="Control Prefacturas", layout="wide")

auth.mostrar_login()  # detiene aquí si todavía no hay sesión iniciada
auth.mostrar_barra_usuario()

COLUMNAS_POR_CATEGORIA = agrupar_columnas_por_categoria()

# ---------------------------------------------------------------------------
# Preferencias del usuario: se cargan una sola vez por sesión (justo
# después del login) y se guardan de nuevo cada vez que cambian más abajo.
# Así, la próxima vez que este usuario inicie sesión, ve las mismas
# columnas y el mismo filtro de estado que dejó la última vez.
# ---------------------------------------------------------------------------
if "preferencias_cargadas" not in st.session_state:
    preferencias = db.obtener_preferencias(st.session_state["username"])
    if preferencias and preferencias.get("columnas_json"):
        columnas_guardadas = [
            c for c in json.loads(preferencias["columnas_json"])
            if c in COLUMNAS_DISPONIBLES
        ]
        for categoria, claves in COLUMNAS_POR_CATEGORIA.items():
            st.session_state[f"cols_{categoria}"] = [c for c in claves if c in columnas_guardadas]
        st.session_state["orden_columnas"] = columnas_guardadas
        st.session_state["filtro_estado_guardado"] = preferencias.get("filtro_estado") or "Todos"
        st.session_state["anios_guardados"] = json.loads(preferencias.get("anios_json") or "[]")
        st.session_state["meses_guardados"] = json.loads(preferencias.get("meses_json") or "[]")
    else:
        st.session_state["filtro_estado_guardado"] = "Todos"
        st.session_state["anios_guardados"] = []
        st.session_state["meses_guardados"] = []
    st.session_state["preferencias_cargadas"] = True

# ---------------------------------------------------------------------------
# Sincronización con Siesa (vista principal -- único punto para actualizar)
# ---------------------------------------------------------------------------
st.markdown("### Control de Prefacturas")

meta = db.obtener_metadata_sync()

col_sync_info, col_sync_boton = st.columns([3, 1])

with col_sync_info:
    if meta["ultima_sincronizacion"]:
        st.caption(f"Última sincronización: {meta['ultima_sincronizacion'][:19].replace('T', ' ')}")
        st.caption(f"Registros en base local: {meta['total_registros']:,}")
        respaldos = backup.listar_backups()
        if respaldos:
            st.caption(f"Último respaldo: {respaldos[0]['modificado_en'].strftime('%Y-%m-%d %H:%M')}")
    else:
        st.warning("Aún no se ha sincronizado ningún dato.")

with col_sync_boton:
    if st.button("🔄 Sincronizar ahora", use_container_width=True):
        with st.spinner("Consultando Siesa y actualizando la base local..."):
            try:
                resumen = sincronizar()
                st.success(f"Listo: {resumen['total_registros']} registros actualizados.")
                st.rerun()
            except SiesaError as e:
                st.error(str(e))

# ---------------------------------------------------------------------------
# Datos: prefacturas + datos de cliente (dirección, país, tipo de OC,
# observaciones, links) unidos por NIT, para poder mostrar cualquiera
# de los dos orígenes en el mismo listado.
# ---------------------------------------------------------------------------
df = db.obtener_todas()

if df.empty:
    st.info("👋 Todavía no hay datos locales. Da clic en **Sincronizar ahora** arriba para traerlos de Siesa.")
    st.stop()

clientes_df = db.obtener_todos_los_clientes()
if not clientes_df.empty:
    columnas_cliente_extra = clientes_df[['nit', 'direccion', 'pais', 'tipo_oc', 'observaciones', 'links']]
    df = df.merge(columnas_cliente_extra, left_on='f200_nit', right_on='nit', how='left')
    df = df.drop(columns=['nit'])

st.markdown("---")

# ---------------------------------------------------------------------------
# Panel único de filtros y búsqueda: todo lo que afecta qué se ve en la
# tabla vive dentro de un solo contenedor con borde, justo encima de ella.
# Antes cada control (buscador, filtro de estado, columnas) estaba
# separado por su propio "---", lo que se sentía como funciones sueltas
# en vez de un panel de control enfocado en la tabla de abajo.
# ---------------------------------------------------------------------------
with st.container(border=True):
    col_kpi_cant, col_kpi_val = st.columns(2)
    # Los KPIs siempre reflejan el TOTAL real (los 1,200+ registros), sin
    # importar el filtro de la tabla ni las columnas elegidas.
    df_sin_facturar = df[df['estado'] == "Sin Facturar"]
    with col_kpi_cant:
        st.metric("Cant. Sin Facturar (total)", len(df_sin_facturar))
    with col_kpi_val:
        valor_total = df_sin_facturar['f310_vlr_neto'].sum()
        st.metric("Valor Total Sin Facturar", f"${valor_total:,.2f} COP")

    st.divider()

    query_busqueda = st.text_input(
        "🔍 Buscar por cliente, NIT, prefactura o factura",
        placeholder="Ej: Automata, 812002995, OSV-1185... (tolera tildes y pequeños errores de tipeo)",
    )

    col_filtro, col_anio, col_mes = st.columns([1.3, 1, 1.7])

    with col_filtro:
        st.caption("Filtrar por Estado")
        filtro_estado = st.segmented_control(
            "Filtrar por Estado",
            ["Todos", "Sin Facturar", "Facturadas", "Anuladas"],
            default=st.session_state.get("filtro_estado_guardado", "Todos"),
            label_visibility="collapsed",
        )
        if filtro_estado is None:  # el usuario deseleccionó el botón activo
            filtro_estado = "Todos"

    # Filtro por año/mes de "Fecha Creación" -- vacío significa "todos"
    # (no se obliga a marcar los 12 meses o todos los años para ver todo).
    anios_disponibles = sorted(
        {int(a) for a in df['fecha_creacion'].dt.year.dropna().unique()},
        reverse=True,
    )
    with col_anio:
        st.caption("Año (Fecha Creación)")
        anios_elegidos = st.multiselect(
            "Año (Fecha Creación)",
            options=anios_disponibles,
            default=[a for a in st.session_state.get("anios_guardados", []) if a in anios_disponibles],
            label_visibility="collapsed",
            placeholder="Todos los años",
        )
    with col_mes:
        st.caption("Mes (Fecha Creación)")
        meses_elegidos_nombres = st.multiselect(
            "Mes (Fecha Creación)",
            options=reportes.MESES,
            default=[m for m in st.session_state.get("meses_guardados", []) if m in reportes.MESES],
            label_visibility="collapsed",
            placeholder="Todos los meses",
        )

    # -----------------------------------------------------------------------
    # Selector de columnas: el usuario decide qué ver, mezclando datos de la
    # prefactura (Siesa), datos de contacto del cliente (Siesa) y los campos
    # manuales (Tipo de OC, Observaciones, Links).
    #
    # Se muestra separado en un multiselect POR CATEGORÍA (en vez de uno solo
    # con "Categoría · Etiqueta" en cada opción) porque ese formato combinado
    # hacía las pastillas demasiado largas para leerse.
    #
    # El orden final de las columnas en la tabla respeta el orden en que el
    # usuario las va seleccionando (sin importar de qué categoría vengan).
    # Como son 3 widgets independientes, se mantiene un "orden_columnas" en
    # session_state que se actualiza cada corrida: se quitan las que ya no
    # están marcadas (conservando el orden relativo de las que quedan) y se
    # agregan al final las que se acaban de seleccionar.
    # -----------------------------------------------------------------------

    def _restaurar_columnas_por_defecto():
        for categoria, claves in COLUMNAS_POR_CATEGORIA.items():
            st.session_state[f"cols_{categoria}"] = [c for c in claves if c in COLUMNAS_DEFAULT]
        st.session_state["orden_columnas"] = list(COLUMNAS_DEFAULT)

    if "orden_columnas" not in st.session_state:
        _restaurar_columnas_por_defecto()

    with st.expander("⚙️ Personalizar columnas del listado", expanded=False):
        st.button("Restaurar columnas por defecto", on_click=_restaurar_columnas_por_defecto)
        st.caption("Las columnas aparecen en la tabla en el orden en que las vayas seleccionando.")

        columnas_ui = st.columns(len(COLUMNAS_POR_CATEGORIA))
        for col_ui, (categoria, claves) in zip(columnas_ui, COLUMNAS_POR_CATEGORIA.items()):
            with col_ui:
                st.caption(f"**{categoria}**")
                st.multiselect(
                    categoria,
                    options=claves,
                    format_func=lambda k: COLUMNAS_DISPONIBLES[k][0],
                    key=f"cols_{categoria}",
                    label_visibility="collapsed",
                )

    # Recalculamos el orden global DESPUÉS de que los 3 multiselects ya
    # actualizaron su propio session_state en esta corrida del script.
    seleccion_actual_plana = set()
    for categoria in COLUMNAS_POR_CATEGORIA:
        seleccion_actual_plana.update(st.session_state.get(f"cols_{categoria}", []))

    orden_previo = st.session_state.get("orden_columnas", [])
    orden_actualizado = [c for c in orden_previo if c in seleccion_actual_plana]  # quita las deseleccionadas

    ya_en_orden = set(orden_actualizado)
    for categoria in COLUMNAS_POR_CATEGORIA:
        for clave in st.session_state.get(f"cols_{categoria}", []):
            if clave not in ya_en_orden:
                orden_actualizado.append(clave)  # agrega al final las recién marcadas
                ya_en_orden.add(clave)

    st.session_state["orden_columnas"] = orden_actualizado

    if not orden_actualizado:
        st.caption("No seleccionaste ninguna columna -- mostrando las columnas por defecto.")

# Guarda las preferencias de este usuario (columnas + filtros) cada vez
# que cambian, para que la próxima sesión arranque igual que como la dejó.
db.guardar_preferencias(
    st.session_state["username"],
    json.dumps(orden_actualizado),
    filtro_estado,
    json.dumps(anios_elegidos),
    json.dumps(meses_elegidos_nombres),
)

columnas_activas = orden_actualizado or list(COLUMNAS_DEFAULT)

df_filtrado = search.buscar(df, query_busqueda)

if filtro_estado != "Todos":
    mapa_filtro = {"Sin Facturar": "Sin Facturar", "Facturadas": "Facturada", "Anuladas": "Anulada"}
    df_filtrado = df_filtrado[df_filtrado['estado'] == mapa_filtro[filtro_estado]]

if anios_elegidos:
    df_filtrado = df_filtrado[df_filtrado['fecha_creacion'].dt.year.isin(anios_elegidos)]
if meses_elegidos_nombres:
    meses_num = [reportes.MESES.index(m) + 1 for m in meses_elegidos_nombres]
    df_filtrado = df_filtrado[df_filtrado['fecha_creacion'].dt.month.isin(meses_num)]

df_filtrado = df_filtrado.reset_index(drop=True)

st.subheader(f"Listado de prefacturas ({len(df_filtrado):,} registros)")
st.caption("Selecciona una fila para ver el historial completo de ese cliente.")

if query_busqueda.strip() and df_filtrado.empty:
    st.warning(
        f"No se encontraron coincidencias para \"{query_busqueda}\". "
        "Intenta con menos palabras o revisa el NIT/prefactura."
    )

# Ya vienen en el orden en que el usuario las seleccionó (ver lógica de
# orden_columnas más arriba) -- no se vuelve a reordenar aquí.
columnas_a_mostrar = columnas_activas
etiquetas = {c: COLUMNAS_DISPONIBLES[c][0] for c in columnas_a_mostrar}

tabla = df_filtrado[columnas_a_mostrar].copy()

# El email puede traer varios correos separados por ';' -- se muestra
# separado por comas para que sea legible en la tabla.
if 'f015_email' in tabla.columns:
    tabla['f015_email'] = tabla['f015_email'].apply(
        lambda v: ", ".join(c.strip() for c in str(v).split(';') if c.strip()) if pd.notna(v) else v
    )

tabla = tabla.rename(columns=etiquetas)

# column_config dinámico: moneda para las columnas de valor, fecha para
# las de fecha, según lo que el usuario haya elegido mostrar.
column_config = {}
for clave in columnas_a_mostrar:
    etiqueta = etiquetas[clave]
    if clave in COLUMNAS_MONEDA:
        column_config[etiqueta] = st.column_config.NumberColumn(etiqueta, format="$ %,.2f")
    elif clave in COLUMNAS_FECHA:
        column_config[etiqueta] = st.column_config.DateColumn(etiqueta, format="DD/MM/YYYY")

evento = st.dataframe(
    tabla,
    use_container_width=True,
    hide_index=True,
    on_select="rerun",
    selection_mode="single-row",
    column_config=column_config,
)

filas_seleccionadas = evento.selection.rows if evento and evento.selection else []

if filas_seleccionadas:
    fila = df_filtrado.iloc[filas_seleccionadas[0]]
    st.session_state["fila_sel_nit"] = fila["f200_nit"]
    st.session_state["fila_sel_razon_social"] = fila["f200_razon_social"]
    st.session_state["fila_sel_prefactura"] = fila["prefactura"]
    st.session_state["fila_sel_email"] = fila.get("f015_email")
    st.session_state["fila_sel_valor"] = fila.get("f310_vlr_neto")


def _parsear_destinatarios(valor_crudo):
    """La API separa varios correos con ';'. El primero va en 'Para',
    el resto en 'CC' (según se definió para esta funcionalidad)."""
    if pd.isna(valor_crudo) or not str(valor_crudo).strip():
        return None, []
    correos = [c.strip() for c in str(valor_crudo).split(';') if c.strip()]
    if not correos:
        return None, []
    return correos[0], correos[1:]


# ---------------------------------------------------------------------------
# Panel de acciones sobre la fila seleccionada: en vez de navegar directo
# al historial (como antes), ahora se muestra un panel con dos acciones,
# ya que seleccionar una fila puede llevar a dos lugares distintos:
# ver el historial completo del cliente, o enviar/reenviar un correo
# sobre esa prefactura puntual.
# ---------------------------------------------------------------------------
if st.session_state.get("fila_sel_prefactura"):
    prefactura_sel = st.session_state["fila_sel_prefactura"]
    razon_social_sel = st.session_state["fila_sel_razon_social"]
    valor_sel = st.session_state.get("fila_sel_valor") or 0

    with st.container(border=True):
        st.markdown(f"**{razon_social_sel}** -- Prefactura `{prefactura_sel}`")

        envios_previos = db.obtener_envios_por_prefactura(prefactura_sel)
        es_reenvio = bool(envios_previos)

        col_hist, col_correo = st.columns(2)
        with col_hist:
            if st.button("📄 Ver historial completo", use_container_width=True):
                st.session_state["cliente_nit"] = st.session_state["fila_sel_nit"]
                st.session_state["cliente_razon_social"] = razon_social_sel
                st.switch_page("pages/1_Historial_Cliente.py")
        with col_correo:
            etiqueta_boton = "🔁 Reenviar correo" if es_reenvio else "✉️ Enviar correo"
            if st.button(etiqueta_boton, use_container_width=True):
                st.session_state["mostrar_form_correo"] = not st.session_state.get("mostrar_form_correo", False)

        if envios_previos:
            ultimo = envios_previos[-1]
            texto_adjuntos = f" · Adjuntos: {ultimo['adjuntos']}" if ultimo.get('adjuntos') else ""
            st.caption(
                f"Último envío: {ultimo['enviado_en'][:19].replace('T', ' ')} "
                f"por {ultimo['username']} a {ultimo['destinatario_to']}"
                f"{texto_adjuntos} "
                f"({len(envios_previos)} envío(s) en total)"
            )

        if st.session_state.get("mostrar_form_correo"):
            destinatario_to, destinatarios_cc = _parsear_destinatarios(st.session_state.get("fila_sel_email"))

            if destinatario_to is None:
                st.warning("Este cliente no tiene ningún correo registrado. No se puede enviar.")
            else:
                st.caption(
                    f"Para: {destinatario_to}"
                    + (f" · CC: {', '.join(destinatarios_cc)}" if destinatarios_cc else "")
                )

                asunto_base = f"Prefactura {prefactura_sel} pendiente de OC - {razon_social_sel}"
                cuerpo_default = (
                    f"Hola {razon_social_sel},\n\n"
                    f"Adjuntamos la prefactura {prefactura_sel} por valor de "
                    f"${valor_sel:,.2f} para su revisión.\n\n"
                    f"Quedamos atentos a la Orden de Compra para proceder con la facturación.\n\n"
                    f"Saludos cordiales."
                )

                if es_reenvio:
                    # IMPORTANTE: Gmail exige que el asunto sea IDÉNTICO al
                    # del hilo original cuando se envía con threadId -- si
                    # no coincide exactamente (ej. agregando "Re: "), Gmail
                    # crea un hilo nuevo en silencio en vez de continuar el
                    # existente. Por eso se reusa el asunto tal cual quedó
                    # en el primer envío, y no se deja editar aquí.
                    asunto_default = envios_previos[0]["asunto"]
                    st.text_input("Asunto", value=asunto_default, disabled=True)
                    st.caption("El asunto no se puede editar en un reenvío, para mantenerlo en el mismo hilo de correo.")
                    asunto = asunto_default
                else:
                    asunto = st.text_input("Asunto", value=asunto_base)

                with st.form("form_enviar_correo"):
                    cuerpo = st.text_area("Mensaje", value=cuerpo_default, height=160)
                    archivos_subidos = st.file_uploader(
                        "Adjuntos (opcional)",
                        accept_multiple_files=True,
                        help="Máximo ~20 MB en total entre todos los archivos.",
                    )
                    enviar = st.form_submit_button("Enviar", use_container_width=True)

                if enviar:
                    adjuntos = [
                        {
                            "nombre": archivo.name,
                            "datos": archivo.getvalue(),
                            "tipo_mime": archivo.type,
                        }
                        for archivo in (archivos_subidos or [])
                    ]
                    try:
                        with st.spinner("Enviando correo..."):
                            resultado = gmail_client.enviar_correo(
                                username=st.session_state["username"],
                                destinatario_to=destinatario_to,
                                destinatarios_cc=destinatarios_cc,
                                asunto=asunto,
                                cuerpo=cuerpo,
                                prefactura=prefactura_sel,
                                adjuntos=adjuntos,
                            )
                        db.registrar_envio_correo(
                            prefactura=prefactura_sel,
                            username=st.session_state["username"],
                            destinatario_to=destinatario_to,
                            destinatarios_cc=", ".join(destinatarios_cc),
                            asunto=asunto,
                            adjuntos=", ".join(a["nombre"] for a in adjuntos),
                            message_id_rfc822=resultado["message_id_rfc822"],
                            gmail_message_id=resultado["gmail_message_id"],
                            gmail_thread_id=resultado["gmail_thread_id"],
                            gmail_account_usado=resultado["cuenta_gmail"],
                        )
                        st.session_state["mostrar_form_correo"] = False
                        st.success(f"Correo enviado a {destinatario_to}.")
                        st.rerun()
                    except gmail_client.GmailNoConectado as e:
                        st.error(
                            f"{e} Corre `python conectar_gmail.py` en tu terminal (una sola vez) "
                            "para conectar tu cuenta."
                        )
                    except gmail_client.AdjuntosDemasiadoGrandes as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"No se pudo enviar el correo: {e}")
