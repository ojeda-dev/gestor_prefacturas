"""Conecta TU cuenta de Gmail con la app (una sola vez por usuario).

Corre esto en tu terminal, con el venv activado:

    python conectar_gmail.py

Se va a abrir tu navegador para que inicies sesión con la cuenta de
Gmail desde la que quieres enviar los correos, y aceptes el permiso.
La app solo pide permiso para ENVIAR correos -- nunca puede leer tu
bandeja de entrada ni tus contactos.

Requisito previo: en .streamlit/secrets.toml debe existir:

    [gmail]
    client_id = "..."
    client_secret = "..."

Ese client_id/secret se crea UNA VEZ en Google Cloud Console (ver
README.md para el paso a paso) y es el mismo para los 3 usuarios --
lo que es único por persona es la autorización que cada quien da al
correr este script, que es lo que queda guardado en la base de datos.
"""
import streamlit as st
import requests
from google_auth_oauthlib.flow import InstalledAppFlow

import db

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]


def _obtener_correo_autorizado(creds) -> str:
    """Usa el access_token recién emitido para consultar qué cuenta se
    autorizó (gracias al scope userinfo.email agregado arriba)."""
    try:
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {creds.token}"},
            timeout=10,
        )
        return resp.json().get("email", "cuenta desconocida")
    except Exception:
        return "cuenta desconocida"


def main() -> None:
    print("=== Conectar cuenta de Gmail ===")
    username = input("Tu usuario en la app (ej. 'andres'): ").strip().lower()

    if db.obtener_usuario(username) is None:
        print(f"El usuario '{username}' no existe en la app. Créalo primero con: python crear_usuario.py")
        return

    try:
        client_id = st.secrets["gmail"]["client_id"]
        client_secret = st.secrets["gmail"]["client_secret"]
    except Exception:
        print(
            "No encontré [gmail] client_id/client_secret en .streamlit/secrets.toml. "
            "Revisa el README para crear las credenciales en Google Cloud Console primero."
        )
        return

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    print("Se va a abrir tu navegador. Inicia sesión con la cuenta de Gmail que quieres usar y acepta el permiso.")
    creds = flow.run_local_server(port=0)

    correo_autorizado = _obtener_correo_autorizado(creds)
    db.guardar_token_gmail(username, creds.refresh_token, correo_autorizado)
    print(f"\n✅ Listo. La cuenta {correo_autorizado} quedó conectada para el usuario '{username}'.")


if __name__ == "__main__":
    main()
