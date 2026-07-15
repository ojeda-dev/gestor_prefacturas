"""Todo lo relacionado con hablar con la API de Siesa vive aquí.
Ningún otro módulo debería usar `requests` directamente."""
import requests
import streamlit as st

from config import URL_API, ID_COMPANIA, DESCRIPCION_CONSULTA, TAMANO_PAGINA


class SiesaError(Exception):
    """Error controlado al consultar la API de Siesa."""


def _headers() -> dict:
    return {
        "client_id": st.secrets["siesa"]["client_id"],
        "ConniKey": st.secrets["siesa"]["ConniKey"],
        "ConniToken": st.secrets["siesa"]["ConniToken"],
    }


def obtener_pagina(numero_pagina: int) -> dict:
    """Trae el JSON crudo de una página. Lanza SiesaError con un mensaje
    entendible si algo falla (red, HTTP, o error de negocio de Siesa)."""
    query_params = {
        "idCompania": ID_COMPANIA,
        "descripcion": DESCRIPCION_CONSULTA,
        "paginacion": f"numPag={numero_pagina}|tamPag={TAMANO_PAGINA}",
    }

    try:
        response = requests.get(URL_API, params=query_params, headers=_headers(), timeout=15)
        response.raise_for_status()
    except requests.exceptions.Timeout:
        raise SiesaError("La consulta a Siesa tardó demasiado en responder (timeout).")
    except requests.exceptions.HTTPError:
        raise SiesaError(f"Error al conectarse a Siesa. Código de estado: {response.status_code}")
    except requests.exceptions.RequestException as e:
        raise SiesaError(f"No se pudo establecer la conexión con el servidor: {e}")

    payload = response.json()
    if payload.get("codigo") != 0:
        raise SiesaError(f"Siesa respondió con error: {payload.get('mensaje', 'sin mensaje')}")

    return payload


def obtener_todas_las_paginas() -> list[dict]:
    """Recorre todas las páginas reportadas por la API y devuelve la lista
    completa de registros crudos (sin normalizar)."""
    primera = obtener_pagina(1)
    detalle = primera.get("detalle", {})
    total_paginas = detalle.get("total_páginas", 1)

    registros = list(detalle.get("Datos", []))

    for pagina in range(2, total_paginas + 1):
        payload = obtener_pagina(pagina)
        registros.extend(payload.get("detalle", {}).get("Datos", []))

    return registros
