# -*- coding: utf-8 -*-
import os
import json
import xmlrpc.client
import pandas as pd
import time
import pickle
import streamlit as st
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

# ---------------------------------------------
# CONFIGURACIÓN GENERAL
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
    "global_agresividad": 1.8,
    "natural_greatness": 2.2,
    "vacunas": 1.8,
    "general": 1.5
}

MULTIPLICADORES_TAMANO = {
    "pequeno": 1.4,
    "mediano": 1.2,
    "grande": 1.0
}

MINIMOS_ACCESORIOS = {
    "grande": {
        "higiene/pampers": 12, "higiene/bolsas de pupu": 12, "higiene/shampoo": 8,
        "higiene/topicos - cremas, perfume": 8, "higiene/pads": 12, "higiene/dental": 8,
        "higiene/wipes": 8, "higiene/cepillos": 8, "higiene/otros": 8, "higiene/hogar": 5,
        "higiene/gatos - arenero": 3, "bowls y feeders": 5, "juguetes": 8, "medias": 8,
        "pecheras/correas/leashes": 5, "camas": 3, "kennel": 3, "bolsos": 3, "arena": 8,
        "gimnasios y rascadores": 3, "carritos": 2, "default": 4
    },
    "mediana": {
        "higiene/pampers": 10, "higiene/bolsas de pupu": 10, "higiene/shampoo": 6,
        "higiene/topicos - cremas, perfume": 6, "higiene/pads": 10, "higiene/dental": 6,
        "higiene/wipes": 6, "higiene/cepillos": 6, "higiene/otros": 6, "higiene/hogar": 4,
        "higiene/gatos - arenero": 2, "bowls y feeders": 4, "juguetes": 6, "medias": 6,
        "pecheras/correas/leashes": 4, "camas": 2, "kennel": 2, "bolsos": 2, "arena": 6,
        "gimnasios y rascadores": 2, "carritos": 1, "default": 3
    },
    "chica": {
        "higiene/pampers": 8, "higiene/bolsas de pupu": 8, "higiene/shampoo": 5,
        "higiene/topicos - cremas, perfume": 5, "higiene/pads": 8, "higiene/dental": 5,
        "higiene/wipes": 5, "higiene/cepillos": 5, "higiene/otros": 5, "higiene/hogar": 3,
        "higiene/gatos - arenero": 1, "bowls y feeders": 3, "juguetes": 5, "medias": 5,
        "pecheras/correas/leashes": 3, "camas": 1, "kennel": 1, "bolsos": 1, "arena": 5,
        "gimnasios y rascadores": 1, "carritos": 1, "default": 2
    }
}

COLUMNS_OUT = ["Código", "Referencia Interna", "Descripción", "Cantidad", "Categoría", "Marca"]

# ---------------------------------------------
# FUNCIONES DE NEGOCIO
# ---------------------------------------------

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
        "Categoría": categoria_nombre,
        "Marca": product_info.get("marca", "").lower()
    }

def determinar_tipo_producto(categoria_nombre, nombre_producto):
    categoria = categoria_nombre.lower()
    nombre = nombre_producto.lower()
    if any(palabra in nombre or palabra in categoria for palabra in EXCLUIR_PALABRAS):
        return None
    if "insumo" in categoria or "gasto" in categoria:
        return "insumos"
    if "alimento" in categoria or "medicado" in categoria or "treat" in categoria:
        return "alimentos"
    elif "accesorio" in categoria:
        return "accesorios"
    elif "medicamento" in categoria or "vacuna" in categoria or "vacunas" in categoria:
        return "medicamentos"
    return None

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
        categoria = product_info.get("categ_id", ["", ""])[1].lower()
        if any(x in categoria for x in ["kennel", "cama", "bolso", "gimnasio", "rascador", "carrito"]):
            return False
        return True
    return False

def es_producto_temporada(product_info):
    nombre = product_info.get("nombre_correcto", "").lower()
    categoria = product_info.get("categ_id", ["", ""])[1].lower()
    palabras_temporada = ["navidad", "xmas", "santa", "noel", "halloween", "bruja", "spooky", "terror"]
    if any(palabra in nombre for palabra in palabras_temporada):
        return True
    if any(palabra in categoria for palabra in palabras_temporada):
        return True
    return False

def mes_envio_temporada(product_info):
    nombre = product_info.get("nombre_correcto", "").lower()
    categoria = product_info.get("categ_id", ["", ""])[1].lower()
    if any(x in nombre for x in ["navidad", "xmas", "santa", "noel"]) or "navidad" in categoria:
        return 11  # Noviembre
    if any(x in nombre for x in ["halloween", "bruja", "spooky", "terror"]) or "halloween" in categoria:
        return 9  # Octubre (enviar en septiembre)
    return None

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

def aplicar_reglas_cantidad(product_info, forecast, stock_tienda, tienda, tipo, subcategoria=None, sugerido_odoo=0):
    tipo_tienda = "mediana"
    tienda_l = tienda.lower()
    if tienda_l in TIENDAS_GRANDES:
        tipo_tienda = "grande"
    elif tienda_l in TIENDAS_MEDIANAS:
        tipo_tienda = "mediana"
    elif tienda_l in TIENDAS_CHICAS:
        tipo_tienda = "chica"

    unidad_repos = product_info.get("x_studio_unidad_de_reposicin", 1)
    try:
        unidad_repos = int(unidad_repos)
    except:
        unidad_repos = 1

    marca = product_info.get("marca", "").lower()

    # Definir meses de stock según tipo
    if tipo == "medicamentos" and ("vacuna" in (subcategoria or "").lower() or "vacunas" in (subcategoria or "").lower()):
        meses_stock = 1.5
    elif marca == "natural greatness":
        meses_stock = 2
    else:
        meses_stock = 1

    # Cantidad base es el sugerido por Odoo
    cantidad = sugerido_odoo

    # Ajuste por tamaño
    tamaño_producto = product_info.get("x_studio_tamano", "mediano").lower()
    multiplicador_tamano = MULTIPLICADORES_TAMANO.get(tamaño_producto, 1.0)

    cantidad = cantidad * multiplicador_tamano * MULTIPLICADORES["global_agresividad"]

    # Mínimos por categoría y tienda para accesorios
    if tipo == "accesorios":
        sub = (subcategoria or "").lower()
        if "pechera" in sub or "correa" in sub or "leash" in sub:
            sub = "pecheras/correas/leashes"
        minimos = MINIMOS_ACCESORIOS.get(tipo_tienda, {})
        minimo = minimos.get(sub, minimos.get("default", 3))
        if cantidad < minimo:
            cantidad = minimo

    # Para medicamentos mínimo 1 unidad si no hay stock
    if tipo == "medicamentos":
        if cantidad < 1 and stock_tienda < 1:
            cantidad = 1

    # Para productos nuevos sin stock, mínimo 8 unidades
    if es_producto_nuevo(product_info, stock_tienda):
        cantidad = max(cantidad, 8)

    # Límite máximo: 3 veces el forecast
    cantidad = min(cantidad, forecast * 3)

    # Redondear a múltiplos de unidad de compra
    cantidad = int(round(cantidad))
    if unidad_repos > 1 and cantidad % unidad_repos != 0:
        cantidad = ((cantidad // unidad_repos) + 1) * unidad_repos

    if cantidad < 0:
        cantidad = 0

    return cantidad

class OdooConnection:
    def __init__(self):
        self.url = st.secrets["odoo"]["url"]
        self.db = st.secrets["odoo"]["db"]
        self.username = st.secrets["odoo"]["username"]
        self.password = st.secrets["odoo"]["password"]
        self.uid = None
        self.models = None
        self.connect()

    def connect(self):
        print("🔗 Conectando a Odoo...")
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
        {'fields': ['id', 'name', 'barcode', 'default_code', 'x_studio_unidad_de_reposicin'],
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
                    'marca',
                    'x_studio_tamano'
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
                    product['x_studio_unidad_de_reposicin'] = template.get('x_studio_unidad_de_reposicin', 1)
                else:
                    product['nombre_correcto'] = limpiar_nombre_producto(product.get('name', ''))
                    product['x_studio_unidad_de_reposicin'] = 1

                if 'marca' not in product:
                    product['marca'] = ""

                if 'x_studio_tamano' not in product:
                    product['x_studio_tamano'] = "mediano"

                products_info[product['id']] = product

        except Exception as e:
            print(f"\nError procesando lote {batch_num}: {e}")
            continue

        time.sleep(0.05)

    print("\n✅ Consulta de productos completada")
    return products_info

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

def escribir_log(log_path, agrupado, estadisticas_tiendas, productos_nuevos, productos_con_qty_to_order):
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"LOG DE PEDIDOS SUGERIDOS - {datetime.now()}\n")
        f.write("=" * 80 + "\n\n")

        f.write("🆕 PRODUCTOS NUEVOS AGREGADOS\n")
        f.write("-" * 50 + "\n")
        for producto in productos_nuevos:
            f.write(f"• {producto['Descripción']} - Categoría: {producto['Categoría']}\n")

        f.write("\n" + "=" * 80 + "\n\n")

        f.write("📋 DETALLE DE PRODUCTOS ENVIADOS POR TIENDA\n")
        f.write("-" * 50 + "\n")
        for ruta, tiendas in agrupado.items():
            for tienda, tipos in tiendas.items():
                total = sum(estadisticas_tiendas[tienda].values())
                lineas = {tipo: len([p for p in tipos.get(tipo, []) if p["Cantidad"] > 0]) for tipo in tipos}
                f.write(f"\n🏪 {tienda.upper()}\n")
                for tipo in ["alimentos", "accesorios", "medicamentos", "insumos"]:
                    f.write(f"   {tipo.title()}: {estadisticas_tiendas[tienda].get(tipo, 0)} unidades, {lineas.get(tipo, 0)} líneas\n")
                f.write(f"   TOTAL: {total} unidades, {sum(lineas.values())} líneas\n")

        f.write("\n" + "=" * 80 + "\n\n")

        f.write("❗ PRODUCTOS NO ORDENADOS MANUALMENTE (qty_to_order = 0 pero recomendados)\n")
        f.write("-" * 50 + "\n")
        for tienda, productos in sorted(productos_con_qty_to_order.items()):
            if productos:
                f.write(f"\n{tienda.upper()}\n")
                for prod in productos:
                    f.write(f"• {prod['nombre']} - Cantidad Recomendada: {prod['cantidad_recomendada']}\n")

def procesar_pedidos_odoo(output_dir="Pedidos_Sugeridos"):
    print("🚀 Iniciando proceso de pedidos sugeridos...")
    os.makedirs(output_dir, exist_ok=True)

    odoo, all_lines, all_product_ids = cargar_datos_reposicion()
    print(f"🔎 Consultando información de {len(all_product_ids)} productos únicos...")
    product_dict = get_product_info_with_cache(odoo, all_product_ids)

    agrupado = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    masters = defaultdict(lambda: defaultdict(list))
    estadisticas_tiendas = defaultdict(lambda: defaultdict(int))
    productos_con_qty_to_order = defaultdict(list)
    productos_nuevos = []

    print("\n⚖️ Aplicando reglas de negocio y control de stock...")
    lineas_por_producto = defaultdict(list)
    for line in all_lines:
        product_id = line['product_id'][0]
        if line.get('qty_to_order', 0) > 0 or line.get('qty_to_order_recommend', 0) > 0:
            lineas_por_producto[product_id].append(line)

    for product_id, lineas in lineas_por_producto.items():
        product_info = product_dict.get(product_id, {})
        if not product_info or not product_info.get("categ_id"):
            continue
        categoria_nombre = product_info["categ_id"][1]
        nombre = product_info.get("nombre_correcto", "")
        tipo = determinar_tipo_producto(categoria_nombre, nombre)
        if not tipo:
            continue

        if es_producto_temporada(product_info):
            continue

        total_solicitado = sum(
            float(l.get('qty_to_order') or l.get('qty_to_order_recommend') or 0)
            for l in lineas
        )
        stock_bodega = float(lineas[0].get('qty_in_wh', 0) or 0)
        if stock_bodega <= 0 or total_solicitado <= 0:
            continue

        lineas.sort(key=lambda l: float(l.get('total_avg') or 0), reverse=True)
        disponible = int(stock_bodega)
        for l in lineas:
            tienda = l['shop_pos_id'][1].strip().lower()
            stock_tienda = int(l.get('qty_to_hand') or 0)
            sugerido_odoo = int(l.get('qty_to_order') or l.get('qty_to_order_recommend') or 0)
            sugerido_top2 = sugerido_top2_6meses(l)
            forecast = max(sugerido_odoo, sugerido_top2)

            if es_producto_nuevo(product_info, stock_tienda):
                cantidad_final = max(8, aplicar_reglas_cantidad(product_info, forecast, stock_tienda, tienda, tipo, categoria_nombre, sugerido_odoo))
                productos_nuevos.append(crear_item_producto(product_info, cantidad_final, categoria_nombre))
            else:
                cantidad_final = aplicar_reglas_cantidad(
                    product_info=product_info,
                    forecast=forecast,
                    stock_tienda=stock_tienda,
                    tienda=tienda,
                    tipo=tipo,
                    subcategoria=categoria_nombre,
                    sugerido_odoo=sugerido_odoo
                )

            if cantidad_final <= 0:
                continue

            item = crear_item_producto(product_info, cantidad_final, categoria_nombre)
            ruta = obtener_ruta(tienda)
            agrupado[ruta][tienda][tipo].append(item)
            if tipo in ["alimentos", "accesorios"]:
                masters[ruta][tipo].append(item)
            estadisticas_tiendas[tienda][tipo] += cantidad_final

            qty_to_order = float(l.get('qty_to_order', 0) or 0)
            qty_to_order_recommend = float(l.get('qty_to_order_recommend', 0) or 0)
            if qty_to_order == 0 and qty_to_order_recommend > 0:
                productos_con_qty_to_order[tienda].append({
                    'nombre': nombre,
                    'cantidad_recomendada': qty_to_order_recommend
                })

    secuencia_global = get_next_global_sequence()
    print(f"\n🗂️ Secuencia global para esta ejecución: {secuencia_global}")

    for ruta, tiendas in agrupado.items():
        ruta_dir = os.path.join(output_dir, f"{ruta}_PEDIDO_{secuencia_global}")
        os.makedirs(ruta_dir, exist_ok=True)

        for tienda, tipos in tiendas.items():
            nombre_tienda = tienda.title().replace(" ", "_")
            carpeta_tienda = os.path.join(ruta_dir, nombre_tienda)
            os.makedirs(carpeta_tienda, exist_ok=True)
            for tipo, productos in tipos.items():
                if productos:
                    df = pd.DataFrame(productos)[COLUMNS_OUT]
                    nombre_archivo = f"{nombre_tienda}_{ruta}_{tipo.upper()}_{secuencia_global}.xlsx"
                    exportar_excel_pedido(df, os.path.join(carpeta_tienda, nombre_archivo))
                    print(f"    └─ {nombre_archivo} ({len(df)} productos)")

    for ruta, tipos in masters.items():
        ruta_dir = os.path.join(output_dir, f"{ruta}_PEDIDO_{secuencia_global}")
        os.makedirs(ruta_dir, exist_ok=True)
        for tipo_master in ["alimentos", "accesorios"]:
            productos_master = [p for p in tipos[tipo_master] if p["Cantidad"] > 0]
            if productos_master:
                productos_consolidados = generar_master_consolidado(productos_master)
                df_master = pd.DataFrame(productos_consolidados)[COLUMNS_OUT]
                master_filename = f"MASTER_{tipo_master.upper()}_{ruta}_{secuencia_global}.xlsx"
                master_path = os.path.join(ruta_dir, master_filename)
                exportar_excel_pedido(df_master, master_path)
                print(f"  📘 {master_filename} ({len(df_master)} productos únicos)")

    log_path = os.path.join(output_dir, f"log_pedidos_{secuencia_global}.txt")
    escribir_log(
        log_path,
        agrupado,
        estadisticas_tiendas,
        productos_nuevos,
        productos_con_qty_to_order
    )

    print("\n✅ Proceso completado. Log generado en:", log_path)

if __name__ == "__main__":
    procesar_pedidos_odoo()