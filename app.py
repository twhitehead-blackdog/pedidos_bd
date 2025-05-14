import streamlit as st
import os
import zipfile
import base64
import json
from datetime import datetime, timedelta
from generar import procesar_pedidos_odoo

# Configuraci贸n de la p谩gina
st.set_page_config(
    page_title="Pedidos Sugeridos Black Dog",
    page_icon="favicon.png",
    layout="centered"
)

# Usuarios v谩lidos desde secrets.toml
USUARIOS_VALIDOS = st.secrets["usuarios"]

# ---------- ESTILOS CSS ----------
st.markdown("""
    <style>
    body, .main, .block-container {
        background-color: #181818 !important;
        color: #fafafa !important;
    }
    .main-title {
        text-align: center;
        font-size: 2.3em;
        font-weight: 800;
        color: #FAB803;
        margin-top: 0.5em;
        margin-bottom: 0.5em;
    }
    .subtitle {
        text-align: center;
        font-size: 1.1em;
        color: #cccccc;
        margin-bottom: 2em;
    }
    .welcome-user {
        text-align: center;
        font-size: 1.15em;
        color: #FAB803;
        margin-bottom: 1.5em;
        font-weight: bold;
    }
    .session-info {
        text-align: center;
        font-size: 0.9em;
        color: #888;
        margin-bottom: 1em;
    }
    .logout-container {
        text-align: right;
        padding-right: 1.5em;
        margin-bottom: 1em;
    }
    .stButton>button, .stDownloadButton>button {
        background-color: #FAB803 !important;
        color: #181818 !important;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.7em 2em;
        font-size: 1.1em;
        border: none;
        box-shadow: 0 2px 8px rgba(250,184,3,0.15);
        margin: 0 auto;
        display: block;
        width: 100%;
        transition: all 0.3s ease;
    }
    .stButton>button:hover, .stDownloadButton>button:hover {
        background-color: #ffd84a !important;
        color: #181818 !important;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(250,184,3,0.25);
    }
    .logout-button {
        background-color: transparent !important;
        color: #FAB803 !important;
        border: 1px solid #FAB803 !important;
        padding: 0.5em 1em !important;
        font-size: 0.9em !important;
        width: auto !important;
    }
    .logout-button:hover {
        background-color: #FAB803 !important;
        color: #181818 !important;
    }
    hr {
        border: 1px solid #FAB803;
        margin-top: 3em;
    }
    .stTextInput, .stSelectbox, div[data-baseweb="input"] {
        max-width: 400px;
        margin: 0 auto;
    }
    .confirmation-box {
        background-color: #444111;
        padding: 1.5em;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        color: #fff;
        margin: 1em auto;
        max-width: 500px;
        animation: fadeIn 0.5s ease-out;
    }
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(-10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .history-box {
        background-color: #111;
        border-left: 4px solid #FAB803;
        padding: 1.5em;
        border-radius: 8px;
        max-width: 500px;
        margin: 2em auto;
        transition: all 0.3s ease;
    }
    .history-box:hover {
        transform: translateX(5px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .result-box {
        margin: 2em auto;
        background-color: #111;
        border: 2px solid #FAB803;
        border-radius: 16px;
        padding: 2em;
        max-width: 500px;
        box-shadow: 0 4px 20px #00000055;
        text-align: center;
        animation: slideIn 0.5s ease-out;
    }
    @keyframes slideIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .stColumn {
        display: flex;
        justify-content: center;
        align-items: center;
    }
    div[data-testid="stForm"] {
        max-width: 400px;
        margin: 0 auto;
    }
    button[kind="formSubmit"] {
        background-color: #FAB803 !important;
        color: #181818 !important;
        width: 100%;
    }
    .error-message {
        color: #ff4b4b;
        text-align: center;
        padding: 1em;
        margin: 1em 0;
        border-radius: 8px;
        background-color: rgba(255,75,75,0.1);
    }
    .success-message {
        color: #28a745;
        text-align: center;
        padding: 1em;
        margin: 1em 0;
        border-radius: 8px;
        background-color: rgba(40,167,69,0.1);
    }
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1em;
    }
    </style>
""", unsafe_allow_html=True)

# ---------- FUNCIONES AUXILIARES ----------
def show_centered_logo(path="logo.png", width=220):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
        st.markdown(
            f"<div style='text-align:center; margin-bottom:1.5em;'>"
            f"<img src='data:image/png;base64,{encoded}' width='{width}'>"
            f"</div>",
            unsafe_allow_html=True
        )

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
                        <div class='history-box'>
                            <b>馃搨 脷ltimo ZIP generado:</b><br>
                            <ul style='color:#cccccc; list-style-position: inside;'>
                                <li><b>Archivo:</b> {hist['archivo']}</li>
                                <li><b>Generado por:</b> {hist['usuario']}</li>
                                <li><b>Fecha:</b> {hist['fecha']}</li>
                            </ul>
                            <div style='text-align:center; margin-top:1em;'>
                                <a download="{hist['archivo']}" href="data:application/zip;base64,{zip_b64}">
                                    <button style='
                                        background-color:#FAB803;
                                        color:#181818;
                                        font-weight:bold;
                                        padding:0.5em 1.5em;
                                        border:none;
                                        border-radius:6px;
                                        font-size:1em;
                                        cursor:pointer;
                                        width: auto;
                                    '>
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
            st.markdown(f"""
                <div class='session-info'>
                    Tiempo restante de sesi贸n: {minutos_restantes} minutos
                </div>
            """, unsafe_allow_html=True)

def cerrar_sesion():
    if 'confirmar_cierre' not in st.session_state:
        st.session_state['confirmar_cierre'] = False

    # Contenedor para el bot贸n de cierre de sesi贸n
    st.markdown("<div class='logout-container'>", unsafe_allow_html=True)
    if not st.session_state['confirmar_cierre']:
        if st.button("Cerrar sesi贸n", key="logout_button"):
            st.session_state['confirmar_cierre'] = True
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # Mostrar confirmaci贸n si es necesario
    if st.session_state['confirmar_cierre']:
        st.warning("驴Est谩s seguro de que deseas cerrar sesi贸n?")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("S铆, cerrar sesi贸n", key="confirm_logout"):
                st.session_state.clear()
                st.rerun()
        with col2:
            if st.button("No, cancelar", key="cancel_logout"):
                st.session_state['confirmar_cierre'] = False
                st.rerun()

# ---------- INICIALIZACI脫N DE ESTADO ----------
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

# ---------- LOGIN ----------
if not st.session_state.get('logueado', False) or (
    st.session_state.get('login_time') and
    datetime.now() - st.session_state['login_time'] > timedelta(minutes=30)
):
    st.session_state['logueado'] = False
    show_centered_logo("logo.png")
    st.markdown("<div class='main-title'>Pedidos Black Dog</div>", unsafe_allow_html=True)
    st.markdown("<div class='subtitle'>Por favor ingresa tus credenciales para continuar.</div>", unsafe_allow_html=True)

    with st.form("login_form"):
        usuario = st.text_input("Usuario")
        contrase帽a = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Iniciar sesión")

        if submitted:
            if usuario in USUARIOS_VALIDOS and USUARIOS_VALIDOS[usuario]["password"] == contraseña:
                st.session_state['logueado'] = True
                st.session_state['usuario'] = usuario
                st.session_state['nombre_completo'] = USUARIOS_VALIDOS[usuario]["nombre"]
                st.session_state['login_time'] = datetime.now()
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# ---------- BARRA DE LOGOUT Y BIENVENIDA ----------
st.markdown(
    f"<div class='welcome-user'>Bienvenido, {st.session_state['nombre_completo']}.</div>",
    unsafe_allow_html=True
)
cerrar_sesion()
mostrar_tiempo_sesion()

# ---------- HOME PRINCIPAL ----------
show_centered_logo("logo.png")
st.markdown("<div class='main-title'>Pedidos Sugeridos Black Dog</div>", unsafe_allow_html=True)
st.markdown("<div class='subtitle'>Automatiza y descarga los pedidos sugeridos para todas las tiendas Black Dog.</div>", unsafe_allow_html=True)

mostrar_historial()

# ---------- FLUJO DE GENERACI脫N DE PEDIDOS ----------
if not st.session_state['confirmado'] and not st.session_state['run']:
    col1, col2, col3 = st.columns([1,1,1])
    with col2:
        if st.button("Generar Pedidos"):
            st.session_state['confirmado'] = True
            st.rerun()

elif st.session_state['confirmado'] and not st.session_state['run']:
    st.markdown("""
        <div class='confirmation-box'>
            驴Est谩s seguro de que deseas generar los pedidos?
        </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("鉁?Confirmar", key="confirm"):
            st.session_state['run'] = True
            st.session_state['confirmado'] = False
            st.rerun()
    with col2:
        if st.button("鉂?Cancelar", key="cancel"):
            st.session_state['confirmado'] = False
            st.rerun()

elif st.session_state['run']:
    try:
        # Spinner centrado usando columnas
        col1, col2, col3 = st.columns([1,2,1])
        with col2:
            with st.spinner("Generando pedidos sugeridos..."):
                procesar_pedidos_odoo()

        last_folders, last_seq = get_last_sequence_folder()
        if last_folders:
            zip_path = f"Pedidos_Sugeridos/PEDIDOS_{last_seq}.zip"

            # Crear ZIP y actualizar historial
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

            # Mostrar resultado
            with open(zip_path, "rb") as f:
                zip_b64 = base64.b64encode(f.read()).decode()
                st.markdown(f"""
                    <div class='result-box'>
                        <div style='font-size: 1.6em; font-weight: bold; margin-bottom: 0.5em; color: #FAB803;'>
                            鉁?Pedido generado correctamente
                        </div>
                        <div style='font-size: 1.1em; margin-bottom: 1em;'>
                            ZIP generado: <b>{os.path.basename(zip_path)}</b><br>
                            Generado por: <b>{historial_data['usuario']}</b><br>
                            Fecha: {historial_data['fecha']}
                        </div>
                        <a download="{historial_data['archivo']}"
                           href="data:application/zip;base64,{zip_b64}">
                            <button style='
                                background-color:#FAB803;
                                color:#181818;
                                font-weight:bold;
                                padding:0.6em 1.5em;
                                border:none;
                                border-radius:6px;
                                font-size:1em;
                                cursor:pointer;
                                width: auto;
                            '>
                                Descargar ZIP
                            </button>
                        </a>
                    </div>
                """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error al generar los pedidos: {str(e)}")
        st.session_state['run'] = False
        st.rerun()

# ---------- FOOTER ----------
st.markdown("""
    <hr>
    <div style='text-align:center; color:#FAB803; padding: 1em;'>
        Desarrollado para Black Dog Panamá &copy; 2024
    </div>
""", unsafe_allow_html=True)
