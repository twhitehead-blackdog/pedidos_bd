# -*- coding: utf-8 -*-
import os
import json
import xmlrpc.client
import pandas as pd
import time
import pickle
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

MINIMOS_ACCESORIOS = {
    "grande": {
        "higiene/pampers": 10, "higiene/bolsas de pupu": 10, "higiene/shampoo": 6,
        "higiene/topicos - cremas, perfume": 6, "higiene/pads": 10, "higiene/dental": 6,
        "higiene/wipes": 6, "higiene/cepillos": 6, "higiene/otros": 6, "higiene/hogar": 4,
        "higiene/gatos - arenero": 2, "bowls y feeders": 4, "juguetes": 6, "medias": 6,
        "pecheras/correas/leashes": 4, "camas": 2, "kennel": 2, "bolsos": 2, "arena": 6,
        "gimnasios y rascadores": 2, "carritos": 1, "default": 3
    },
    "mediana": {
        "higiene/pampers": 8, "higiene/bolsas de pupu": 8, "higiene/shampoo": 6,
        "higiene/topicos - cremas, perfume": 6, "higiene/pads": 8, "higiene/dental": 6,
        "higiene/wipes": 6, "higiene/cepillos": 6, "higiene/otros": 6, "higiene/hogar": 4,
        "higiene/gatos - arenero": 2, "bowls y feeders": 4, "juguetes": 6, "medias": 6,
        "pecheras/correas/leashes": 4, "camas": 2, "kennel": 2, "bolsos": 2, "arena": 6,
        "gimnasios y rascadores": 2, "carritos": 1, "default": 3
    },
    "chica": {
        "higiene/pampers": 8, "higiene/bolsas de pupu": 8, "higiene/shampoo": 6,
        "higiene/topicos - cremas, perfume": 6, "higiene/pads": 8, "higiene/dental": 6,
        "higiene/wipes": 6, "higiene/cepillos": 6, "higiene/otros": 6, "higiene/hogar": 4,
        "higiene/gatos - arenero": 2, "bowls y feeders": 4, "juguetes": 4, "medias": 6,
        "pecheras/correas/leashes": 4, "camas": 1, "kennel": 1, "bolsos": 1, "arena": 6,
        "gimnasios y rascadores": 1, "carritos": 1, "default": 2
    }
}

COLUMNS_OUT = ["Código", "Referencia Interna", "Descripción", "Cantidad", "Categoría"]

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

def crear_item_producto(product_info, cantidad, categoria_nombre, es_nuevo=False):
    return {
        "Código": product_info.get("barcode", ""),
        "Referencia Interna": product_info.get("default_code", ""),
        "Descripción": product_info.get("nombre_correcto", ""),
        "Cantidad": cantidad,
        "Categoría": categoria_nombre
    }

def determinar_tipo_producto(categoria_nombre, nombre_producto):
    categoria = categoria_nombre.lower()
    nombre = nombre_producto.lower()
    if "insumo" in categoria or "gasto" in categoria:
        return "insumos"
    if "alimento" in categoria or "medicado" in categoria or "treat" in categoria:
        return "alimentos"
    elif "accesorio" in categoria:
        return "accesorios"
    elif "medicamento" in categoria:
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
    if any(x in nombre for x in ["navidad", "xmas", "santa", "noel", "halloween", "bruja", "spooky", "terror"]):
        return True
    if "navidad" in categoria or "halloween" in categoria:
        return True
    return False

def mes_envio_temporada(product_info):
    nombre = product_info.get("nombre_correcto", "").lower()
    categoria = product_info.get("categ_id", ["", ""])[1].lower()
    if "navidad" in nombre or "xmas" in nombre or "santa" in nombre or "noel" in nombre or "navidad" in categoria:
        return 11  # Noviembre
    if "halloween" in nombre or "bruja" in nombre or "spooky" in nombre or "terror" in nombre or "halloween" in categoria:
        return 9  # Octubre (enviar en septiembre)
    return None

def sugerido_top3_6meses(linea):
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
    top3 = sorted(ventas, reverse=True)[:3]
    return int(round(sum(top3) / 3))

def aplicar_reglas_cantidad(product_info, forecast, stock_tienda, tienda, tipo, subcategoria=None):
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

    cantidad = int(forecast)

    # 1. Medicamentos: mínimo 1, en unidad de compra
    if tipo == "medicamentos":
        if cantidad > 0:
            pass  # El sugerido manda
        else:
            if stock_tienda < 1:
                cantidad = 1 - stock_tienda
            else:
                cantidad = 0
        if unidad_repos > 1 and cantidad % unidad_repos != 0:
            cantidad = ((cantidad // unidad_repos) + 1) * unidad_repos
        return cantidad

    # 2. Latas de comida: múltiplos de 6
    if tipo == "alimentos" and subcategoria and "lata" in subcategoria.lower():
        if cantidad > 0:
            if cantidad % 6 != 0:
                cantidad = ((cantidad // 6) + 1) * 6
        else:
            if stock_tienda < 6:
                cantidad = 6 - stock_tienda
                if cantidad < 0:
                    cantidad = 0
            else:
                cantidad = 0
        return cantidad

    # 3. Juguetes Interactivos: mínimo 2
    if tipo == "accesorios" and subcategoria and "juguete" in subcategoria.lower() and "interactivo" in subcategoria.lower():
        if cantidad > 0:
            pass
        else:
            if stock_tienda < 2:
                cantidad = 2 - stock_tienda
            else:
                cantidad = 0
        return cantidad

    # 4. Accesorios por tipo de tienda
    if tipo == "accesorios":
        sub = (subcategoria or "").lower()
        if "pechera" in sub or "correa" in sub or "leash" in sub:
            sub = "pecheras/correas/leashes"
        minimos = MINIMOS_ACCESORIOS.get(tipo_tienda, {})
        minimo = minimos.get(sub, minimos.get("default", 2))
        if cantidad > 0:
            pass  # El sugerido manda
        else:
            if stock_tienda < minimo:
                cantidad = minimo - stock_tienda
            else:
                cantidad = 0
        if unidad_repos > 1 and cantidad % unidad_repos != 0:
            cantidad = ((cantidad // unidad_repos) + 1) * unidad_repos
        return cantidad

    # Para otros casos, redondear a múltiplo de unidad de compra
    if cantidad > 0:
        if unidad_repos > 1 and cantidad % unidad_repos != 0:
            cantidad = ((cantidad // unidad_repos) + 1) * unidad_repos
    else:
        if stock_tienda < unidad_repos:
            cantidad = unidad_repos - stock_tienda
        else:
            cantidad = 0

    return cantidad

# ---------------------------------------------
# CONEXIÓN ODOO Y UTILIDADES
# ---------------------------------------------

class OdooConnection:
    def __init__(self):
        self.url = 'https://blackdogpanama.odoo.com'
        self.db = 'dev-psdc-blackdogpanama-prod-3782039'
        self.username = 'mercadeo@blackdogpanama.com'
        self.password = 'Emanuel1010.'
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
                    'product_tmpl_id'
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

        # Productos nuevos agregados
        f.write("🆕 PRODUCTOS NUEVOS AGREGADOS\n")
        f.write("-" * 50 + "\n")
        for producto in productos_nuevos:
            f.write(f"• {producto['Descripción']} - Categoría: {producto['Categoría']}\n")

        f.write("\n" + "=" * 80 + "\n\n")

        # Totales por tienda
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

        # Productos con qty_to_order = 0 pero recomendados
        f.write("❗ PRODUCTOS NO ORDENADOS MANUALMENTE (qty_to_order = 0 pero recomendados)\n")
        f.write("-" * 50 + "\n")
        for tienda, productos in sorted(productos_con_qty_to_order.items()):
            if productos:
                f.write(f"\n{tienda.upper()}\n")
                for prod in productos:
                    f.write(f"• {prod['nombre']} - Cantidad Recomendada: {prod['cantidad_recomendada']}\n")

# ---------------------------------------------
# PROCESAMIENTO PRINCIPAL
# ---------------------------------------------

def procesar_pedidos_odoo(output_dir="Pedidos_Sugeridos"):
    print("🚀 Iniciando proceso de pedidos sugeridos...")
    os.makedirs(output_dir, exist_ok=True)

    # Cargar datos
    odoo, all_lines, all_product_ids = cargar_datos_reposicion()
    print(f"🔎 Consultando información de {len(all_product_ids)} productos únicos...")
    product_dict = get_product_info_with_cache(odoo, all_product_ids)

    # Inicializar estructuras
    agrupado = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    masters = defaultdict(lambda: defaultdict(list))
    estadisticas_tiendas = defaultdict(lambda: defaultdict(int))
    productos_con_qty_to_order = defaultdict(list)
    productos_nuevos = []

    # Ley del rico y del pobre y reglas de negocio
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

        # 1. Productos de temporada
        if es_producto_temporada(product_info):
            mes_envio = mes_envio_temporada(product_info)
            mes_actual = datetime.now().month
            if mes_envio and mes_actual == mes_envio:
                stock_bodega = int(lineas[0].get('qty_in_wh', 0) or 0)
                tiendas_activas = [l['shop_pos_id'][1].strip().lower() for l in lineas]
                if len(tiendas_activas) > 0 and stock_bodega > 0:
                    cantidad_por_tienda = stock_bodega // len(tiendas_activas)
                    if cantidad_por_tienda > 0:
                        for l in lineas:
                            tienda = l['shop_pos_id'][1].strip().lower()
                            item = crear_item_producto(product_info, cantidad_por_tienda, categoria_nombre)
                            ruta = obtener_ruta(tienda)
                            agrupado[ruta][tienda][tipo].append(item)
                            if tipo in ["alimentos", "accesorios"]:
                                masters[ruta][tipo].append(item)
                            estadisticas_tiendas[tienda][tipo] += cantidad_por_tienda
                    # No agregar más líneas para este producto
                continue

        # 2. Control de stock: no sobrepasar stock de bodega, priorizar tiendas con mejores ventas
        total_solicitado = sum(
            float(l.get('qty_to_order') or l.get('qty_to_order_recommend') or 0)
            for l in lineas
        )
        stock_bodega = float(lineas[0].get('qty_in_wh', 0) or 0)
        if stock_bodega <= 0 or total_solicitado <= 0:
            continue

        # Ordenar líneas por ventas históricas (total_avg) descendente
        lineas.sort(key=lambda l: float(l.get('total_avg') or 0), reverse=True)
        disponible = int(stock_bodega)
        for l in lineas:
            tienda = l['shop_pos_id'][1].strip().lower()
            stock_tienda = int(l.get('qty_to_hand') or 0)

            # Sugerido Odoo y sugerido top 3 meses
            sugerido_odoo = int(l.get('qty_to_order') or l.get('qty_to_order_recommend') or 0)
            sugerido_top3 = sugerido_top3_6meses(l)
            forecast = max(sugerido_odoo, sugerido_top3)

            # 3. Productos nuevos
            if es_producto_nuevo(product_info, stock_tienda):
                cantidad_final = 5
                productos_nuevos.append(crear_item_producto(product_info, cantidad_final, categoria_nombre))
            else:
                cantidad_final = aplicar_reglas_cantidad(
                    product_info=product_info,
                    forecast=forecast,
                    stock_tienda=stock_tienda,
                    tienda=tienda,
                    tipo=tipo,
                    subcategoria=categoria_nombre
                )

            # No sobrepasar stock de bodega
            if cantidad_final > disponible:
                cantidad_final = disponible
            if cantidad_final <= 0:
                continue
            disponible -= cantidad_final

            item = crear_item_producto(product_info, cantidad_final, categoria_nombre)
            ruta = obtener_ruta(tienda)
            agrupado[ruta][tienda][tipo].append(item)
            if tipo in ["alimentos", "accesorios"]:
                masters[ruta][tipo].append(item)
            estadisticas_tiendas[tienda][tipo] += cantidad_final

            # Seguimiento para log
            qty_to_order = float(l.get('qty_to_order', 0) or 0)
            qty_to_order_recommend = float(l.get('qty_to_order_recommend', 0) or 0)
            if qty_to_order == 0 and qty_to_order_recommend > 0:
                productos_con_qty_to_order[tienda].append({
                    'nombre': nombre,
                    'cantidad_recomendada': qty_to_order_recommend
                })

            if disponible <= 0:
                break  # Ya no hay más stock para repartir

    # Generar archivos por tienda
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

    # Generar archivos MASTER por ruta SOLO para alimentos y accesorios
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

    # Generar log
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