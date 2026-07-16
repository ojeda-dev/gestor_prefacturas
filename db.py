"""Toda la interacción con SQLite vive aquí. Ningún otro módulo debería
importar `sqlite3` directamente.

¿Por qué SQLite y no Postgres? Con 3 usuarios internos y ~1,200 registros,
un archivo local es más que suficiente: cero infraestructura que mantener,
y SQLite maneja sin problema varias lecturas concurrentes (que es el caso
de uso aquí -- lecturas frecuentes, escrituras solo durante la sincronización).
Si el equipo crece a decenas de usuarios concurrentes o el volumen sube a
cientos de miles de registros, ahí sí valdría migrar a Postgres.
"""
import sqlite3
from datetime import datetime, date

import pandas as pd

from config import DB_PATH

DDL = """
CREATE TABLE IF NOT EXISTS prefacturas (
    prefactura              TEXT PRIMARY KEY,
    f310_referencia         TEXT,
    f310_numero_orden_compra TEXT,
    f310_vlr_bruto          REAL,
    f310_vlr_dscto          REAL,
    f310_vlr_imp            REAL,
    f310_vlr_neto           REAL,
    fecha_creacion          TEXT,
    fecha_aprovacion        TEXT,
    fecha_anulado           TEXT,
    fecha_facturacion       TEXT,
    factura                 TEXT,
    f200_nit                TEXT,
    f200_razon_social       TEXT,
    f015_contacto           TEXT,
    f015_telefono           TEXT,
    f015_celular            TEXT,
    f015_email              TEXT,
    tipo_cliente            TEXT,
    f310_id_cond_pago       TEXT,
    f310_id_moneda_docto    TEXT,
    f310_notas              TEXT,
    estado                  TEXT,
    actualizado_en          TEXT
);
CREATE INDEX IF NOT EXISTS idx_prefacturas_nit ON prefacturas(f200_nit);
CREATE INDEX IF NOT EXISTS idx_prefacturas_estado ON prefacturas(estado);

CREATE TABLE IF NOT EXISTS clientes (
    nit                     TEXT PRIMARY KEY,
    razon_social            TEXT,
    contacto                TEXT,
    telefono                TEXT,
    celular                 TEXT,
    email                   TEXT,
    direccion               TEXT,
    pais                    TEXT,
    moneda                  TEXT,
    tipo_oc                 TEXT DEFAULT '',
    observaciones           TEXT DEFAULT '',
    links                   TEXT DEFAULT '',
    actualizado_en_siesa    TEXT,
    actualizado_en_usuario  TEXT
);

CREATE TABLE IF NOT EXISTS sync_metadata (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    ultima_sincronizacion TEXT,
    total_registros INTEGER
);

CREATE TABLE IF NOT EXISTS usuarios (
    username         TEXT PRIMARY KEY,
    nombre_completo  TEXT,
    password_hash    TEXT NOT NULL,
    salt             TEXT NOT NULL,
    creado_en        TEXT
);

CREATE TABLE IF NOT EXISTS preferencias_usuario (
    username         TEXT PRIMARY KEY,
    columnas_json    TEXT,
    filtro_estado    TEXT,
    anios_json       TEXT,
    meses_json       TEXT,
    actualizado_en   TEXT,
    FOREIGN KEY (username) REFERENCES usuarios(username)
);

CREATE TABLE IF NOT EXISTS gmail_tokens (
    username           TEXT PRIMARY KEY,
    refresh_token      TEXT NOT NULL,
    correo_autorizado  TEXT,
    autorizado_en      TEXT,
    FOREIGN KEY (username) REFERENCES usuarios(username)
);

CREATE TABLE IF NOT EXISTS envios_correo (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    prefactura           TEXT NOT NULL,
    username             TEXT NOT NULL,
    destinatario_to      TEXT,
    destinatarios_cc     TEXT,
    asunto               TEXT,
    adjuntos             TEXT,
    message_id_rfc822    TEXT,
    gmail_message_id     TEXT,
    gmail_thread_id      TEXT,
    gmail_account_usado  TEXT,
    enviado_en           TEXT
);
CREATE INDEX IF NOT EXISTS idx_envios_prefactura ON envios_correo(prefactura);

CREATE TABLE IF NOT EXISTS configuracion_gestion (
    id                      INTEGER PRIMARY KEY CHECK (id = 1),
    plazo_dias_habiles      INTEGER DEFAULT 5,
    dias_recordatorio       INTEGER DEFAULT 3,
    dias_suspender          INTEGER DEFAULT 5,
    actualizado_en          TEXT
);

CREATE TABLE IF NOT EXISTS gestion_prefacturas (
    prefactura              TEXT PRIMARY KEY,
    fecha_primer_correo     TEXT NOT NULL,
    estado_gestion          TEXT NOT NULL DEFAULT 'Pendiente',
    dias_habiles_transcurridos INTEGER DEFAULT 0,
    actualizado_en          TEXT
);
"""

COLUMNAS_TABLA = [
    'prefactura', 'f310_referencia', 'f310_numero_orden_compra',
    'f310_vlr_bruto', 'f310_vlr_dscto', 'f310_vlr_imp', 'f310_vlr_neto',
    'fecha_creacion', 'fecha_aprovacion', 'fecha_anulado', 'fecha_facturacion',
    'factura', 'f200_nit', 'f200_razon_social', 'f015_contacto',
    'f015_telefono', 'f015_celular', 'f015_email', 'tipo_cliente',
    'f310_id_cond_pago', 'f310_id_moneda_docto', 'f310_notas', 'estado',
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def _migrar_columnas_faltantes(conn: sqlite3.Connection) -> None:
    """Agrega columnas nuevas a tablas que ya existían de una versión
    anterior de la app, sin necesidad de borrar la base de datos.
    SQLite no soporta 'ADD COLUMN IF NOT EXISTS', así que verificamos
    manualmente con PRAGMA table_info."""
    columnas_actuales = {row[1] for row in conn.execute("PRAGMA table_info(clientes)")}
    if "email" not in columnas_actuales:
        conn.execute("ALTER TABLE clientes ADD COLUMN email TEXT")

    columnas_preferencias = {row[1] for row in conn.execute("PRAGMA table_info(preferencias_usuario)")}
    if "anios_json" not in columnas_preferencias:
        conn.execute("ALTER TABLE preferencias_usuario ADD COLUMN anios_json TEXT")
    if "meses_json" not in columnas_preferencias:
        conn.execute("ALTER TABLE preferencias_usuario ADD COLUMN meses_json TEXT")

    columnas_envios = {row[1] for row in conn.execute("PRAGMA table_info(envios_correo)")}
    if "adjuntos" not in columnas_envios:
        conn.execute("ALTER TABLE envios_correo ADD COLUMN adjuntos TEXT")


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(DDL)
        _migrar_columnas_faltantes(conn)


def reemplazar_datos(df: pd.DataFrame) -> None:
    """Reemplaza el contenido completo de la tabla con el DataFrame recibido.

    Se usa un reemplazo total (no upsert incremental) porque la fuente de
    verdad sigue siendo Siesa: si una prefactura se anula o se corrige allá,
    queremos que la sincronización siguiente lo refleje sin dejar registros
    huérfanos. Con ~1,200 filas esto toma milisegundos, así que no hay
    penalización real de rendimiento por hacerlo así."""
    init_db()

    df_para_guardar = df.copy()
    for col in COLUMNAS_TABLA:
        if col not in df_para_guardar.columns:
            df_para_guardar[col] = None

    # Fechas como texto ISO para que SQLite las guarde de forma consistente
    for col in ('fecha_creacion', 'fecha_aprovacion', 'fecha_anulado', 'fecha_facturacion'):
        df_para_guardar[col] = df_para_guardar[col].apply(
            lambda v: v.isoformat() if pd.notna(v) else None
        )

    with get_connection() as conn:
        conn.execute("DELETE FROM prefacturas")
        df_para_guardar[COLUMNAS_TABLA].to_sql(
            "prefacturas", conn, if_exists="append", index=False
        )
        conn.execute(
            """
            INSERT INTO sync_metadata (id, ultima_sincronizacion, total_registros)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                ultima_sincronizacion = excluded.ultima_sincronizacion,
                total_registros = excluded.total_registros
            """,
            (datetime.now().isoformat(), len(df_para_guardar)),
        )


def obtener_todas() -> pd.DataFrame:
    init_db()
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM prefacturas", conn)

    for col in ('fecha_creacion', 'fecha_aprovacion', 'fecha_anulado', 'fecha_facturacion'):
        df[col] = pd.to_datetime(df[col], errors='coerce')

    return df


def obtener_todos_los_clientes() -> pd.DataFrame:
    """Trae el catálogo completo de clientes (datos de Siesa + manuales).
    Se usa para poder mostrar columnas como 'Tipo de OC' u 'Observaciones'
    en el listado principal, que solo existen en esta tabla."""
    init_db()
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM clientes", conn)


def obtener_historial_por_nit(nit: str) -> pd.DataFrame:
    init_db()
    with get_connection() as conn:
        df = pd.read_sql(
            "SELECT * FROM prefacturas WHERE f200_nit = ? ORDER BY fecha_creacion DESC",
            conn, params=(nit,),
        )

    for col in ('fecha_creacion', 'fecha_aprovacion', 'fecha_anulado', 'fecha_facturacion'):
        df[col] = pd.to_datetime(df[col], errors='coerce')

    return df


def obtener_metadata_sync() -> dict:
    init_db()
    with get_connection() as conn:
        cur = conn.execute("SELECT ultima_sincronizacion, total_registros FROM sync_metadata WHERE id = 1")
        row = cur.fetchone()

    if row is None:
        return {"ultima_sincronizacion": None, "total_registros": 0}
    return {"ultima_sincronizacion": row[0], "total_registros": row[1]}


# ---------------------------------------------------------------------------
# Clientes: catálogo único por NIT con datos de Siesa + campos manuales.
#
# A diferencia de `reemplazar_datos`, aquí NO se borra la tabla en cada
# sincronización. Se usa upsert (INSERT ... ON CONFLICT DO UPDATE) y la
# cláusula de actualización SOLO incluye las columnas que vienen de Siesa.
# Los campos manuales (tipo_oc, observaciones, links) jamás aparecen en
# esa cláusula, así que sincronizar 1 o 1000 veces nunca los toca.
# ---------------------------------------------------------------------------

def upsert_clientes(df_prefacturas: pd.DataFrame) -> None:
    """Extrae el catálogo único de clientes desde el DataFrame de
    prefacturas ya normalizado (antes de recortarlo a COLUMNAS_TABLA) y
    actualiza sus datos de Siesa en la tabla `clientes`, preservando
    cualquier campo manual que el usuario ya haya llenado."""
    init_db()

    if df_prefacturas.empty:
        return

    # Nos quedamos con el registro más reciente por NIT, para que los
    # datos de contacto reflejen la información más actual de Siesa.
    df_ordenado = df_prefacturas.sort_values('fecha_creacion', ascending=False)
    ultimo_por_nit = df_ordenado.drop_duplicates(subset='f200_nit', keep='first')

    ahora = datetime.now().isoformat()

    filas = [
        (
            row.get('f200_nit'),
            row.get('f200_razon_social'),
            row.get('f015_contacto'),
            row.get('f015_telefono'),
            row.get('f015_celular'),
            row.get('f015_email'),
            row.get('f015_direccion1'),
            row.get('pais'),
            row.get('f310_id_moneda_docto'),
            ahora,
        )
        for _, row in ultimo_por_nit.iterrows()
        if pd.notna(row.get('f200_nit'))
    ]

    with get_connection() as conn:
        conn.executemany(
            """
            INSERT INTO clientes (
                nit, razon_social, contacto, telefono, celular, email,
                direccion, pais, moneda, actualizado_en_siesa
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(nit) DO UPDATE SET
                razon_social         = excluded.razon_social,
                contacto             = excluded.contacto,
                telefono             = excluded.telefono,
                celular              = excluded.celular,
                email                = excluded.email,
                direccion            = excluded.direccion,
                pais                 = excluded.pais,
                moneda               = excluded.moneda,
                actualizado_en_siesa = excluded.actualizado_en_siesa
            """,
            filas,
        )


def obtener_cliente(nit: str) -> dict | None:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM clientes WHERE nit = ?", (nit,))
        row = cur.fetchone()

    return dict(row) if row else None


def actualizar_datos_cliente(nit: str, tipo_oc: str, observaciones: str, links: str) -> None:
    """Guarda los campos manuales de un cliente. Nunca es tocada por
    upsert_clientes, así que no hay riesgo de que una sincronización
    borre lo que el usuario escribió aquí."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE clientes
            SET tipo_oc = ?, observaciones = ?, links = ?, actualizado_en_usuario = ?
            WHERE nit = ?
            """,
            (tipo_oc, observaciones, links, datetime.now().isoformat(), nit),
        )


# ---------------------------------------------------------------------------
# Usuarios: login simple para uso interno. Las contraseñas nunca se
# guardan en texto plano -- solo su hash + salt (ver auth.py).
# ---------------------------------------------------------------------------

def crear_usuario(username: str, nombre_completo: str, password_hash: str, salt: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO usuarios (username, nombre_completo, password_hash, salt, creado_en)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, nombre_completo, password_hash, salt, datetime.now().isoformat()),
        )


def actualizar_password_usuario(username: str, password_hash: str, salt: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            "UPDATE usuarios SET password_hash = ?, salt = ? WHERE username = ?",
            (password_hash, salt, username),
        )


def obtener_usuario(username: str) -> dict | None:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM usuarios WHERE username = ?", (username,))
        row = cur.fetchone()

    return dict(row) if row else None


def listar_usuarios() -> list[str]:
    init_db()
    with get_connection() as conn:
        cur = conn.execute("SELECT username FROM usuarios ORDER BY username")
        return [row[0] for row in cur.fetchall()]


# ---------------------------------------------------------------------------
# Preferencias por usuario: qué columnas eligió ver y qué filtro de
# estado tenía activo. Se restauran automáticamente la próxima vez que
# ese usuario inicie sesión.
# ---------------------------------------------------------------------------

def guardar_preferencias(
    username: str, columnas_json: str, filtro_estado: str,
    anios_json: str = "[]", meses_json: str = "[]",
) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO preferencias_usuario (
                username, columnas_json, filtro_estado, anios_json, meses_json, actualizado_en
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                columnas_json  = excluded.columnas_json,
                filtro_estado  = excluded.filtro_estado,
                anios_json     = excluded.anios_json,
                meses_json     = excluded.meses_json,
                actualizado_en = excluded.actualizado_en
            """,
            (username, columnas_json, filtro_estado, anios_json, meses_json, datetime.now().isoformat()),
        )


def obtener_preferencias(username: str) -> dict | None:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM preferencias_usuario WHERE username = ?", (username,))
        row = cur.fetchone()

    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Gmail: cada usuario conecta su PROPIA cuenta (OAuth) vía conectar_gmail.py.
# Solo se guarda el refresh_token (nunca la contraseña de Gmail -- eso lo
# maneja Google, la app nunca la ve).
# ---------------------------------------------------------------------------

def guardar_token_gmail(username: str, refresh_token: str, correo_autorizado: str) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO gmail_tokens (username, refresh_token, correo_autorizado, autorizado_en)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(username) DO UPDATE SET
                refresh_token     = excluded.refresh_token,
                correo_autorizado = excluded.correo_autorizado,
                autorizado_en     = excluded.autorizado_en
            """,
            (username, refresh_token, correo_autorizado, datetime.now().isoformat()),
        )


def obtener_token_gmail(username: str) -> dict | None:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM gmail_tokens WHERE username = ?", (username,))
        row = cur.fetchone()

    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Auditoría de envíos de correo: qué usuario le envió qué correo a qué
# prefactura, y los identificadores necesarios para que un reenvío quede
# en el mismo hilo de conversación (ver gmail_client.py).
# ---------------------------------------------------------------------------

def registrar_envio_correo(
    prefactura: str, username: str, destinatario_to: str, destinatarios_cc: str,
    asunto: str, message_id_rfc822: str, gmail_message_id: str,
    gmail_thread_id: str, gmail_account_usado: str, adjuntos: str = "",
) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO envios_correo (
                prefactura, username, destinatario_to, destinatarios_cc, asunto,
                adjuntos, message_id_rfc822, gmail_message_id, gmail_thread_id,
                gmail_account_usado, enviado_en
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prefactura, username, destinatario_to, destinatarios_cc, asunto,
                adjuntos, message_id_rfc822, gmail_message_id, gmail_thread_id,
                gmail_account_usado, datetime.now().isoformat(),
            ),
        )


def obtener_envios_por_prefactura(prefactura: str) -> list[dict]:
    """Ordenado del más antiguo al más reciente -- así se puede reconstruir
    la cadena de References/In-Reply-To en el orden correcto."""
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM envios_correo WHERE prefactura = ? ORDER BY enviado_en ASC",
            (prefactura,),
        )
        return [dict(row) for row in cur.fetchall()]


def obtener_todos_los_envios() -> pd.DataFrame:
    """Para el dashboard de resumen de correos: todos los envíos
    registrados, del más reciente al más antiguo."""
    init_db()
    with get_connection() as conn:
        df = pd.read_sql("SELECT * FROM envios_correo ORDER BY enviado_en DESC", conn)

    df['enviado_en'] = pd.to_datetime(df['enviado_en'], errors='coerce')
    return df


def obtener_conteo_envios_por_prefactura() -> dict[str, int]:
    """Retorna {prefactura: cantidad_de_envios} para todas las prefacturas
    que tienen al menos un correo registrado."""
    init_db()
    with get_connection() as conn:
        cur = conn.execute(
            "SELECT prefactura, COUNT(*) as total FROM envios_correo GROUP BY prefactura"
        )
        return {row[0]: row[1] for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Configuración global de reglas de gestión (singleton: solo 1 fila).
# ---------------------------------------------------------------------------

def obtener_configuracion_gestion() -> dict:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM configuracion_gestion WHERE id = 1")
        row = cur.fetchone()

    if row is None:
        return {
            "plazo_dias_habiles": 5,
            "dias_recordatorio": 3,
            "dias_suspender": 5,
        }
    return dict(row)


def guardar_configuracion_gestion(
    plazo_dias_habiles: int, dias_recordatorio: int, dias_suspender: int,
) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO configuracion_gestion (id, plazo_dias_habiles, dias_recordatorio, dias_suspender, actualizado_en)
            VALUES (1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                plazo_dias_habiles = excluded.plazo_dias_habiles,
                dias_recordatorio  = excluded.dias_recordatorio,
                dias_suspender     = excluded.dias_suspender,
                actualizado_en     = excluded.actualizado_en
            """,
            (plazo_dias_habiles, dias_recordatorio, dias_suspender, datetime.now().isoformat()),
        )


# ---------------------------------------------------------------------------
# Gestión por prefactura: registra el primer correo y rastrea el
# estado de seguimiento (Pendiente / Recordatorio / Suspender).
# ---------------------------------------------------------------------------

def registrar_primer_correo(prefactura: str, fecha_primer_correo: str) -> None:
    """Inserta un registro de gestión SOLO si no existía ya para esta
    prefactura (no sobreescribe un registro existente)."""
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO gestion_prefacturas (prefactura, fecha_primer_correo, estado_gestion, dias_habiles_transcurridos, actualizado_en)
            VALUES (?, ?, 'Pendiente', 0, ?)
            """,
            (prefactura, fecha_primer_correo, datetime.now().isoformat()),
        )


def actualizar_estado_gestion(prefactura: str, estado: str, dias_habiles: int) -> None:
    init_db()
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE gestion_prefacturas
            SET estado_gestion = ?, dias_habiles_transcurridos = ?, actualizado_en = ?
            WHERE prefactura = ?
            """,
            (estado, dias_habiles, datetime.now().isoformat(), prefactura),
        )


def obtener_gestion_prefactura(prefactura: str) -> dict | None:
    init_db()
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT * FROM gestion_prefacturas WHERE prefactura = ?", (prefactura,)
        )
        row = cur.fetchone()
    return dict(row) if row else None


def obtener_todas_las_gestiones() -> pd.DataFrame:
    init_db()
    with get_connection() as conn:
        return pd.read_sql("SELECT * FROM gestion_prefacturas", conn)


def recalcular_todos_los_estados_gestion() -> None:
    """Recalcula el estado de gestión de TODAS las prefacturas que tengan
    registro en gestion_prefacturas, usando la configuración actual."""
    from dateutil import parser as dtparser
    from gestion import calcular_estado_gestion

    config = obtener_configuracion_gestion()
    gestiones = obtener_todas_las_gestiones()

    if gestiones.empty:
        return

    hoy = date.today()
    for _, row in gestiones.iterrows():
        fecha_pc = dtparser.isoparse(row['fecha_primer_correo']).date()
        estado, dias = calcular_estado_gestion(
            fecha_pc, hoy,
            config['dias_recordatorio'],
            config['dias_suspender'],
        )
        actualizar_estado_gestion(row['prefactura'], estado, dias)


def inicializar_gestiones_retroactivas() -> int:
    """Para cada prefactura que tiene correos enviados pero NO tiene
    registro en gestion_prefacturas, crea el registro usando la fecha
    del primer correo. Retorna la cantidad de registros creados."""
    from dateutil import parser as dtparser
    from gestion import calcular_estado_gestion

    init_db()
    config = obtener_configuracion_gestion()
    hoy = date.today()
    creados = 0

    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT prefactura, MIN(enviado_en) as primer_correo
            FROM envios_correo
            GROUP BY prefactura
            """
        )
        envios_por_prefactura = cur.fetchall()

    for prefactura, primer_correo_str in envios_por_prefactura:
        existe = obtener_gestion_prefactura(prefactura)
        if existe:
            continue

        fecha_pc = dtparser.isoparse(primer_correo_str).date()
        estado, dias = calcular_estado_gestion(
            fecha_pc, hoy,
            config['dias_recordatorio'],
            config['dias_suspender'],
        )

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO gestion_prefacturas (prefactura, fecha_primer_correo, estado_gestion, dias_habiles_transcurridos, actualizado_en)
                VALUES (?, ?, ?, ?, ?)
                """,
                (prefactura, primer_correo_str, estado, dias, datetime.now().isoformat()),
            )
        creados += 1

    return creados
