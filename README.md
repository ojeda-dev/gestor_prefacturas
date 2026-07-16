# Control de Prefacturas

Sistema interno de gestión de prefacturas para el equipo comercial. Sincroniza datos del ERP Siesa Cloud hacia una base SQLite local, permite explorar, filtrar y buscar prefacturas con KPIs en tiempo real, enviar correos electrónicos a clientes para solicitar Órdenes de Compra, y auditar toda la actividad de envío.

Diseñado para un equipo pequeño (~3 usuarios, ~1,200 registros). Sin infraestructura de servidor.

---

## Tabla de contenidos

1. [Tecnologías](#tecnologías)
2. [Características principales](#características-principales)
3. [Estructura del proyecto](#estructura-del-proyecto)
4. [Requisitos previos](#requisitos-previos)
5. [Instalación](#instalación)
6. [Configuración](#configuración)
7. [Uso](#uso)
8. [Sincronización de datos](#sincronización-de-datos)
9. [Envío de correos (Gmail API)](#envío-de-correos-gmail-api)
10. [Arquitectura y diseño](#arquitectura-y-diseño)
11. [Modelos de datos](#modelos-de-datos)
12. [Scripts CLI](#scripts-cli)
13. [Respaldo automático](#respaldo-automático)
14. [Búsqueda fuzzy](#búsqueda-fuzzy)
15. [Solución de problemas](#solución-de-problemas)

---

## Tecnologías

| Componente | Tecnología | Versión mínima |
|---|---|---|
| Framework UI | Streamlit | ≥ 1.35 |
| Base de datos | SQLite (embebida) | — |
| Manipulación de datos | Pandas | ≥ 2.0 |
| API ERP | Siesa Cloud API | v3.0.1 |
| Envío de correos | Gmail API (Google) | — |
| Búsqueda fuzzy | rapidfuzz | ≥ 3.0 |
| Autenticación | PBKDF2-HMAC-SHA256 (hashlib) | — |
| Gráficos | Altair | — |
| OAuth | google-auth, google-auth-oauthlib | ≥ 2.30, ≥ 1.2 |
| Plataforma | Python 3.14+ | Windows/Linux |

---

## Características principales

- **Sincronización automática** desde Siesa Cloud con reemplazo total (sin registros fantasma)
- **Listado interactivo** con KPIs: cantidad y valor sin facturar (COP y USD)
- **Filtros** por estado (Sin Facturar / Facturadas / Anuladas), año y mes
- **Búsqueda tolerante** a tildes y errores de tipeo (fuzzy search)
- **Personalización de columnas**: el usuario elige qué columnas ver, con persistencia por sesión
- **Envío de correos** vía Gmail API con soporte de threading y adjuntos (hasta 20 MB)
- **Auditoría completa** de correos enviados (quién, cuándo, a quién, qué prefactura)
- **Historial de cliente** con gráfico de valor facturado por mes (Altair)
- **Ficha de cliente** con datos de Siesa (solo lectura) y campos editables manuales (Tipo OC, Observaciones, Links)
- **Dashboard de correos** con KPIs, gráfico por usuario y lista de prefacturas sin contactar
- **Respaldo automático** diario con retención de 30 días
- **Autenticación** con contraseñas hasheadas (PBKDF2, 200k iteraciones)
- **Preferencias persistentes** por usuario (columnas, filtros, años, meses)

---

## Estructura del proyecto

```
proyecto_prefacturas/
├── app.py                        # Página principal: listado, filtros, KPIs, envío de correo
├── pages/
│   ├── 1_Historial_Cliente.py    # Historial + gráfico de facturación del cliente
│   ├── 2_Ficha_Cliente.py        # Datos de Siesa + campos manuales (Tipo OC, Observaciones, Links)
│   └── 3_Resumen_Correos.py      # Dashboard de correos enviados
├── siesa_client.py               # Cliente de la API de Siesa (ERP)
├── gmail_client.py               # Envío de correos + threading (vía Gmail API)
├── conectar_gmail.py             # Script: cada usuario conecta su cuenta de Gmail (OAuth)
├── auth.py                       # Login (usuario/contraseña con hash PBKDF2)
├── crear_usuario.py              # Script: crear/actualizar usuarios (interactivo por consola)
├── search.py                     # Buscador tolerante a tildes y errores de tipeo (rapidfuzz)
├── reportes.py                   # Agregaciones para gráficos (valor facturado por mes)
├── data.py                       # Normalización y reglas de negocio (determinación de estado)
├── db.py                         # Capa de acceso a datos (init, guardar, consultar SQLite)
├── sync.py                       # Sincroniza Siesa -> SQLite (reemplazo total)
├── backup.py                     # Respaldo automático diario de la BD
├── config.py                     # Constantes compartidas (URL API, columnas, rutas)
├── control_prefacturas.py        # Versión legacy/alternativa (consulta directa a API, sin BD local)
├── data/
│   ├── prefacturas.db            # Base de datos SQLite (se crea automáticamente)
│   └── backups/                  # Respaldos diarios (prefacturas_YYYYMMDD.db)
├── .streamlit/
│   └── secrets.toml              # Credenciales (Siesa API + Gmail OAuth)
├── requirements.txt              # Dependencias de Python
└── README.md                     # Este archivo
```

---

## Requisitos previos

- **Python 3.14+** (recomendado: crear un entorno virtual)
- **Cuenta de Siesa Cloud** con acceso a la API de consulta de prefacturas
- **Cuenta de Google Cloud** (opcional, solo si se desea envío de correos vía Gmail)

---

## Instalación

### 1. Clonar el repositorio

```bash
git clone <url_del_repositorio>
cd proyecto_prefacturas
```

### 2. Crear entorno virtual e instalar dependencias

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

En Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Crear el primer usuario

```powershell
python crear_usuario.py
```

El script es interactivo: pide usuario, nombre completo, y contraseña (con confirmación). Las contraseñas se almacenan con hash PBKDF2 (200,000 iteraciones + salt aleatorio).

### 4. Ejecutar la app

```powershell
streamlit run app.py
```

Se abre el navegador en `http://localhost:8501`. Inicia sesión con las credenciales creadas en el paso anterior.

---

## Configuración

Todas las credenciales se almacenan en `.streamlit/secrets.toml`:

```toml
[siesa]
client_id = "tu_client_id"
ConniKey = "tu_conni_key"
ConniToken = "tu_conni_token"

[gmail]
client_id = "tu_client_id.apps.googleusercontent.com"
client_secret = "tu_client_secret"
```

> **Nota:** El archivo `.streamlit/secrets.toml` nunca se commitea al repositorio. Cada entorno de despliegue debe crearlo manualmente.

---

## Uso

### Listado principal (`app.py`)

Al iniciar sesión se muestra la tabla de prefacturas con:

- **KPIs superiores**: cantidad sin facturar, valor sin facturar (COP y USD)
- **Filtros en la barra lateral**: estado (Todos / Sin Facturar / Facturadas / Anuladas), año, mes de fecha de creación
- **Búsqueda**: campo de búsqueda que acepta NIT, razón social, número de prefactura, o contacto. Tolera tildes y errores de tipeo.
- **Personalización de columnas**: botón "⚙️ Columnas" para elegir qué columnas ver, agrupadas en:
  - Prefactura Siesa (referencia, orden de compra, valores, fechas, factura, notas)
  - Cliente Siesa (NIT, razón social, contacto, teléfono, celular, email, tipo cliente, condición de pago, moneda)
  - Datos Adicionales (estado)
- **Preferencias persistentes**: columnas, filtro de estado, años y meses seleccionados se guardan por usuario y se restauran en la próxima sesión.

Al seleccionar una fila en la tabla se despliega un panel de acciones:

- **Enviar correo**: abre formulario para redactar y enviar un correo al cliente (ver sección de envío de correos)
- **Ver historial completo**: navega a la página de historial del cliente
- **Ver/Editar ficha**: navega a la ficha del cliente

### Historial de cliente (`pages/1_Historial_Cliente.py`)

- Muestra todas las prefacturas de un cliente específico (por NIT), con consultas indexadas a SQLite.
- **KPIs del cliente**: total prefacturas, pendientes, valor pendiente COP/USD.
- **Gráfico de valor facturado por mes** (Altair), con filtros de año y mes, separado por moneda (COP/USD).

### Ficha de cliente (`pages/2_Ficha_Cliente.py`)

- **Datos de Siesa** (solo lectura): razón social, contacto, teléfono, celular, email, dirección, país, moneda.
- **Campos editables manuales**: Tipo de OC, Observaciones, Links.
  - Estos campos **nunca se sobreescriben** en una sincronización (upsert preservando campos manuales).
- Links clickeables como accesos rápidos.

### Dashboard de correos enviados (`pages/3_Resumen_Correos.py`)

- **KPIs**: total correos enviados, enviados en últimos 7 días, prefacturas contactadas.
- **Gráfico de correos por usuario**.
- **Lista de prefacturas sin facturar que nunca han recibido correo** (vista accionable para el equipo comercial).
- **Historial reciente** de envíos (últimos 200 registros).

---

## Sincronización de datos

### Manual

Botón "🔄 Sincronizar ahora" en la barra lateral de la app.

### Automática (recomendada)

Programar `sync.py` para que corra periódicamente:

**Linux/macOS (cron), cada 15 minutos:**

```bash
*/15 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/python sync.py >> sync.log 2>&1
```

**Windows (Task Scheduler):**

1. Abrir Programador de Tareas
2. Crear tarea nueva → Acción: "Iniciar un programa"
3. Programa: `python sync.py`
4. Iniciar en: `C:\Users\Usuario\Desktop\Proyectos\proyecto_prefacturas`

### Comportamiento de la sincronización

- `sync.py` trae **todos** los registros de prefacturas desde la API de Siesa, paginando automáticamente.
- **Reemplazo total** (DELETE + INSERT) en cada sincronización: garantiza que prefacturas anuladas o corregidas en Siesa se reflejen sin registros fantasma.
- Actualiza también un catálogo de clientes con **upsert** (preservando campos manuales: Tipo OC, Observaciones, Links).
- Ejecuta un respaldo de la BD antes de cada sincronización (ver [Respaldo automático](#respaldo-automático)).
- Con este volumen de datos (~1,200 registros), el costo de borrar y recargar todo es insignificante (milisegundos).

---

## Envío de correos (Gmail API)

Cada usuario conecta **su propia cuenta de Gmail** para enviar correos desde la app. La app nunca ve ni guarda la contraseña — solo un permiso limitado a "enviar correos" (scope `gmail.send`). No puede leer la bandeja de entrada.

### 1. Crear las credenciales de Google Cloud (una sola vez, para todo el equipo)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/) y crea un proyecto nuevo (o usa uno existente).
2. En "APIs y servicios" → "Biblioteca", busca y habilita **Gmail API**.
3. En "APIs y servicios" → "Pantalla de consentimiento OAuth":
   - Tipo de usuario: **Externo** (a menos que tengan Google Workspace, en cuyo caso pueden usar "Interno" — ver nota abajo).
   - Completa el nombre de la app y tu correo de contacto.
   - En "Usuarios de prueba", agrega **los correos Gmail de los usuarios** que van a enviar correos.
4. En "APIs y servicios" → "Credenciales" → "Crear credenciales" → "ID de cliente de OAuth":
   - Tipo de aplicación: **Aplicación de escritorio**.
   - Copia el **Client ID** y el **Client Secret** que te da.
5. Agrégalos a `.streamlit/secrets.toml`:
   ```toml
   [gmail]
   client_id = "tu_client_id.apps.googleusercontent.com"
   client_secret = "tu_client_secret"
   ```

### 2. Cada usuario conecta su cuenta (una vez por persona)

Con el venv activado:

```powershell
python conectar_gmail.py
```

Va a pedir tu usuario de la app, luego abre el navegador para que inicies sesión con la cuenta de Gmail que quieres usar y aceptes el permiso. El refresh token se almacena en la tabla `gmail_tokens` de la BD.

### ⚠️ Nota importante sobre la pantalla de consentimiento en modo "Testing"

Si dejas la pantalla de consentimiento OAuth en modo **"Testing"** (lo normal para un proyecto pequeño sin verificar por Google), los `refresh_token` que emite Google **expiran cada 7 días** — pasado ese tiempo, cada usuario tendría que volver a correr `conectar_gmail.py`.

- Si tienen **Google Workspace** (correos de dominio propio, no @gmail.com sueltos), pueden poner el tipo de usuario en **"Interno"** en vez de "Externo" — esto elimina el límite de 7 días y no requiere verificación de Google.
- Si usan cuentas @gmail.com personales, la alternativa es solicitar la verificación de la app ante Google (proceso más largo), o simplemente aceptar reconectar cada semana corriendo el script de nuevo.

### Características del envío de correos

- **Soporte de threading**: reenvíos aparecen en la misma conversación de correo para el destinatario, usando cabeceras RFC 822 (`Message-ID`, `In-Reply-To`, `References`).
- **Adjuntos**: límite de 20 MB total por correo.
- **Separación To/CC**: el primer correo de la lista va en "Para", el resto en "CC".
- **Auditoría completa**: cada envío queda registrado en `envios_correo` con: quién envió, cuándo, a quién, qué prefactura, adjuntos, IDs de Gmail (`message_id`, `thread_id`).

---

## Arquitectura y diseño

### Flujo de datos

```
Siesa Cloud API  ──sync.py──>  SQLite (local)  ──app.py / pages──>  Usuario
                                    │
                                    ├── backup.py (respaldo diario)
                                    └── gmail_client.py (envío de correos)
```

1. **`sync.py`** trae todos los datos de Siesa (paginando automáticamente según `total_páginas` que informa la propia API) y **reemplaza** el contenido de la tabla `prefacturas` en SQLite.
2. **`app.py`** y las páginas **nunca llaman a Siesa directamente** — solo leen de SQLite. Por eso el historial de cliente es instantáneo, y los KPIs siempre reflejan el total real (no solo una página de 100 registros).
3. La selección de un cliente en la tabla principal guarda su NIT en `st.session_state` y navega automáticamente a la página de historial (`st.switch_page`), donde se hace un `SELECT ... WHERE f200_nit = ?` contra un índice — de ahí la velocidad.

### Decisiones de diseño

| Decisión | Justificación |
|---|---|
| **SQLite, no Postgres** | Con 3 usuarios y ~1,200 registros no hace falta un motor de base de datos con servidor. Si el equipo crece o el volumen sube a cientos de miles de filas, migrar tiene sentido. |
| **Pandas, no Polars** | El cuello de botella nunca fue el cómputo (los datos son pequeños), era la latencia de red contra la API. Con los datos ya en SQLite, pandas sobra y de más. |
| **Reemplazo total en cada sync, no upsert incremental** | Si una prefactura se anula o corrige en Siesa, la siguiente sincronización lo refleja sin dejar registros "fantasma". Con este volumen de datos el costo es insignificante (milisegundos). |
| **Envío de correo vía Gmail API, no mailto** | Cada usuario conecta su propia cuenta (scope limitado a "enviar", nunca a leer), y cada envío queda auditado en `envios_correo` — quién envió qué, cuándo, y a quién — con soporte de threading para que un reenvío aparezca en la misma conversación de correo. |
| **Campos manuales preservados en sync** | Los campos Tipo OC, Observaciones y Links se actualizan solo por el usuario, nunca por la sincronización desde Siesa. Esto permite enriquecer la información del cliente sin perderla. |

---

## Modelos de datos

### Tabla `prefacturas` (principal, reemplazada en cada sync)

| Columna | Tipo | Descripción |
|---|---|---|
| `prefactura` | TEXT PK | Número de prefactura |
| `f310_referencia` | TEXT | Referencia |
| `f310_numero_orden_compra` | TEXT | Número de orden de compra |
| `f310_vlr_bruto` | REAL | Valor bruto |
| `f310_vlr_dscto` | REAL | Descuento |
| `f310_vlr_imp` | REAL | Impuesto |
| `f310_vlr_neto` | REAL | Valor neto |
| `fecha_creacion` | TEXT (ISO) | Fecha de creación |
| `fecha_aprovacion` | TEXT (ISO) | Fecha de aprobación |
| `fecha_anulado` | TEXT (ISO) | Fecha de anulación |
| `fecha_facturacion` | TEXT (ISO) | Fecha de facturación |
| `factura` | TEXT | Número de factura |
| `f200_nit` | TEXT | NIT del cliente |
| `f200_razon_social` | TEXT | Razón social |
| `f015_contacto` | TEXT | Contacto |
| `f015_telefono` | TEXT | Teléfono |
| `f015_celular` | TEXT | Celular |
| `f015_email` | TEXT | Email(s) separados por `;` |
| `tipo_cliente` | TEXT | Tipo de cliente |
| `f310_id_cond_pago` | TEXT | Condición de pago |
| `f310_id_moneda_docto` | TEXT | Moneda (COP/USD) |
| `f310_notas` | TEXT | Notas de Siesa |
| `estado` | TEXT | **Calculado**: "Sin Facturar", "Facturada" o "Anulada" |
| `actualizado_en` | TEXT | Timestamp de última actualización |

**Índices**: `idx_prefacturas_nit` (sobre `f200_nit`), `idx_prefacturas_estado` (sobre `estado`).

#### Regla de negocio: determinación de estado

```python
if fecha_anulado tiene valor:   -> "Anulada"
elif factura tiene valor:       -> "Facturada"
else:                          -> "Sin Facturar"
```

Se consideran "vacíos" no solo `NaN`, sino también cadenas `"-"`, `"n/a"`, `"null"`, `""`, etc.

### Tabla `clientes` (catálogo, upsert preservando campos manuales)

| Columna | Tipo | Origen |
|---|---|---|
| `nit` | TEXT PK | Siesa |
| `razon_social` | TEXT | Siesa |
| `contacto` | TEXT | Siesa |
| `telefono` | TEXT | Siesa |
| `celular` | TEXT | Siesa |
| `email` | TEXT | Siesa |
| `direccion` | TEXT | Siesa |
| `pais` | TEXT | Siesa |
| `moneda` | TEXT | Siesa |
| `tipo_oc` | TEXT (default `''`) | **Manual** — nunca se sobreescribe en sync |
| `observaciones` | TEXT (default `''`) | **Manual** — nunca se sobreescribe en sync |
| `links` | TEXT (default `''`) | **Manual** — nunca se sobreescribe en sync |
| `actualizado_en_siesa` | TEXT | Siesa |
| `actualizado_en_usuario` | TEXT | Manual |

### Tabla `usuarios`

| Columna | Tipo |
|---|---|
| `username` | TEXT PK |
| `nombre_completo` | TEXT |
| `password_hash` | TEXT |
| `salt` | TEXT |
| `creado_en` | TEXT |

### Tabla `preferencias_usuario`

| Columna | Tipo |
|---|---|
| `username` | TEXT PK (FK → usuarios) |
| `columnas_json` | TEXT (JSON array) |
| `filtro_estado` | TEXT |
| `anios_json` | TEXT (JSON array) |
| `meses_json` | TEXT (JSON array) |
| `actualizado_en` | TEXT |

### Tabla `gmail_tokens`

| Columna | Tipo |
|---|---|
| `username` | TEXT PK (FK → usuarios) |
| `refresh_token` | TEXT |
| `correo_autorizado` | TEXT |
| `autorizado_en` | TEXT |

### Tabla `envios_correo`

| Columna | Tipo |
|---|---|
| `id` | INTEGER PK AUTOINCREMENT |
| `prefactura` | TEXT NOT NULL |
| `username` | TEXT NOT NULL |
| `destinatario_to` | TEXT |
| `destinatarios_cc` | TEXT |
| `asunto` | TEXT |
| `adjuntos` | TEXT |
| `message_id_rfc822` | TEXT |
| `gmail_message_id` | TEXT |
| `gmail_thread_id` | TEXT |
| `gmail_account_usado` | TEXT |
| `enviado_en` | TEXT |

**Índice**: `idx_envios_prefactura` (sobre `prefactura`).

### Tabla `sync_metadata`

| Columna | Tipo |
|---|---|
| `id` | INTEGER PK (CHECK id=1) |
| `ultima_sincronizacion` | TEXT |
| `total_registros` | INTEGER |

---

## Scripts CLI

### `crear_usuario.py`

Script interactivo por consola para dar de alta o actualizar usuarios.

```powershell
python crear_usuario.py
```

Pide: usuario, nombre completo, y contraseña (con confirmación). Las contraseñas se almacenan con hash PBKDF2 (200,000 iteraciones + salt aleatorio). La comparación en login usa `secrets.compare_digest` para evitar timing attacks.

### `conectar_gmail.py`

Script para que cada usuario autorice su cuenta de Gmail vía OAuth.

```powershell
python conectar_gmail.py
```

Abre el navegador para que el usuario inicie sesión y acepte el permiso `gmail.send`. El refresh token se almacena en la tabla `gmail_tokens`. Solo se ejecuta una vez por usuario (o cada 7 días si el proyecto está en modo Testing).

### `sync.py`

Sincronización de datos desde Siesa Cloud. Ejecutable desde la línea de comandos o programado con cron/Task Scheduler.

```powershell
python sync.py
```

Opcionalmente acepta argumentos para logging detallado.

### `control_prefacturas.py` (legacy)

Versión anterior/alternativa del sistema que consultaba la API de Siesa directamente (sin base de datos local), con paginación manual. **No forma parte de la arquitectura actual** pero se mantiene en el repositorio por referencia.

---

## Respaldo automático

El módulo `backup.py` crea un respaldo de la base de datos antes de cada sincronización:

- **Ubicación**: `data/backups/prefacturas_YYYYMMDD.db`
- **Retención**: conserva los últimos 30 días, elimina los más antiguos automáticamente.
- **Ejecución**: se ejecuta como parte de cada sincronización (`sync.py`), tanto manual como automática.

---

## Búsqueda fuzzy

El módulo `search.py` utiliza la librería `rapidfuzz` (algoritmo `partial_ratio`) para buscar tolerando:

- **Tildes y acentos**: busca "empresa" y encuentra "Empresa S.A.S."
- **Errores de tipeo**: busca "clinte" y encuentra "Cliente"
- **Búsqueda parcial**: busca por NIT, razón social, número de prefactura, o nombre de contacto

El umbral de similitud es 70/100. La búsqueda combina resultados exactos (优先) con resultados fuzzy para máxima relevancia.

---

## Solución de problemas

### La app no arranca

```
ModuleNotFoundError: No module named 'streamlit'
```

Asegúrate de tener el entorno virtual activado y las dependencias instaladas:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Error de autenticación con Siesa

Verifica que las credenciales en `.streamlit/secrets.toml` sean correctas y que la API de Siesa esté disponible.

### Los correos no se envían

1. Verifica que el usuario haya ejecutado `conectar_gmail.py` y haya autorizado su cuenta.
2. Si el refresh token expiró (cada 7 días en modo Testing), vuelve a ejecutar `conectar_gmail.py`.
3. Verifica que `client_id` y `client_secret` en `secrets.toml` sean correctos.

### La sincronización no trae datos

1. Verifica la conectividad de red.
2. Revisa el log de sincronización si ejecutaste `sync.py` manualmente.
3. Verifica que la API de Siesa no esté en mantenimiento.

### La BD está corrupta o vacía

1. Los respaldos diarios están en `data/backups/`. Copia el más reciente a `data/prefacturas.db`.
2. Si no hay respaldos, ejecuta `sync.py` para reconstruir la base desde cero.

---

## Licencia

Proyecto interno. No distribuir externamente.
