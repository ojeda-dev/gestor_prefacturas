"""Autenticación simple para la app (usuario + contraseña).

No es un sistema de nivel empresarial (sin SSO, sin recuperación de
contraseña por correo, sin expiración de sesión) -- pero es apropiado
para una herramienta interna de pocos usuarios conocidos. Lo importante
que SÍ se respeta: las contraseñas nunca se guardan ni se comparan en
texto plano.
"""
import hashlib
import secrets

import streamlit as st

ITERACIONES_HASH = 200_000


def _hash_password(password: str, sal: str) -> str:
    return hashlib.pbkdf2_hmac(
        'sha256', password.encode('utf-8'), sal.encode('utf-8'), ITERACIONES_HASH
    ).hex()


def hashear_password_nueva(password: str) -> tuple[str, str]:
    """Genera una sal nueva y devuelve (hash, sal) para guardar."""
    sal = secrets.token_hex(16)
    return _hash_password(password, sal), sal


def verificar_password(password: str, sal: str, hash_guardado: str) -> bool:
    """Compara en tiempo constante (evita timing attacks triviales)."""
    return secrets.compare_digest(_hash_password(password, sal), hash_guardado)


def exigir_sesion() -> None:
    """Debe llamarse al inicio de cada página de pages/. Si no hay una
    sesión iniciada (por ejemplo, alguien entra directo a la URL de una
    página sin pasar por el login de app.py), corta la ejecución de esa
    página y muestra un aviso para volver a iniciar sesión."""
    if "usuario_autenticado" not in st.session_state:
        st.warning("Debes iniciar sesión primero.")
        st.page_link("app.py", label="⬅️ Ir a iniciar sesión", icon="⬅️")
        st.stop()


def mostrar_login() -> None:
    """Se llama al inicio de app.py. Si ya hay sesión activa, no hace
    nada y la página sigue su curso normal. Si no, muestra el formulario
    de usuario/contraseña y detiene la ejecución del resto de la página
    hasta que las credenciales sean correctas."""
    if "usuario_autenticado" in st.session_state:
        return

    import db  # import local para evitar dependencia circular con db.py

    st.markdown("### 🔒 Iniciar sesión")
    st.caption("Control de Prefacturas -- acceso interno")

    with st.form("form_login"):
        username = st.text_input("Usuario")
        password = st.text_input("Contraseña", type="password")
        enviado = st.form_submit_button("Ingresar", use_container_width=True)

    if enviado:
        usuario = db.obtener_usuario(username.strip())
        if usuario and verificar_password(password, usuario["salt"], usuario["password_hash"]):
            st.session_state["usuario_autenticado"] = True
            st.session_state["username"] = usuario["username"]
            st.session_state["nombre_completo"] = usuario["nombre_completo"] or usuario["username"]
            st.rerun()
        else:
            st.error("Usuario o contraseña incorrectos.")

    st.stop()


def cerrar_sesion() -> None:
    """Limpia la sesión del usuario actual, incluyendo sus preferencias
    cargadas en memoria (columnas elegidas, etc.), para que el siguiente
    login (del mismo u otro usuario) arranque limpio.

    Nota: no se llama a st.rerun() aquí. Al usarse como on_click de un
    botón, Streamlit ya vuelve a ejecutar el script automáticamente en
    cuanto termina esta función -- llamarlo aquí no tiene efecto y solo
    genera una advertencia."""
    claves_a_limpiar = [
        "usuario_autenticado", "username", "nombre_completo",
        "preferencias_cargadas", "orden_columnas",
    ]
    for clave in claves_a_limpiar:
        st.session_state.pop(clave, None)

    for clave in list(st.session_state.keys()):
        if clave.startswith("cols_"):
            st.session_state.pop(clave, None)


def mostrar_barra_usuario() -> None:
    """Barra en la sidebar con el nombre del usuario activo y botón de
    cerrar sesión. Se llama desde app.py y desde cada página."""
    with st.sidebar:
        st.caption(f"👤 {st.session_state.get('nombre_completo', '')}")
        st.button("Cerrar sesión", on_click=cerrar_sesion, use_container_width=True)