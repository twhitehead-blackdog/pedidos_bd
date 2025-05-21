# -*- coding: utf-8 -*-
import os
import json
import xmlrpc.client
import pandas as pd
import time
import pickle
import math
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# ---------------------------------------------
# CONFIGURACIÓN GENERAL Y CONSTANTES
# ---------------------------------------------

EXCLUIR_PALABRAS = ["urna", "ropa mascota", "(copia)"]

RUTAS = {
    "R1": ["brisas del golf", "brisas norte", "villa zaita", "condado del rey"],
    "R2": ["albrook fields", "bella vista", "plaza emporio", "ocean mall", "santa maria"],
    "R3": ["calle 50", "coco del mar", "versalles", "costa verde"]
}

TIENDAS_GRANDES = {"ocean mall", "calle 50", "albrook fields", "brisas del golf", "santa maria", "bella vista"}
TIENDAS_MEDIANAS = {"costa verde", "villa zaita", "condado del rey", "brisas norte", "versalles", "coco del mar"}
TIENDAS_CHICAS = {"plaza emporio"}

MULTIPLICADORES = {
    "global_agresividad": 1.0,
    "natural_greatness": 2.0,
    "vacunas": 1.5,
    "general": 1.0
}

# Multiplicadores por categoría según tamaño de tienda
MULTIPLICADORES_POR_CATEGORIA = {
    "grande": {
        "alimentos": 1.4,
        "accesorios": 1.1,
        "medicamentos": 1.3,
        "otros": 1.1,
        "insumos": 1.0
    },
    "mediana": {
        "alimentos": 1.1 ,
        "accesorios": 1.0,
        "medicamentos": 1.0,
        "otros": 1.0,
        "insumos": 1.0
    },
    "chica": {
        "alimentos": 0.8,
        "accesorios": 0.7,
        "medicamentos": 0.8,
        "otros": 0.9,
        "insumos": 1.0
    }
}

# Mínimos para alimentos según tamaño de tienda (simplificado)
MINIMOS_ALIMENTOS = {
    "grande": 1,
    "mediana": 1,
    "chica": 1  # Corregido a 1 para tiendas chicas
}

MINIMOS_ACCESORIOS = {
    "grande": {
        "bowls y feeders": 2, "camas": 1, "kennel": 1, "gimnasios y rascadores": 1,
        "higiene/pampers": 12, "higiene/bolsas de pupu": 12, "higiene/shampoo": 8,
        "higiene/topicos - cremas, perfume": 8, "higiene/pads": 12, "higiene/dental": 8,
        "higiene/wipes": 8, "higiene/cepillos": 8, "higiene/otros": 8, "higiene/hogar": 5,
        "higiene/gatos - arenero": 1, "juguetes": 8, "medias": 8,
        "pecheras/correas/leashes": 5, "bolsos": 3, "arena": 8,
        "carritos": 2, "default": 4
    },
    "mediana": {
        "bowls y feeders": 2, "camas": 1, "kennel": 1, "gimnasios y rascadores": 1,
        "higiene/pampers": 10, "higiene/bolsas de pupu": 10, "higiene/shampoo": 6,
        "higiene/topicos - cremas, perfume": 6, "higiene/pads": 10, "higiene/dental": 6,
        "higiene/wipes": 6, "higiene/cepillos": 6, "higiene/otros": 6, "higiene/hogar": 4,
        "higiene/gatos - arenero": 1, "juguetes": 6, "medias": 6,
        "pecheras/correas/leashes": 4, "bolsos": 2, "arena": 6,
        "carritos": 1, "default": 3
    },
    "chica": {
        "bowls y feeders": 2, "camas": 1, "kennel": 1, "gimnasios y rascadores": 1,
        "higiene/pampers": 8, "higiene/bolsas de pupu": 8, "higiene/shampoo": 5,
        "higiene/topicos - cremas, perfume": 5, "higiene/pads": 8, "higiene/dental": 5,
        "higiene/wipes": 5, "higiene/cepillos": 5, "higiene/otros": 5, "higiene/hogar": 3,
        "higiene/gatos - arenero": 1, "juguetes": 5, "medias": 5,
        "pecheras/correas/leashes": 3, "bolsos": 1, "arena": 5,
        "carritos": 1, "default": 2
    }
}

LIMITES_MAXIMOS = {
    "grande": 200,
    "mediana": 150,
    "chica": 100
}

COLUMNS_OUT = ["Código", "Referencia Interna", "Descripción", "Cantidad", "Categoría"]

SUBCATEGORIAS_MINIMO_1 = [
    "camas", "gimnasios y rascadores", "otros", "kennel", "kennels", "gatos - arenero"
]

NOMBRE_BOLSAS = "BOLSAS BLACK DOG (UNIDAD)"
CANTIDAD_BOLSAS = 50

# Categorías a excluir de la generación de archivos
CATEGORIAS_EXCLUIR = ["insumos", "otros"]

# ---------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------

def es_subcategoria_minimo_1(subcategoria):
    sub = (subcategoria or "").strip().lower()
    for clave in SUBCATEGORIAS_MINIMO_1:
        if clave in sub:
            return True
    return False

def get_next_global_sequence():
    sequence_file = "secuencia_global.json"
    try:
        if os.path.exists(sequence_file):
            with open(sequence_file, 'r') as f:
                data = json.load(f)
            current = data.get("last", 0) + 1
        else:
            current = 1
        with open(sequence_file, 'w') as f:
            json.dump({"last": current}, f)
        return str(current).zfill(3)
    except Exception as e:
        print(f"Error con la secuencia global: {e}")
        return datetime.now().strftime("%Y%m%d_%H%M%S")

def obtener_ruta(tienda):
    tienda = tienda.lower()
    for ruta, tiendas in RUTAS.items():
        if tienda in [t.lower() for t in tiendas]:
            return ruta
    return "SIN_RUTA"

def limpiar_nombre_producto(nombre):
    if not nombre:
        return ""
    nombre = nombre.replace("(copia)", "").strip()
    while "  " in nombre:
        nombre = nombre.replace("  ", " ")
    return nombre

def crear_item_producto(product_info, cantidad, categoria_nombre):
    return {
        "Código": product_info.get("barcode", ""),
        "Referencia Interna": product_info.get("default_code", ""),
        "Descripción": product_info.get("nombre_correcto", ""),
        "Cantidad": cantidad,
        "Categoría": categoria_nombre
    }

def determinar_tipo_producto(categoria_nombre, nombre_producto):
    categoria = str(categoria_nombre).lower()
    nombre = str(nombre_producto).lower()
    if any(palabra in nombre or palabra in categoria for palabra in EXCLUIR_PALABRAS):
        return "otros"
    if "insumo" in categoria or "gasto" in categoria:
        return "insumos"
    if "alimento" in categoria or "medicado" in categoria or "treat" in categoria:
        return "alimentos"
    elif "accesorio" in categoria:
        return "accesorios"
    elif "medicamento" in categoria or "vacuna" in categoria or "vacunas" in categoria:
        return "medicamentos"
    return "otros"

def es_producto_nuevo(product_info, stock_tienda):
    fecha_creacion = product_info.get("create_date")
    if not fecha_creacion:
        return False
    try:
        fecha_creacion = datetime.strptime(fecha_creacion[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return False
    hace_15_dias = datetime.now() - timedelta(days=15)
    if fecha_creacion > hace_15_dias and stock_tienda == 0:
        categoria = ""
        if product_info.get("categ_id"):
            categoria = str(product_info["categ_id"][1]).lower()
        if any(x in categoria for x in ["kennel", "cama", "bolso", "gimnasio", "rascador", "carrito"]):
            return False
        return True
    return False

def es_temporada_activa(product_info):
    nombre = product_info.get("nombre_correcto", "").lower()
    categoria = ""
    if product_info.get("categ_id"):
        categoria = str(product_info["categ_id"][1]).lower()
    hoy = datetime.now()
    is_halloween = product_info.get("x_studio_halloween", False)
    is_navidad = product_info.get("x_studio_navidad", False)
    palabras_navidad = ["navidad", "xmas", "santa", "noel", "holiday", "christmas"]
    palabras_halloween = ["halloween", "bruja", "spooky", "terror"]
    es_navidad = any(x in nombre or x in categoria for x in palabras_navidad)
    es_halloween = any(x in nombre or x in categoria for x in palabras_halloween)
    if is_navidad or es_navidad:
        return hoy.month == 11 or (hoy.month == 12 and hoy.day <= 24)
    if is_halloween or es_halloween:
        return hoy.month == 9 or hoy.month == 10
    return True

def sugerido_top2_6meses(linea):
    ventas = [
        linea.get('qty_month0', 0),
        linea.get('qty_month1', 0),
        linea.get('qty_month2', 0),
        linea.get('qty_month3', 0),
        linea.get('qty_month4', 0),
        linea.get('qty_month5', 0),
    ]
    ventas = [float(v) for v in ventas if v is not None]
    if not ventas:
        return 0
    top2 = sorted(ventas, reverse=True)[:2]
    return int(round(sum(top2) / 2))

def obtener_unidad_reposicion(product_info):
    valor_variante = product_info.get("x_studio_unidad_de_reposicin", None)
    try:
        unidad_variante = int(valor_variante)
        if unidad_variante and unidad_variante > 0:
            return unidad_variante
    except Exception:
        pass
    plantilla = product_info.get("product_template", {})
    valor_plantilla = plantilla.get("x_studio_unidad_de_reposicin", None) if plantilla else None
    try:
        unidad_plantilla = int(valor_plantilla)
        if unidad_plantilla and unidad_plantilla > 0:
            return unidad_plantilla
    except Exception:
        pass
    return 1

def obtener_minimo_categoria(subcategoria, tipo_tienda):
    if not subcategoria:
        return MINIMOS_ACCESORIOS[tipo_tienda]["default"]

    subcategoria = subcategoria.lower()
    for clave, valor in MINIMOS_ACCESORIOS[tipo_tienda].items():
        if clave.lower() in subcategoria:
            return valor

    return MINIMOS_ACCESORIOS[tipo_tienda]["default"]

def obtener_minimo_alimento(tipo_tienda):
    return MINIMOS_ALIMENTOS[tipo_tienda]

def aplicar_reglas_cantidad(
    product_info, forecast, stock_tienda, tienda, tipo, subcategoria=None,
    sugerido_odoo=0, disponible=0, productos_unidad_repos_invalida=None
):
    unidad_repos = obtener_unidad_reposicion(product_info)
    if not isinstance(unidad_repos, int) or unidad_repos < 1:
        if productos_unidad_repos_invalida is not None:
            productos_unidad_repos_invalida.append({
                "producto": product_info.get("nombre_correcto", ""),
                "codigo": product_info.get("default_code", "SIN CODIGO"),
                "categoria": str(product_info.get("categ_id", ["", ""])[1]) if product_info.get("categ_id") else ""
            })
        return 0

    if disponible < unidad_repos:
        return 0

    # Determinar tipo de tienda
    tipo_tienda = "mediana"
    tienda_l = tienda.lower()
    if tienda_l in TIENDAS_GRANDES:
        tipo_tienda = "grande"
    elif tienda_l in TIENDAS_MEDIANAS:
        tipo_tienda = "mediana"
    elif tienda_l in TIENDAS_CHICAS:
        tipo_tienda = "chica"

    # PRIMERO: Calcular cantidad basada en mínimos
    cantidad_minima = 0

    # Aplicar mínimos según tipo de producto
    if tipo == "accesorios" and subcategoria:
        minimo_categoria = obtener_minimo_categoria(subcategoria, tipo_tienda)
        if stock_tienda < minimo_categoria:
            cantidad_minima = minimo_categoria - stock_tienda

    # Aplicar mínimos para alimentos
    elif tipo == "alimentos":
        minimo_alimento = obtener_minimo_alimento(tipo_tienda)
        if stock_tienda < minimo_alimento:
            cantidad_minima = minimo_alimento - stock_tienda

    # SEGUNDO: Calcular cantidad basada en sugerido/forecast con multiplicadores
    cantidad_sugerida = max(sugerido_odoo, forecast, 0)

    # Aplicar multiplicador por categoría según tamaño de tienda
    multiplicador_categoria = MULTIPLICADORES_POR_CATEGORIA[tipo_tienda].get(tipo, 1.0)

    # Aplicar multiplicadores específicos
    categ_id = product_info.get("categ_id", ["", ""])
    categoria_full = " / ".join(str(x) for x in categ_id)
    if "natural greatness" in categoria_full.strip().lower():
        cantidad_sugerida = cantidad_sugerida * MULTIPLICADORES["natural_greatness"] * multiplicador_categoria
    elif "vacuna" in categoria_full.strip().lower():
        cantidad_sugerida = cantidad_sugerida * MULTIPLICADORES["vacunas"] * multiplicador_categoria
    else:
        cantidad_sugerida = cantidad_sugerida * MULTIPLICADORES["global_agresividad"] * multiplicador_categoria

    # TERCERO: Tomar el máximo entre cantidad mínima y cantidad sugerida
    cantidad = max(cantidad_minima, cantidad_sugerida)

    # Si no hay cantidad, asegurar al menos la unidad de reposición
    if cantidad == 0 and disponible >= unidad_repos:
        cantidad = unidad_repos

    # Redondear a múltiplos de la unidad de reposición
    cantidad = int(math.ceil(float(cantidad) / unidad_repos) * unidad_repos)

    # Verificar disponibilidad
    if cantidad > disponible:
        cantidad = (disponible // unidad_repos) * unidad_repos
    if cantidad < unidad_repos:
        return 0

    # Aplicar límites máximos
    limite_maximo = LIMITES_MAXIMOS.get(tipo_tienda, 15)
    if cantidad > limite_maximo:
        cantidad = int(math.ceil(float(limite_maximo) / unidad_repos) * unidad_repos)
        if cantidad > disponible:
            cantidad = (disponible // unidad_repos) * unidad_repos
    if cantidad < unidad_repos:
        return 0

    return int(cantidad)

# ---------------------------------------------
# CONEXIÓN Y DESCARGA DE DATOS DE ODOO
# ---------------------------------------------

class OdooConnection:
    def __init__(self):
        self.url = "https://blackdogpanama.odoo.com"
        self.db = "dev-psdc-blackdogpanama-prod-3782039"
        self.username = "mercadeo@blackdogpanama.com"
        self.password = "Emanuel1010."
        self.uid = None
        self.models = None
        self.connect()

    def connect(self):
        print("🔗 Conectando a Odoo...")
        if not self.url.startswith("http://") and not self.url.startswith("https://"):
            raise ValueError("La URL de Odoo debe empezar con http:// o https://")
        try:
            common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
            self.uid = common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')
            print("✅ Conexión exitosa con Odoo")
        except Exception as e:
            print(f"❌ Error conectando a Odoo: {e}")
            raise

    def execute(self, model, method, *args, **kwargs):
        try:
            return self.models.execute_kw(
                self.db, self.uid, self.password,
                model, method, *args, **kwargs
            )
        except Exception as e:
            print(f"❌ Error ejecutando {method} en {model}: {e}")
            raise

def cargar_datos_reposicion():
    odoo = OdooConnection()
    print("\n📊 Buscando órdenes de reposición en estado borrador...")
    orders = odoo.execute(
        'estimated.replenishment.order',
        'search_read',
        [[('state', '=', 'draft')]],
        {'fields': ['id', 'shop_pos_ids']}
    )
    print(f"└── Encontradas {len(orders)} órdenes en estado borrador\n")

    all_lines = []
    all_product_ids = set()

    for order in orders:
        order_id = order['id']
        try:
            lines = odoo.execute(
                'estimated.replenishment.order.line',
                'search_read',
                [[('order_id', '=', order_id)]],
                {
                    'fields': [
                        'product_id',
                        'qty_to_order',
                        'qty_to_order_recommend',
                        'qty_in_wh',
                        'shop_pos_id',
                        'total_avg',
                        'uom_po_id',
                        'qty_to_hand',
                        'qty_month0', 'qty_month1', 'qty_month2',
                        'qty_month3', 'qty_month4', 'qty_month5'
                    ]
                }
            )
            for line in lines:
                if line.get('product_id') and line.get('shop_pos_id'):
                    all_lines.append(line)
                    all_product_ids.add(line['product_id'][0])
        except Exception as e:
            print(f"Error procesando orden {order_id}: {e}")
            continue

    return odoo, all_lines, all_product_ids

# ---------------------------------------------
# CACHÉ DE PRODUCTOS PARA CONSULTAS RÁPIDAS
# ---------------------------------------------

def get_cache_path():
    return Path("cache/products_cache.pkl")

def get_cache_metadata_path():
    return Path("cache/cache_metadata.json")

def is_cache_valid():
    metadata_path = get_cache_metadata_path()
    if not metadata_path.exists():
        return False
    try:
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        last_update = datetime.fromisoformat(metadata['last_update'])
        return datetime.now() - last_update < timedelta(days=15)
    except Exception as e:
        print(f"Error verificando metadata del caché: {e}")
        return False

def save_products_cache(products_info):
    cache_path = get_cache_path()
    metadata_path = get_cache_metadata_path()
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(cache_path, 'wb') as f:
        pickle.dump(products_info, f)
    metadata = {
        'last_update': datetime.now().isoformat(),
        'products_count': len(products_info)
    }
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f)
    print(f"✅ Caché actualizado con {len(products_info)} productos")

def load_products_cache():
    cache_path = get_cache_path()
    try:
        with open(cache_path, 'rb') as f:
            return pickle.load(f)
    except Exception as e:
        print(f"Error cargando caché: {e}")
        return None

def get_product_info_with_cache(odoo, product_ids):
    if is_cache_valid():
        print("📂 Usando caché de productos...")
        cached_products = load_products_cache()
        if cached_products is not None:
            print(f"✅ Caché cargado con {len(cached_products)} productos")
            return cached_products
    print("🔄 Caché no válido o no existe, consultando productos desde Odoo...")
    products_info = get_product_info_in_batches(odoo, product_ids)
    save_products_cache(products_info)
    return products_info

def get_product_info_in_batches(odoo, product_ids, batch_size=100):
    context_en = {'lang': 'en_US'}
    print("\n📊 Descargando todas las plantillas de productos (en inglés)...")

    all_templates = odoo.execute(
        'product.template',
        'search_read',
        [[]],
        {'fields': [
            'id', 'name', 'barcode', 'default_code',
            'x_studio_unidad_de_reposicin',
            'x_studio_halloween', 'x_studio_navidad'
        ],
         'context': context_en}
    )

    template_by_barcode = {}
    template_by_ref = {}
    template_by_id = {}
    for template in all_templates:
        if template.get('barcode'):
            template_by_barcode[template['barcode']] = template
        if template.get('default_code'):
            template_by_ref[template['default_code']] = template
        template_by_id[template['id']] = template

    print(f"✅ {len(all_templates)} plantillas descargadas")
    products_info = {}
    total_products = len(product_ids)
    product_ids_list = list(product_ids)
    total_batches = (total_products + batch_size - 1) // batch_size

    print(f"\n📊 Progreso de consulta de productos:")
    print(f"   Total productos: {total_products}")
    print(f"   Total lotes: {total_batches}")

    for batch_num, i in enumerate(range(0, total_products, batch_size), 1):
        batch = product_ids_list[i:i + batch_size]
        progress = (batch_num / total_batches) * 100
        print(f"   [{batch_num}/{total_batches}] {progress:.1f}% completado", end='\r')

        try:
            batch_products = odoo.execute(
                'product.product',
                'read',
                [batch],
                {'fields': [
                    'id',
                    'barcode',
                    'default_code',
                    'name',
                    'display_name',
                    'categ_id',
                    'create_date',
                    'product_tmpl_id',
                    'uom_po_id',
                    'x_studio_unidad_de_reposicin'
                ],
                'context': context_en}
            )

            for product in batch_products:
                template = None
                if product.get('product_tmpl_id'):
                    tmpl_id = product['product_tmpl_id'][0]
                    template = template_by_id.get(tmpl_id)
                if not template and product.get('barcode'):
                    template = template_by_barcode.get(product['barcode'])
                if not template and product.get('default_code'):
                    template = template_by_ref.get(product['default_code'])

                if template:
                    product['nombre_correcto'] = limpiar_nombre_producto(template['name'])
                    product['x_studio_halloween'] = template.get('x_studio_halloween', False)
                    product['x_studio_navidad'] = template.get('x_studio_navidad', False)
                    product['product_template'] = template
                else:
                    product['nombre_correcto'] = limpiar_nombre_producto(product.get('name', ''))
                    product['x_studio_halloween'] = False
                    product['x_studio_navidad'] = False
                    product['product_template'] = {}

                products_info[product['id']] = product

        except Exception as e:
            print(f"\nError procesando lote {batch_num}: {e}")
            continue

        time.sleep(0.05)

    print("\n✅ Consulta de productos completada")
    return products_info

# ---------------------------------------------
# EXPORTACIÓN Y LOGS
# ---------------------------------------------

def exportar_excel_pedido(df, path):
    df = df.sort_values(["Categoría", "Descripción"])
    df.to_excel(path, index=False)

def generar_master_consolidado(productos):
    consolidado = {}
    for producto in productos:
        key = (producto["Código"], producto["Referencia Interna"], producto["Descripción"], producto["Categoría"])
        if key in consolidado:
            consolidado[key]["Cantidad"] += producto["Cantidad"]
        else:
            consolidado[key] = producto.copy()
    return list(consolidado.values())

def escribir_log(log_path, productos_nuevos, productos_no_suplidos, resumen_tiendas, productos_unidad_repos_invalida):
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"LOG DE PEDIDOS SUGERIDOS - {datetime.now()}\n")
        f.write("=" * 80 + "\n\n")

        f.write("🆕 PRODUCTOS NUEVOS AGREGADOS\n")
        f.write("-" * 50 + "\n")
        for producto in productos_nuevos:
            f.write(f"• {producto['Descripción']} - Categoría: {producto['Categoría']}\n")

        f.write("\n" + "=" * 80 + "\n\n")

        f.write("❗ PRODUCTOS NO SUPLIDOS POR FALTA DE STOCK EN BODEGA\n")
        f.write("-" * 50 + "\n")
        for p in productos_no_suplidos:
            f.write(f"• {p['producto']} ({p['categoria']}) en {p['tienda'].title()}: Solicitado {p['solicitado']}, Entregado {p['entregado']} ({p['motivo']})\n")

        f.write("\n" + "=" * 80 + "\n\n")

        f.write("📋 RESUMEN DE PRODUCTOS ENVIADOS POR TIENDA\n")
        f.write("-" * 50 + "\n")
        for tienda, resumen in resumen_tiendas.items():
            f.write(f"\n🏪 {tienda.upper()}\n")
            for tipo, cantidad in resumen.items():
                f.write(f"   {tipo.title()}: {cantidad} unidades\n")

        if productos_unidad_repos_invalida:
            f.write("\n" + "=" * 80 + "\n\n")
            f.write("⚠️ PRODUCTOS CON UNIDAD DE REPOSICIÓN INVÁLIDA\n")
            f.write("-" * 50 + "\n")
            for p in productos_unidad_repos_invalida:
                f.write(f"• {p['producto']} ({p['codigo']}) - {p['categoria']}\n")

# ---------------------------------------------
# PROCESO PRINCIPAL DE GENERACIÓN DE PEDIDOS
# ---------------------------------------------

def procesar_pedidos_odoo(output_dir="Pedidos_Sugeridos"):
    print("🚀 Iniciando proceso de pedidos sugeridos...")
    os.makedirs(output_dir, exist_ok=True)

    odoo, all_lines, all_product_ids = cargar_datos_reposicion()
    print(f"🔎 Consultando información de {len(all_product_ids)} productos únicos...")
    product_dict = get_product_info_with_cache(odoo, all_product_ids)

    agrupado = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    masters = defaultdict(lambda: defaultdict(list))
    resumen_tiendas = defaultdict(lambda: defaultdict(int))
    productos_nuevos = []
    productos_no_suplidos = []
    productos_unidad_repos_invalida = []

    print("\n⚖️ Aplicando reglas de negocio y control de stock...")

    lineas_por_producto = defaultdict(list)
    for line in all_lines:
        product_id = line['product_id'][0]
        lineas_por_producto[product_id].append(line)

    for product_id, lineas in lineas_por_producto.items():
        product_info = product_dict.get(product_id, {})
        if not product_info or not product_info.get("categ_id"):
            continue

        categoria_nombre = str(product_info["categ_id"][1]) if len(product_info["categ_id"]) > 1 else ""
        nombre = product_info.get("nombre_correcto", "")
        tipo = determinar_tipo_producto(categoria_nombre, nombre)

        # Saltamos las categorías excluidas
        if tipo in CATEGORIAS_EXCLUIR:
            continue

        if not es_temporada_activa(product_info):
            continue

        stock_bodega = float(lineas[0].get('qty_in_wh', 0) or 0)
        if stock_bodega <= 0:
            continue

        lineas.sort(key=lambda l: sugerido_top2_6meses(l), reverse=True)
        disponible = int(stock_bodega)
        for l in lineas:
            tienda = l['shop_pos_id'][1].strip().lower()
            stock_tienda = int(l.get('qty_to_hand') or 0)
            sugerido = sugerido_top2_6meses(l)

            cantidad_final = aplicar_reglas_cantidad(
                product_info=product_info,
                forecast=sugerido,
                stock_tienda=stock_tienda,
                tienda=tienda,
                tipo=tipo,
                subcategoria=categoria_nombre,
                sugerido_odoo=sugerido,
                disponible=disponible,
                productos_unidad_repos_invalida=productos_unidad_repos_invalida
            )

            if cantidad_final > 0 and es_producto_nuevo(product_info, stock_tienda):
                productos_nuevos.append(crear_item_producto(product_info, cantidad_final, categoria_nombre))

            if cantidad_final > disponible:
                productos_no_suplidos.append({
                    "tienda": tienda,
                    "producto": nombre,
                    "categoria": categoria_nombre,
                    "solicitado": cantidad_final,
                    "entregado": disponible,
                    "motivo": "Stock insuficiente en bodega"
                })
                cantidad_final = disponible
            if cantidad_final <= 0:
                continue
            disponible -= cantidad_final

            item = crear_item_producto(product_info, cantidad_final, categoria_nombre)
            ruta = obtener_ruta(tienda)
            agrupado[ruta][tienda][tipo].append(item)
            if tipo in ["alimentos", "accesorios", "medicamentos"]:  # Incluimos medicamentos en los masters
                masters[ruta][tipo].append(item)
            resumen_tiendas[tienda][tipo] += cantidad_final

            if disponible < obtener_unidad_reposicion(product_info):
                break

    secuencia_global = get_next_global_sequence()
    print(f"\n🗂️ Secuencia global para esta ejecución: {secuencia_global}")

    # --- AGREGAR BOLSAS BLACK DOG (UNIDAD) A TODOS LOS PEDIDOS ---
    id_bolsas = None
    for pid, pinfo in product_dict.items():
        if pinfo.get("nombre_correcto", "").strip().upper() == NOMBRE_BOLSAS:
            id_bolsas = pid
            break

    for ruta, tiendas in agrupado.items():
        ruta_dir = os.path.join(output_dir, f"{ruta}_PEDIDO_{secuencia_global}")
        os.makedirs(ruta_dir, exist_ok=True)

        for tienda, tipos in tiendas.items():
            # Agrega las bolsas a cada pedido de accesorios de cada tienda
            if id_bolsas and "accesorios" in tipos:
                bolsas_info = product_dict[id_bolsas]
                item_bolsas = crear_item_producto(bolsas_info, CANTIDAD_BOLSAS, str(bolsas_info.get("categ_id", ["", ""])[1]) if bolsas_info.get("categ_id") else "")
                accesorios = agrupado[ruta][tienda]["accesorios"]
                ya_esta = any(x["Código"] == item_bolsas["Código"] for x in accesorios)
                if not ya_esta:
                    accesorios.append(item_bolsas)
                    resumen_tiendas[tienda]["accesorios"] += CANTIDAD_BOLSAS

            nombre_tienda = tienda.title().replace(" ", "_")
            carpeta_tienda = os.path.join(ruta_dir, nombre_tienda)
            os.makedirs(carpeta_tienda, exist_ok=True)
            for tipo, productos in tipos.items():
                # Saltamos las categorías excluidas
                if tipo in CATEGORIAS_EXCLUIR:
                    continue

                tipo_archivo = tipo.upper() if tipo else "OTROS"
                if productos:
                    df = pd.DataFrame(productos)[COLUMNS_OUT]
                    nombre_archivo = f"{nombre_tienda}_{ruta}_{tipo_archivo}_{secuencia_global}.xlsx"
                    exportar_excel_pedido(df, os.path.join(carpeta_tienda, nombre_archivo))
                    print(f"    └─ {nombre_archivo} ({len(df)} productos)")

    for ruta, tipos in masters.items():
        ruta_dir = os.path.join(output_dir, f"{ruta}_PEDIDO_{secuencia_global}")
        os.makedirs(ruta_dir, exist_ok=True)
        for tipo_master in ["alimentos", "accesorios", "medicamentos"]:  # Incluimos medicamentos en los masters
            if tipo_master in tipos:
                productos_master = [p for p in tipos[tipo_master] if p["Cantidad"] > 0]
                if productos_master:
                    productos_consolidados = generar_master_consolidado(productos_master)
                    df_master = pd.DataFrame(productos_consolidados)[COLUMNS_OUT]
                    master_filename = f"MASTER_{tipo_master.upper()}_{ruta}_{secuencia_global}.xlsx"
                    master_path = os.path.join(ruta_dir, master_filename)
                    exportar_excel_pedido(df_master, master_path)
                    print(f"  📘 {master_filename} ({len(df_master)} productos únicos)")

    # Generamos el master martes solo con las categorías permitidas
    todos_los_productos = []
    for ruta, tiendas in agrupado.items():
        for tienda, tipos in tiendas.items():
            for tipo, productos in tipos.items():
                if tipo not in CATEGORIAS_EXCLUIR:  # Solo incluimos categorías permitidas
                    todos_los_productos.extend(productos)

    master_martes = generar_master_consolidado(todos_los_productos)
    df_master_martes = pd.DataFrame(master_martes)[COLUMNS_OUT]
    master_martes_path = os.path.join(output_dir, f"MASTER_MARTES_{secuencia_global}.xlsx")
    exportar_excel_pedido(df_master_martes, master_martes_path)
    print(f"\n📘 MASTER_MARTES generado: {master_martes_path} ({len(df_master_martes)} productos únicos)")

    log_path = os.path.join(output_dir, f"log_pedidos_{secuencia_global}.txt")
    escribir_log(
        log_path,
        productos_nuevos,
        productos_no_suplidos,
        resumen_tiendas,
        productos_unidad_repos_invalida
    )

    print("\n✅ Proceso completado. Log generado en:", log_path)

if __name__ == "__main__":
    procesar_pedidos_odoo()