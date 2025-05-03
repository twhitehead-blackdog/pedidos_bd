import streamlit as st
import os
import zipfile
import base64

from generar import procesar_pedidos_odoo

st.set_page_config(
    page_title="Pedidos Sugeridos Black Dog",
    page_icon="favicon.png",
    layout="centered"
)

# CSS para fondo negro, detalles dorados y botones estilizados
st.markdown("""
    <style>
    body, .main, .block-container {
        background-color: #181818 !important;
        color: #fafafa !important;
    }
    .main-title {
        text-align: center;
        font-size: 2.5em;
        font-weight: 800;
        margin-bottom: 0.2em;
        letter-spacing: 1px;
        color: #FAB803;
        text-shadow: 0 2px 8px #00000055;
    }
    .subtitle {
        text-align: center;
        font-size: 1.18em;
        color: #cccccc;
        margin-bottom: 2em;
    }
    .welcome-card {
        background: #222;
        border-radius: 18px;
        border: 2px solid #FAB803;
        padding: 1.5em 2em;
        margin-bottom: 2em;
        box-shadow: 0 4px 24px #00000033;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }
    .stButton>button {
        background-color: #FAB803;
        color: #181818;
        font-weight: bold;
        border-radius: 8px;
        border: none;
        padding: 0.7em 2.5em;
        font-size: 1.2em;
        margin: 0 auto;
        display: block;
        box-shadow: 0 2px 8px rgba(250,184,3,0.15);
        transition: background 0.2s;
    }
    .stButton>button:hover {
        background-color: #ffd84a;
        color: #181818;
    }
    .stDownloadButton>button {
        background-color: #FAB803;
        color: #181818;
        font-weight: bold;
        border-radius: 8px;
        border: none;
        padding: 0.6em 2em;
        font-size: 1.1em;
        margin: 0 auto;
        display: block;
        box-shadow: 0 2px 8px rgba(250,184,3,0.15);
        transition: background 0.2s;
    }
    .stDownloadButton>button:hover {
        background-color: #ffd84a;
        color: #181818;
    }
    hr {
        border: 1px solid #FAB803;
        margin-top: 2em;
        margin-bottom: 1em;
    }
    </style>
""", unsafe_allow_html=True)

# Logo centrado y tamaño profesional antes del título
def show_centered_logo(path="logo.png", width=220):
    if os.path.exists(path):
        with open(path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; margin-bottom: 1.5em;">
                <img src="data:image/png;base64,{encoded}" width="{width}">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown("<div style='text-align:center; color:#FAB803;'>[Sube tu logo como <b>logo.png</b> para verlo aquí]</div>", unsafe_allow_html=True)

show_centered_logo("logo.png", width=220)

# Título y subtítulo centrados
st.markdown("<div class='main-title'>Pedidos Sugeridos Black Dog</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='subtitle'>Automatiza y descarga los pedidos sugeridos para todas las tiendas Black Dog.<br>Simple, rápido y profesional.</div>",
    unsafe_allow_html=True
)

# Tarjeta de bienvenida elegante
st.markdown("""
    <div class='welcome-card'>
        <b>¿Cómo funciona?</b><br>
        <ul style='color:#FAB803;'>
            <li>Presiona <b>Start</b> para generar los pedidos sugeridos.</li>
            <li>Al finalizar, descarga todos los archivos en un solo ZIP.</li>
            <li>El sistema aplica reglas inteligentes y control de stock.</li>
        </ul>
    </div>
""", unsafe_allow_html=True)

if 'run' not in st.session_state:
    st.session_state['run'] = False

if st.button("Start"):
    st.session_state['run'] = True
    with st.spinner("Generando pedidos sugeridos..."):
        procesar_pedidos_odoo()
    st.success("¡Pedidos generados exitosamente!")

def get_last_sequence_folder(base_dir="Pedidos_Sugeridos"):
    if not os.path.exists(base_dir):
        return [], None
    folders = [os.path.join(base_dir, f) for f in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, f))]
    if not folders:
        return [], None
    secuencias = []
    for folder in folders:
        parts = os.path.basename(folder).split("_")
        if len(parts) >= 3 and parts[-2] == "PEDIDO":
            secuencias.append(parts[-1])
    if not secuencias:
        return [], None
    last_seq = max(secuencias)
    last_folders = [f for f in folders if f.endswith(f"PEDIDO_" + last_seq)]
    return last_folders, last_seq

if st.session_state['run']:
    last_folders, last_seq = get_last_sequence_folder()
    if last_folders:
        zip_path = f"Pedidos_Sugeridos/PEDIDOS_{last_seq}.zip"
        if not os.path.exists(zip_path):
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for folder in last_folders:
                    for root, dirs, files in os.walk(folder):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, "Pedidos_Sugeridos")
                            zipf.write(file_path, arcname)
        with open(zip_path, "rb") as f:
            st.download_button(
                label="Descargar todos los pedidos generados (.zip)",
                data=f,
                file_name=os.path.basename(zip_path),
                mime="application/zip"
            )
        st.markdown(
            "<div style='text-align:center; color:#FAB803; margin-top:1em;'>El ZIP contiene todas las rutas generadas en la última ejecución.</div>",
            unsafe_allow_html=True
        )
    else:
        st.warning("No se encontró ninguna carpeta de pedidos generados aún.")

st.markdown(
    "<hr>"
    "<div style='text-align:center; color:#FAB803; font-size:0.95em;'>"
    "Desarrollado para Black Dog Panamá &copy; 2025"
    "</div>",
    unsafe_allow_html=True
)
