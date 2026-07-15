"""Envío de correos vía la API de Gmail.

Cada usuario conecta su PROPIA cuenta de Gmail (ver conectar_gmail.py) --
la app nunca ve ni guarda contraseñas, solo un refresh_token que Google
emite tras el consentimiento del usuario, con permiso limitado a
"enviar correos" (scope gmail.send), no a leer la bandeja de entrada.

Soporte de hilos (threading): cuando ya se le envió un correo antes a una
prefactura, un "reenvío" debe aparecer en la misma conversación de correo
para quien lo reciba -- incluso si el reenvío lo hace un usuario distinto
con una cuenta de Gmail distinta a la que envió el primer correo. Por eso
la app misma genera y guarda su propio 'Message-ID' (RFC 822) en cada
envío, y usa 'In-Reply-To' / 'References' para encadenarlos. El threadId
interno de Gmail (que es específico de cada cuenta) solo se reutiliza
cuando el reenvío lo hace la MISMA cuenta que envió antes; si es una
cuenta distinta, el encadenamiento para el destinatario sigue funcionando
gracias a esas cabeceras, que es el mecanismo estándar de threading de
correo (no depende de que ambos envíos salgan del mismo buzón).
"""
from email.message import EmailMessage
from email.utils import make_msgid
import base64

import streamlit as st

import db

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]
TOKEN_URI = "https://oauth2.googleapis.com/token"

# Límite conservador (Gmail acepta ~25MB de adjuntos por correo antes de
# empezar a fallar de forma poco clara vía la API); dejamos margen.
LIMITE_ADJUNTOS_BYTES = 20 * 1024 * 1024


class GmailNoConectado(Exception):
    """El usuario todavía no autorizó su cuenta de Gmail."""


class AdjuntosDemasiadoGrandes(Exception):
    """La suma de los adjuntos supera el límite razonable para un correo."""


def _adjuntar_archivos(mensaje: EmailMessage, adjuntos: list[dict]) -> None:
    """adjuntos: lista de {'nombre': str, 'datos': bytes, 'tipo_mime': str}."""
    if not adjuntos:
        return

    total_bytes = sum(len(a["datos"]) for a in adjuntos)
    if total_bytes > LIMITE_ADJUNTOS_BYTES:
        raise AdjuntosDemasiadoGrandes(
            f"Los adjuntos pesan {total_bytes / 1024 / 1024:.1f} MB en total, "
            f"por encima del límite de {LIMITE_ADJUNTOS_BYTES / 1024 / 1024:.0f} MB."
        )

    for adjunto in adjuntos:
        tipo_mime = adjunto.get("tipo_mime") or "application/octet-stream"
        maintype, _, subtype = tipo_mime.partition("/")
        if not subtype:
            maintype, subtype = "application", "octet-stream"
        mensaje.add_attachment(
            adjunto["datos"],
            maintype=maintype,
            subtype=subtype,
            filename=adjunto["nombre"],
        )


def _construir_mensaje(
    destinatario_to: str,
    destinatarios_cc: list[str],
    asunto: str,
    cuerpo: str,
    envios_previos: list[dict],
    cuenta_remitente: str,
    adjuntos: list[dict] | None = None,
) -> tuple[EmailMessage, str | None]:
    """Arma el EmailMessage con las cabeceras de threading correctas y los
    adjuntos si los hay. Devuelve (mensaje, thread_id_de_gmail_a_reutilizar_o_None).

    Separado de enviar_correo() para poder probarse sin tocar la red ni
    la API de Gmail."""
    mensaje = EmailMessage()
    mensaje.set_content(cuerpo)
    mensaje["To"] = destinatario_to
    if destinatarios_cc:
        mensaje["Cc"] = ", ".join(destinatarios_cc)
    mensaje["Subject"] = asunto

    nuevo_message_id = make_msgid()
    mensaje["Message-ID"] = nuevo_message_id

    thread_id_gmail = None

    if envios_previos:
        referencias = " ".join(
            e["message_id_rfc822"] for e in envios_previos if e.get("message_id_rfc822")
        )
        if referencias:
            mensaje["References"] = referencias
            mensaje["In-Reply-To"] = envios_previos[-1]["message_id_rfc822"]

        # El threadId de Gmail es un id interno de esa cuenta específica.
        # Solo tiene sentido reutilizarlo si el envío anterior salió de la
        # MISMA cuenta que va a enviar ahora.
        anteriores_misma_cuenta = [
            e for e in envios_previos if e.get("gmail_account_usado") == cuenta_remitente
        ]
        if anteriores_misma_cuenta:
            thread_id_gmail = anteriores_misma_cuenta[-1].get("gmail_thread_id")

    _adjuntar_archivos(mensaje, adjuntos or [])

    return mensaje, thread_id_gmail


def _credenciales_para(username: str):
    """Import diferido de las librerías de Google -- así el resto de la
    app no depende de que estén instaladas si alguien no usa esta feature."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request

    token = db.obtener_token_gmail(username)
    if token is None:
        raise GmailNoConectado(
            "No has conectado tu cuenta de Gmail todavía. "
            "Corre 'python conectar_gmail.py' en tu terminal (una sola vez)."
        )

    creds = Credentials(
        token=None,
        refresh_token=token["refresh_token"],
        token_uri=TOKEN_URI,
        client_id=st.secrets["gmail"]["client_id"],
        client_secret=st.secrets["gmail"]["client_secret"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds, token["correo_autorizado"]


def enviar_correo(
    username: str,
    destinatario_to: str,
    destinatarios_cc: list[str],
    asunto: str,
    cuerpo: str,
    prefactura: str,
    adjuntos: list[dict] | None = None,
) -> dict:
    """Envía el correo y devuelve los identificadores que hay que guardar
    en envios_correo (vía db.registrar_envio_correo) para que un futuro
    reenvío quede en el mismo hilo.

    adjuntos: lista de {'nombre': str, 'datos': bytes, 'tipo_mime': str}."""
    from googleapiclient.discovery import build

    creds, cuenta_remitente = _credenciales_para(username)
    envios_previos = db.obtener_envios_por_prefactura(prefactura)

    mensaje, thread_id_gmail = _construir_mensaje(
        destinatario_to, destinatarios_cc, asunto, cuerpo, envios_previos, cuenta_remitente,
        adjuntos=adjuntos,
    )

    raw = base64.urlsafe_b64encode(mensaje.as_bytes()).decode()
    cuerpo_peticion = {"raw": raw}
    if thread_id_gmail:
        cuerpo_peticion["threadId"] = thread_id_gmail

    servicio = build("gmail", "v1", credentials=creds)
    enviado = servicio.users().messages().send(userId="me", body=cuerpo_peticion).execute()

    return {
        "message_id_rfc822": mensaje["Message-ID"],
        "gmail_message_id": enviado.get("id"),
        "gmail_thread_id": enviado.get("threadId"),
        "cuenta_gmail": cuenta_remitente,
    }