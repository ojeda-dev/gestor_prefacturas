"""Configuración y constantes compartidas por toda la app."""
from pathlib import Path

URL_API = "https://apiqa.siesacloud.com/connekta/siesa/dinamico/consulta/v3.0.1"
ID_COMPANIA = "7661"
DESCRIPCION_CONSULTA = "cloudfleet_Control_Prefacturas"
TAMANO_PAGINA = 100

# Base de datos SQLite local. 3 usuarios internos -> no hace falta un motor
# de servidor (Postgres/MySQL); un archivo local es suficiente y no requiere
# infraestructura adicional.
DB_PATH = Path(__file__).parent / "data" / "prefacturas.db"

# Columnas que esperamos siempre tener disponibles, aunque la API no las
# devuelva en algún registro puntual.
COLUMNAS_ESPERADAS = [
    'fecha_creacion', 'fecha_aprovacion', 'prefactura', 'f310_referencia',
    'f310_numero_orden_compra', 'f310_vlr_bruto', 'f310_vlr_dscto',
    'f310_vlr_imp', 'f310_vlr_neto', 'fecha_anulado', 'fecha_facturacion',
    'factura', 'f200_nit', 'f200_razon_social', 'f015_contacto',
    'f015_telefono', 'f015_celular', 'f015_email', 'tipo_cliente',
    'f310_id_cond_pago', 'f310_id_moneda_docto', 'f310_notas',
    'pais', 'f015_direccion1',
]

COLUMNAS_VISIBLES = {
    'f200_razon_social': 'Cliente',
    'prefactura': 'Prefactura',
    'f310_vlr_neto': 'Valor',
    'estado': 'Estado',
    'fecha_facturacion': 'Fecha Facturacion',
    'factura': 'Factura',
}

# Campos de la ficha de cliente que SÍ vienen de Siesa (se sincronizan
# automáticamente y no son editables a mano).
CAMPOS_CLIENTE_SIESA = {
    'razon_social': 'Razón Social',
    'contacto': 'Contacto',
    'telefono': 'Teléfono',
    'celular': 'Celular',
    'email': 'Email(s)',
    'direccion': 'Dirección',
    'pais': 'País',
    'moneda': 'Moneda',
}

# Campos de la ficha de cliente que llena el usuario manualmente. Estos
# NUNCA se sobreescriben durante una sincronización con Siesa.
CAMPOS_CLIENTE_MANUALES = {
    'tipo_oc': 'Tipo de OC',
    'observaciones': 'Observaciones',
    'links': 'Links',
}

# ---------------------------------------------------------------------------
# Catálogo de columnas que el usuario puede elegir mostrar en el listado
# principal. Cada entrada es: clave -> (etiqueta visible, categoría).
# Las categorías se usan solo para agrupar visualmente el selector.
# ---------------------------------------------------------------------------
COLUMNAS_DISPONIBLES = {
    'f200_razon_social':        ('Cliente', 'Prefactura (Siesa)'),
    'prefactura':               ('Prefactura', 'Prefactura (Siesa)'),
    'f310_referencia':          ('Referencia', 'Prefactura (Siesa)'),
    'f310_numero_orden_compra': ('Núm. Orden de Compra', 'Prefactura (Siesa)'),
    'f310_vlr_bruto':           ('Valor Bruto', 'Prefactura (Siesa)'),
    'f310_vlr_dscto':           ('Descuento', 'Prefactura (Siesa)'),
    'f310_vlr_imp':             ('Impuesto', 'Prefactura (Siesa)'),
    'f310_vlr_neto':            ('Valor Neto', 'Prefactura (Siesa)'),
    'estado':                   ('Estado', 'Prefactura (Siesa)'),
    'fecha_creacion':           ('Fecha Creación', 'Prefactura (Siesa)'),
    'fecha_aprovacion':         ('Fecha Aprobación', 'Prefactura (Siesa)'),
    'fecha_facturacion':        ('Fecha Facturación', 'Prefactura (Siesa)'),
    'fecha_anulado':            ('Fecha Anulación', 'Prefactura (Siesa)'),
    'factura':                  ('Factura', 'Prefactura (Siesa)'),
    'tipo_cliente':             ('Tipo Cliente', 'Prefactura (Siesa)'),
    'f310_id_cond_pago':        ('Condición de Pago', 'Prefactura (Siesa)'),
    'f310_id_moneda_docto':     ('Moneda Doc.', 'Prefactura (Siesa)'),
    'f310_notas':               ('Notas Siesa', 'Prefactura (Siesa)'),
    'f015_contacto':            ('Contacto', 'Cliente (Siesa)'),
    'f015_telefono':            ('Teléfono', 'Cliente (Siesa)'),
    'f015_celular':             ('Celular', 'Cliente (Siesa)'),
    'f015_email':               ('Email(s)', 'Cliente (Siesa)'),
    'direccion':                ('Dirección', 'Cliente (Siesa)'),
    'pais':                     ('País', 'Cliente (Siesa)'),
    'tipo_oc':                  ('Tipo de OC', 'Datos Adicionales'),
    'observaciones':            ('Observaciones', 'Datos Adicionales'),
    'links':                    ('Links', 'Datos Adicionales'),
}

# Columnas visibles por defecto la primera vez que se abre la app
# (mismo set que ya se venía usando antes de que el listado fuera
# personalizable).
COLUMNAS_DEFAULT = ['f200_razon_social', 'prefactura', 'f310_vlr_neto', 'estado', 'fecha_facturacion', 'factura']

# Reglas de formato para el listado dinámico
COLUMNAS_MONEDA = ['f310_vlr_bruto', 'f310_vlr_dscto', 'f310_vlr_imp', 'f310_vlr_neto']
COLUMNAS_FECHA = ['fecha_creacion', 'fecha_aprovacion', 'fecha_facturacion', 'fecha_anulado']


def agrupar_columnas_por_categoria() -> dict:
    """Agrupa COLUMNAS_DISPONIBLES por categoría, preservando el orden de
    aparición tanto de las categorías como de las columnas dentro de cada
    una. Se usa para mostrar el selector de columnas separado por grupo,
    en vez de una sola lista larga con el nombre de la categoría repetido
    en cada opción (lo cual hacía las etiquetas demasiado largas)."""
    agrupado = {}
    for clave, (_etiqueta, categoria) in COLUMNAS_DISPONIBLES.items():
        agrupado.setdefault(categoria, []).append(clave)
    return agrupado