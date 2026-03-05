import streamlit as st
import pandas as pd
import requests
import io
import re
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE SEGURIDAD ---
def check_password():
    """Devuelve True si el usuario introdujo la contraseña correcta."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Eliminar contraseña de la memoria
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # Pantalla de Login inicial
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Introduce la contraseña de equipo", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        # Contraseña incorrecta
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Contraseña incorrecta. Inténtalo de nuevo", type="password", on_change=password_entered, key="password")
        st.error("😕 Acceso denegado")
        return False
    else:
        # Contraseña correcta
        return True

if check_password():
    # --- TODO TU CÓDIGO DE LA APLICACIÓN VA AQUÍ ---
    st.set_page_config(page_title="Price Intel Pro v4.2", layout="wide")
    
    # Identidad Anti-Bot
    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}

    @st.cache_data(ttl=3600)
    def cargar_datos_seguro():
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3], "enc": "utf-8"}
        }
        
        def descargar(nombre, info):
            try:
                r = requests.get(info["url"], headers=HEADERS, timeout=15)
                df = pd.read_csv(io.StringIO(r.content.decode(info["enc"], errors='replace')), sep=info["sep"], on_bad_lines='skip', engine='python')
                t = pd.DataFrame()
                t['PN'] = df.iloc[:, info["cols"][0]].astype(str).str.upper().str.strip()
                t['COSTO'] = df.iloc[:, info["cols"][1]].replace(r'[^0-9,.]', '', regex=True).replace(',', '.', regex=True).astype(float)
                t['STOCK'] = df.iloc[:, info["cols"][2]].astype(str)
                t['PROVEEDOR'] = nombre
                return t
            except: return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: descargar(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    st.title("🧡 Panel de Inteligencia Comercial")
    margen = st.sidebar.slider("Margen de beneficio deseado (%)", 0, 50, 15)
    
    if st.sidebar.button("🔄 Forzar actualización de datos"):
        st.cache_data.clear()

    db = cargar_datos_seguro()
    busqueda = st.text_input("🔍 Introduce el Part Number (PN):").upper()

    if busqueda:
        res = db[db['PN'] == busqueda].sort_values('COSTO')
        if not res.empty:
            cols = st.columns(3)
            for i, (_, r) in enumerate(res.iterrows()):
                pvp = r['COSTO'] * (1 + (margen/100))
                with cols[i % 3]:
                    st.markdown(f"""
                    <div style="border: 1px solid #ddd; padding: 15px; border-radius: 10px; background: white; margin-bottom: 10px;">
                        <h3>{r['PROVEEDOR']}</h3>
                        <p>Costo: <b>{r['COSTO']:.2f}€</b></p>
                        <p style="color: #ff6000; font-size: 20px;">PVP Sugerido: <b>{pvp:.2f}€</b></p>
                        <p>Stock: {r['STOCK']}</p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.error("Producto no encontrado.")
