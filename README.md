# Control de Prefacturas

## Estructura

```
proyecto_prefacturas/
├── app.py                        # Página principal: listado, filtros, KPIs, envío de correo
├── pages/
│   ├── 1_Historial_Cliente.py    # Historial + gráfico de facturación del cliente
│   └── 2_Ficha_Cliente.py        # Datos de Siesa + campos manuales (Tipo OC, Observaciones, Links)
├── siesa_client.py                # Único módulo que llama a la API de Siesa
├── gmail_client.py                # Envío de correos + threading (vía Gmail API)
├── conectar_gmail.py              # Script: cada usuario conecta su cuenta de Gmail
├── auth.py                        # Login (usuario/contraseña con hash)
├── crear_usuario.py                # Script: dar de alta usuarios de la app
├── search.py                       # Buscador tolerante a tildes y errores de tipeo
├── reportes.py                     # Agregaciones para gráficos (valor facturado por mes)
├── data.py                        # Normalización y reglas de negocio (estado)
├── db.py                          # Acceso a SQLite (init, guardar, consultar)
├── sync.py                        # Sincroniza Siesa -> SQLite
├── config.py                      # Constantes compartidas
├── data/prefacturas.db            # Base de datos SQLite (se crea sola)
└── requirements.txt
```

## Cómo funciona

1. **`sync.py`** trae todos los datos de Siesa (paginando automáticamente
   según `total_páginas` que informa la propia API) y **reemplaza** el
   contenido de la tabla `prefacturas` en SQLite.
2. **`app.py`** y la página de historial **nunca llaman a Siesa
   directamente** — solo leen de SQLite. Por eso el historial de cliente
   es instantáneo, y los KPIs siempre reflejan el total real (no solo
   una página de 100 registros).
3. La selección de un cliente en la tabla principal guarda su NIT en
   `st.session_state` y navega automáticamente a la página de historial
   (`st.switch_page`), donde se hace un `SELECT ... WHERE f200_nit = ?`
   contra un índice — de ahí la velocidad.

## Configuración de credenciales

Igual que antes, en `.streamlit/secrets.toml`:

```toml
[siesa]
client_id = "..."
ConniKey = "..."
ConniToken = "..."
```

## Mantener los datos sincronizados

**Opción A — manual:** botón "🔄 Sincronizar ahora" en la barra lateral
de la app.

**Opción B — automática (recomendada):** programar `sync.py` para que
corra solo cada cierto tiempo:

```bash
# Linux/cron, cada 15 minutos
*/15 * * * * cd /ruta/al/proyecto && /ruta/al/venv/bin/python sync.py >> sync.log 2>&1
```

En Windows, lo mismo se logra con el Programador de Tareas apuntando a
`python sync.py` con el directorio de trabajo en la carpeta del proyecto.

Con esto los 3 usuarios siempre ven datos frescos sin que nadie tenga que
acordarse de sincronizar manualmente.

## Envío de correos (Gmail API)

Cada usuario conecta **su propia cuenta de Gmail** para enviar correos desde la app. La app nunca ve ni guarda tu contraseña -- solo un permiso limitado a "enviar correos" (no puede leer tu bandeja de entrada).

### 1. Crear las credenciales de Google Cloud (una sola vez, para todo el equipo)

1. Ve a [Google Cloud Console](https://console.cloud.google.com/) y crea un proyecto nuevo (o usa uno existente).
2. En "APIs y servicios" → "Biblioteca", busca y habilita **Gmail API**.
3. En "APIs y servicios" → "Pantalla de consentimiento OAuth":
   - Tipo de usuario: **Externo** (a menos que tengan Google Workspace, en cuyo caso pueden usar "Interno" -- ver nota abajo).
   - Completa el nombre de la app y tu correo de contacto.
   - En "Usuarios de prueba", agrega **los correos Gmail de los 3 usuarios** que van a enviar correos.
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
Va a pedir tu usuario de la app, luego abre el navegador para que inicies sesión con la cuenta de Gmail que quieres usar y aceptes el permiso.

### ⚠️ Nota importante sobre la pantalla de consentimiento en modo "Testing"

Si dejas la pantalla de consentimiento OAuth en modo **"Testing"** (lo normal para un proyecto pequeño sin verificar por Google), los `refresh_token` que emite Google **expiran cada 7 días** -- pasado ese tiempo, cada usuario tendría que volver a correr `conectar_gmail.py`.

- Si tienen **Google Workspace** (correos de dominio propio, no @gmail.com sueltos), pueden poner el tipo de usuario en **"Interno"** en vez de "Externo" -- esto elimina el límite de 7 días y no requiere verificación de Google.
- Si usan cuentas @gmail.com personales, la alternativa es solicitar la verificación de la app ante Google (proceso más largo), o simplemente aceptar reconectar cada semana corriendo el script de nuevo.

## Correr la app

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Decisiones de diseño (por qué se hizo así)

- **SQLite, no Postgres:** con 3 usuarios y ~1,200 registros no hace
  falta un motor de base de datos con servidor. Si el equipo crece o el
  volumen sube a cientos de miles de filas, ahí sí migrar tiene sentido.
- **Pandas, no Polars:** el cuello de botella nunca fue el cómputo (los
  datos son pequeños), era la latencia de red contra la API. Con los
  datos ya en SQLite, pandas sobra y de más.
- **Reemplazo total en cada sync, no upsert incremental:** así, si una
  prefactura se anula o corrige en Siesa, la siguiente sincronización lo
  refleja sin dejar registros "fantasma". Con este volumen de datos el
  costo de borrar y recargar todo es insignificante (milisegundos).
- **Envío de correo vía Gmail API, no mailto:** cada usuario conecta su propia cuenta (scope limitado a "enviar", nunca a leer), y cada envío queda auditado en `envios_correo` -- quién envió qué, cuándo, y a quién -- con soporte de threading para que un reenvío aparezca en la misma conversación de correo para el destinatario, sin importar si lo reenvía la misma persona u otra.
