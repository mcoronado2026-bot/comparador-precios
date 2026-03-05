import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE RENDIMIENTO ---
st.set_page_config(page_title="Price Intel Engine v5.3 - Full Restore", layout="wide")

st.markdown("""
    <style>
    .price-card {
        background: white; border-radius: 12px; padding: 15px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1); border-top: 4px solid #ff6000;
        text-align: center; margin-bottom: 15px;
    }
    .vendor-name { font-size: 0.8rem; font-weight: bold; color: #888; text-transform: uppercase; }
    .price-val { font-size: 1.8rem; font-weight: 700; color: #111; }
    .pvp-val { font-size: 1.1rem; font-weight: 600; color: #ff6000; }
    </style>
    """, unsafe_allow_html=True)

# --- MOTOR DE DATOS (TODOS LOS PROVEEDORES) ---
@st.cache_data(ttl=3600, show_spinner="Actualizando base de datos global...")
def cargar_inventario_completo():
    # Configuración maestra de cada mayorista (URLs y columnas)
    # Formato cols: [Índice_PN, Índice_Precio, Índice_Stock, Índice_Descripción]
    PROVEEDORES = {
        "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
        "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
        "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
        "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"},
        "SYK": {"url": "https://www.siewert-kau.com/en/api/prices/c2c27194842155240822/full.csv", "sep": ";", "cols": [0, 4, 5, 1], "enc": "utf-8"}, # URL estimada
        "JARLTECH": {"url": "https://www.jarltech.com/en/price-list/public/6e71ab92e54c52048ce923615c89a2f9/560ae19c129df2eff97bedb97ed5a5a6", "sep": ",", "cols": [0, 5, 8, 1], "enc": "utf-8"},
        "KOSATEK": {"url": "https://data.kosatec.de/25795/883601faba9d8f15e7bbe644549f5188/preisliste.csv", "sep": ";", "cols": [1, 10, 15, 2], "enc": "utf-8"}
    }

    def fetch(nombre, cfg):
        try:
            # Si es una URL de prueba o vacía, saltamos
            if "TU_" in cfg["url"] or "URL_AQUI" in cfg["url"]: return pd.DataFrame()
            
            r = requests.get(cfg["url"], timeout=12)
            df = pd.read_csv(io.StringIO(r.content.decode(cfg["enc"], errors='ignore')), 
                             sep=cfg["sep"], engine='c', on_bad_lines='skip', low_memory=False)
            
            res = pd.DataFrame()
            res['PN'] = df.iloc[:, cfg["cols"][0]].astype(str).str.upper().str.strip()
            # Limpieza agresiva de precios (quitar €, comas, espacios)
            res['COSTO'] = pd.to_numeric(df.iloc[:, cfg["cols"][1]].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)')[0], errors='coerce')
            res['STOCK'] = df.iloc[:, cfg["cols"][2]].astype(str)
            res['DESC'] = df.iloc[:, cfg["cols"][3]].astype(str)
            res['PROVEEDOR'] = nombre
            return res.dropna(subset=['COSTO'])
        except Exception as e:
            return pd.DataFrame()

    # Ejecución en paralelo real para no perder tiempo
    with ThreadPoolExecutor(max_workers=7) as executor:
        results = list(executor.map(lambda p: fetch(*p), PROVEEDORES.items()))
    
    return pd.concat(results, ignore_index=True)

# --- INTERFAZ ---
if "password_correct" not in st.session_state:
    st.title("🔐 Acceso Price Intel")
    if st.text_input("Contraseña", type="password") == st.secrets["password"]:
        st.session_state["password_correct"] = True
        st.rerun()
    st.stop()

db = cargar_inventario_completo()

st.title("🚀 Inventory Engine v5.3 (Full Multi-Vendor)")

search = st.text_input("🔍 Pega tus PN (ej: PN1 | PN2)").upper()

if search:
    pns = [p.strip() for p in search.split("|") if p.strip()]
    res = db[db['PN'].isin(pns)]

    if not res.empty:
        if "active_pn" not in st.session_state or st.session_state.active_pn not in pns:
            st.session_state.active_pn = pns[0]

        # SECCIÓN DE TARJETAS
        pn_actual = st.session_state.active_pn
        data_pn = res[res['PN'] == pn_actual].sort_values('COSTO')
        
        st.subheader(f"📦 Referencia: {pn_actual}")
        st.caption(data_pn['DESC'].iloc[0] if not data_pn.empty else "")

        margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)

        cols = st.columns(4)
        for i, (_, row) in enumerate(data_pn.iterrows()):
            pvp = row['COSTO'] * (1 + (margen/100))
            with cols[i % 4]:
                st.markdown(f"""
                    <div class="price-card">
                        <div class="vendor-name">{row['PROVEEDOR']}</div>
                        <div class="price-big" style="font-size:1.8rem; font-weight:bold;">{row['COSTO']:.2f}€</div>
                        <div class="pvp-orange">PVP: {pvp:.2f}€</div>
                        <div style="font-size:0.8rem; margin-top:5px;">Stock: <b>{row['STOCK']}</b></div>
                    </div>
                """, unsafe_allow_html=True)

        # TABLA DE NAVEGACIÓN
        st.divider()
        res_resumen = res.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
        sel = st.dataframe(res_resumen, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

        if sel and sel.selection.rows:
            st.session_state.active_pn = res_resumen.iloc[sel.selection.rows[0]]['PN']
            st.rerun()
    else:
        st.warning("No se encontraron coincidencias. Revisa si las URLs de SYK/KOSATEK/JARLTECH son correctas.")

