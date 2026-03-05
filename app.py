import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- SISTEMA DE SEGURIDAD (LOGIN) ---
def check_password():
    """Devuelve True si el usuario introdujo la contraseña correcta."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Eliminar de memoria por seguridad
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Introduce la contraseña de equipo", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Contraseña incorrecta. Inténtalo de nuevo", type="password", on_change=password_entered, key="password")
        st.error("😕 Acceso denegado")
        return False
    else:
        return True

if check_password():
    # --- CONFIGURACIÓN DE PÁGINA ---
    st.set_page_config(page_title="Price Intel Pro v4.5", layout="wide")
    
    # CSS para diseño profesional y tarjetas responsive
    st.markdown("""
        <style>
        .card {
            background: #ffffff; padding: 15px; border-radius: 10px;
            border-top: 4px solid #ff6000; box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-bottom: 20px; min-height: 190px; transition: 0.3s;
        }
        .card:hover { transform: translateY(-5px); }
        .vendor-name { font-size: 11px; color: #888; font-weight: bold; text-transform: uppercase; }
        .price-val { font-size: 26px; font-weight: bold; color: #1d1d1b; margin: 5px 0; }
        .pvp-val { color: #ff6000; font-size: 19px; font-weight: bold; }
        .savings-tag { background: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
        </style>
        """, unsafe_allow_html=True)

    # --- MOTOR DE DATOS (CON PARALELISMO Y CACHÉ) ---
    @st.cache_data(ttl=3600)
    def cargar_datos_seguro():
        # Diccionario con URLs corregidas en una sola línea para evitar SyntaxError
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"}
        }
        
        def descargar(nombre, info):
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(info["url"], headers=headers, timeout=15)
                df = pd.read_csv(io.StringIO(r.content.decode(info["enc"], errors='replace')), sep=info["sep"], on_bad_lines='skip', engine='python')
                t = pd.DataFrame()
                t['PN'] = df.iloc[:, info["cols"][0]].astype(str).str.upper().str.strip()
                t['COSTO'] = df.iloc[:, info["cols"][1]].replace(r'[^0-9,.]', '', regex=True).replace(',', '.', regex=True).astype(float)
                t['STOCK'] = df.iloc[:, info["cols"][2]].astype(str)
                t['DESC'] = df.iloc[:, info["cols"][3]].astype(str)
                t['PROVEEDOR'] = nombre
                return t
            except:
                return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: descargar(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    db = cargar_datos_seguro()

    # --- INTERFAZ DE USUARIO ---
    st.title("🧡 Console Price Intelligence v4.5")
    
    # Barra lateral
    margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
    if st.sidebar.button("🔄 Forzar Recarga de Datos"):
        st.cache_data.clear()
        st.rerun()

    # Buscador principal
    entrada = st.text_input("🔍 P
    
