import streamlit as st
import os
import zipfile
import base64
import json
from datetime import datetime, timedelta
from generar import procesar_pedidos_odoo

st.set_page_config(page_title="Pedidos Sugeridos Black Dog", page_icon="favicon.png", layout="centered")

CONFIG_PATH = "config_ajustes.json"
USUARIOS_VALIDOS = st.secrets["usuarios"]

def cargar_configuracion(path=CONFIG_PATH):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        return {"meses_inventario": {"general": 1.0}}

def guardar_configuracion(config, path=CONFIG_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

def show_centered_logo(path="logo.png", width=220):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
        st.markdown(f"<div style='text-align:center; margin-bottom:1.5em;'><img src='data:image/png;base64,{encoded}' width='{width}'></div>", unsafe_allow_html=True)

def get_last_sequence_folder(base_dir="Pedidos_Sugeridos"):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        return [], None
    folders = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    secuencias = [f.split("_")[-1] for f in folders if "PEDIDO_" in f]
    if not secuencias:
        return [], None
    last_seq = max(secuencias)
    last_folders = [f for f in folders if f.endswith(f"PEDIDO_" + last_seq)]
    return last_folders, last_seq

def mostrar_historial():
    historial_path = "Pedidos_Sugeridos/historial.json"
    if os.path.exists(historial_path):
        with open(historial_path, "r", encoding="utf-8") as f:
            hist = json.load(f)
            zip_path = f"Pedidos_Sugeridos/{hist['archivo']}"
            if os.path.exists(zip_path):
                with open(zip_path, "rb") as fzip:
                    zip_b64 = base64.b64encode(fzip.read()).decode()
                    st.markdown(f"""
                        <div style='background:#111; border-left:4px solid #FAB803; padding:1.5em; border-radius:8px; max-width:500px; margin:2em auto;'>
                            <b>📂 Último ZIP generado:</b><br>
                            <ul style='color:#ccc; list-style-position: inside;'>
                                <li><b>Archivo:</b> {hist['archivo']}</li>
                                <li><b>Generado por:</b> {hist['usuario']}</li>
                                <li><b>Fecha:</b> {hist['fecha']}</li>
                            </ul>
                            <div style='text-align:center; margin-top:1em;'>
                                <a download="{hist['archivo']}" href="data:application/zip;base64,{zip_b64}">
                                    <button style='background:#FAB803; color:#181818; font-weight:bold; padding:0.5em 1.5em; border:none; border-radius:6px; font-size:1em; cursor:pointer;'>
                                        Descargar ZIP anterior
                                    </button>
                                </a>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

def mostrar_tiempo_sesion():
    if st.session_state.get('login_time'):
        tiempo_transcurrido = datetime.now() - st.session_state['login_time']
        tiempo_restante = timedelta(minutes=30) - tiempo_transcurrido
        minutos_restantes = int(tiempo_restante.total_seconds() / 60)
        if minutos_restantes > 0:
            st.markdown(f"<div style='text-align:center; font-size:0.9em; color:#888; margin-bottom:1em;'>Tiempo restante de sesión: {minutos_restantes} minutos</div>", unsafe_allow_html=True)

def cerrar_sesion():
    if 'confirmar_cierre' not in st.session_state:
        st.session_state['confirmar_cierre'] = False

    st.markdown("<div style='text-align:right; padding-right:1.5em; margin-bottom:1em;'>", unsafe_allow_html=True)
    if not st.session_state['confirmar_cierre']:
        if st.button("Cerrar sesión", key="logout_button"):
            st.session_state['confirmar_cierre'] = True
    st.markdown("</div>", unsafe_allow_html=True)

    if st.session_state['confirmar_cierre']:
        st.warning("¿Estás seguro de que deseas cerrar sesión?")
        col1, col2 = st.columns(2, gap="large")
        with col1:
            if st.button("Sí, cerrar sesión", key="confirm_logout"):
                st.session_state.clear()
                st.experimental_rerun()
        with col2:
            if st.button("No, cancelar", key="cancel_logout"):
                st.session_state['confirmar_cierre'] = False

# Inicialización estado
if 'logueado' not in st.session_state:
    st.session_state['logueado'] = False
if 'login_time' not in st.session_state:
    st.session_state['login_time'] = None
if 'confirmado' not in st.session_state:
    st.session_state['confirmado'] = False
if 'run' not in st.session_state:
    st.session_state['run'] = False
if 'usuario' not in st.session_state:
    st.session_state['usuario'] = None
if 'nombre_completo' not in st.session_state:
    st.session_state['nombre_completo'] = None
if 'config' not in st.session_state:
    st.session_state['config'] = cargar_configuracion()

# Login y expiración
if not st.session_state['logueado'] or (st.session_state['login_time'] and datetime.now() - st.session_state['login_time'] > timedelta(minutes=30)):
    st.session_state['logueado'] = False
    show_centered_logo("logo.png")
    st.markdown("<h1 style='text-align:center; color:#FAB803;'>Pedidos Black Dog</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#ccc;'>Por favor ingresa tus credenciales para continuar.</p>", unsafe_allow_html=True)

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        contraseña = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Iniciar sesión")

        if submitted:
            if usuario in USUARIOS_VALIDOS and USUARIOS_VALIDOS[usuario]["password"] == contraseña:
                st.session_state['logueado'] = True
                st.session_state['usuario'] = usuario
                st.session_state['nombre_completo'] = USUARIOS_VALIDOS[usuario]["nombre"]
                st.session_state['login_time'] = datetime.now()
                st.experimental_rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# Bienvenida y logout
st.markdown(f"<h2 style='text-align:center; color:#FAB803;'>👋 Bienvenido, {st.session_state['nombre_completo']}.</h2>", unsafe_allow_html=True)
cerrar_sesion()
mostrar_tiempo_sesion()

# Sidebar: control numérico con botones + y -
st.sidebar.header("Configuración de Pedidos")

meses_general_raw = st.session_state.config.get("meses_inventario", {}).get("general", 1.0)
try:
    meses_general = float(meses_general_raw)
except (TypeError, ValueError):
    meses_general = 1.0

st.sidebar.markdown("### Meses inventario general")
col1, col2, col3 = st.sidebar.columns([1,2,1], gap="small")
with col1:
    if st.button("-", key="menos_meses"):
        meses_general = max(0.1, meses_general - 0.1)
        st.session_state.config["meses_inventario"]["general"] = round(meses_general, 2)
        guardar_configuracion(st.session_state.config)
with col2:
    st.markdown(f"<h3 style='text-align:center; margin:0;'>{meses_general:.1f}</h3>", unsafe_allow_html=True)
with col3:
    if st.button("+", key="mas_meses"):
        meses_general = min(12.0, meses_general + 0.1)
        st.session_state.config["meses_inventario"]["general"] = round(meses_general, 2)
        guardar_configuracion(st.session_state.config)

# Mostrar logo y título principal
show_centered_logo("logo.png")
st.markdown("<h1 style='text-align:center; color:#FAB803;'>Pedidos Sugeridos Black Dog</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align:center; color:#ccc;'>Automatiza y descarga los pedidos sugeridos para todas las tiendas Black Dog.</p>", unsafe_allow_html=True)

mostrar_historial()

# Flujo para generar pedidos
if not st.session_state['confirmado'] and not st.session_state['run']:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        if st.button("Generar Pedidos"):
            st.session_state['confirmado'] = True

elif st.session_state['confirmado'] and not st.session_state['run']:
    st.markdown("""
        <div style='background:#444111; padding:1.5em; border-radius:10px; text-align:center; font-weight:bold; color:#fff; max-width:500px; margin:1em auto;'>
            ¿Estás seguro de que deseas generar los pedidos?
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")
    with col1:
        if st.button("✅ Confirmar", key="confirm"):
            st.session_state['run'] = True
            st.session_state['confirmado'] = False
    with col2:
        if st.button("❌ Cancelar", key="cancel"):
            st.session_state['confirmado'] = False

elif st.session_state['run']:
    try:
        config = st.session_state.get("config")
        if config is None:
            st.error("No hay configuración cargada. Por favor, carga o guarda la configuración.")
            st.session_state['run'] = False
        else:
            meses_inventario = config.get("meses_inventario", {}).get("general", 1)
            with st.spinner("Generando pedidos sugeridos..."):
                procesar_pedidos_odoo(output_dir="Pedidos_Sugeridos", meses_inventario=meses_inventario, config=config)

            last_folders, last_seq = get_last_sequence_folder()
            if last_folders:
                zip_path = f"Pedidos_Sugeridos/PEDIDOS_{last_seq}.zip"

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                    for folder in last_folders:
                        for root, dirs, files in os.walk(folder):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, "Pedidos_Sugeridos")
                                zipf.write(file_path, arcname)

                historial_data = {
                    "usuario": st.session_state.get("usuario", "Desconocido"),
                    "archivo": os.path.basename(zip_path),
                    "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                with open("Pedidos_Sugeridos/historial.json", "w", encoding="utf-8") as f:
                    json.dump(historial_data, f, ensure_ascii=False, indent=2)

                with open(zip_path, "rb") as f:
                    zip_b64 = base64.b64encode(f.read()).decode()
                    st.markdown(f"""
                        <div style='margin:2em auto; background:#111; border:2px solid #FAB803; border-radius:16px; padding:2em; max-width:500px; box-shadow:0 4px 20px #00000055; text-align:center;'>
                            <div style='font-size:1.6em; font-weight:bold; margin-bottom:0.5em; color:#FAB803;'>
                                ✅ Pedido generado correctamente
                            </div>
                            <div style='font-size:1.1em; margin-bottom:1em;'>
                                ZIP generado: <b>{os.path.basename(zip_path)}</b><br>
                                Generado por: <b>{historial_data['usuario']}</b><br>
                                Fecha: {historial_data['fecha']}
                            </div>
                            <a download="{historial_data['archivo']}" href="data:application/zip;base64,{zip_b64}">
                                <button style='background:#FAB803; color:#181818; font-weight:bold; padding:0.6em 1.5em; border:none; border-radius:6px; font-size:1em; cursor:pointer;'>
                                    Descargar ZIP General
                                </button>
                            </a>
                        </div>
                    """, unsafe_allow_html=True)

                # ZIP solo medicamentos
                medicamentos_dir = os.path.join("Pedidos_Sugeridos", "medicamentos")
                zip_medicamentos_path = f"Pedidos_Sugeridos/MEDICAMENTOS_{last_seq}.zip"

                if os.path.exists(medicamentos_dir):
                    with zipfile.ZipFile(zip_medicamentos_path, 'w', zipfile.ZIP_DEFLATED) as zipf_med:
                        for root, dirs, files in os.walk(medicamentos_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                arcname = os.path.relpath(file_path, "Pedidos_Sugeridos")
                                zipf_med.write(file_path, arcname)

                    with open(zip_medicamentos_path, "rb") as f_med:
                        zip_med_b64 = base64.b64encode(f_med.read()).decode()

                    st.markdown(f"""
                        <div style='margin:1em auto; background:#111; border:2px solid #FAB803; border-radius:16px; padding:1.5em; max-width:500px; text-align:center;'>
                            <div style='font-size:1.4em; font-weight:bold; margin-bottom:0.5em; color:#FAB803;'>
                                💊 Pedido Farmacia (Medicamentos) generado correctamente
                            </div>
                            <a download="MEDICAMENTOS_{last_seq}.zip" href="data:application/zip;base64,{zip_med_b64}">
                                <button style='background:#FAB803; color:#181818; font-weight:bold; padding:0.6em 1.5em; border:none; border-radius:6px; font-size:1em; cursor:pointer;'>
                                    Descargar ZIP Farmacia
                                </button>
                            </a>
                        </div>
                    """, unsafe_allow_html=True)

            st.session_state['run'] = False

    except Exception as e:
        st.error(f"Error al generar los pedidos: {str(e)}")
        st.session_state['run'] = False

st.markdown("<hr><div style='text-align:center; color:#FAB803; padding:1em;'>Desarrollado para Black Dog Panamá &copy; 2024</div>", unsafe_allow_html=True)
