<requirements>
import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor
</requirements>

<logic>
# --- CONFIGURACIÓN DE ALTO RENDIMIENTO ---
st.set_page_config(page_title="Price Intel Turbo v6.0", layout="wide")

# Estilo CSS optimizado para carga rápida
st.markdown("""
    <style>
    .price-card {
        background: #fff; border-radius: 8px; padding: 15px;
        border-left: 5px solid #ff6000; box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        margin-bottom: 10px; text-align: center;
    }
    .vendor { font-size: 0.75rem; color: #666; font-weight: bold; }
    .price { font-size: 1.6rem; font-weight: 800; color: #1a1a1a; }
    .pvp { color: #ff6000; font-weight: 600; border-top: 1px solid #eee; margin-top: 5px; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def cargar_motor_optimizido():
    """
    Motor de ingesta de datos con procesamiento paralelo y limpieza vectorial.
    """
    PROVEEDORES = {
        "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
        "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
        "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
        "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"}
    }

    def fetch_worker(nombre, cfg):
        try:
            r = requests.get(cfg["url"], timeout=10)
            # engine='c' es hasta 10 veces más rápido que el motor de Python
            df = pd.read_csv(io.BytesIO(r.content), sep=cfg["sep"], usecols=cfg["cols"], 
                             encoding=cfg["enc"], on_bad_lines='skip', engine='c')
            
            # Mapeo directo de columnas para evitar fragmentación de memoria
            res = pd.DataFrame({
                'PN': df.iloc[:, 0].astype(str).str.upper().str.strip(),
                'COSTO': df.iloc[:, 1].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)')[0].astype(float),
                'STOCK': df.iloc[:, 2].fillna('0'),
                'DESC': df.iloc[:, 3].fillna('Sin descripción'),
                'PROVEEDOR': nombre
            })
            return res.dropna(subset=['COSTO'])
        except:
            return pd.DataFrame()

    with ThreadPoolExecutor(max_workers=len(PROVEEDORES)) as executor:
        results = list(executor.map(lambda p: fetch_worker(*p), PROVEEDORES.items()))
    
    return pd.concat(results, ignore_index=True)

# --- FLUJO PRINCIPAL ---
try:
    db = cargar_motor_optimizido()
except Exception as e:
    st.error("Error crítico al sincronizar. Revisa la conexión.")
    st.stop()

st.title("⚡ Price Intel Turbo v6.0")

# Input optimizado para búsquedas masivas
search_input = st.text_input("🔍 Introduce Part Numbers separados por '|'").strip().upper()

if search_input:
    target_pns = [p.strip() for p in search_input.split('|') if p.strip()]
    
    # Filtrado masivo vectorial (mucho más rápido que bucles for)
    mask = db['PN'].isin(target_pns)
    res_final = db[mask]

    if not res_final.empty:
        # Sidebar para cálculos dinámicos
        margen = st.sidebar.number_input("Margen %", 0, 100, 15)
        
        # Iteración sobre PNs encontrados
        for pn in target_pns:
            data_pn = res_final[res_final['PN'] == pn].sort_values('COSTO')
            if data_pn.empty: continue
            
            st.subheader(f"📦 PN: {pn}")
            st.caption(data_pn['DESC'].iloc[0])
            
            grid = st.columns(4)
            for idx, (_, row) in enumerate(data_pn.iterrows()):
                pvp = row['COSTO'] * (1 + (margen/100))
                with grid[idx % 4]:
                    st.markdown(f"""
                        <div class="price-card">
                            <div class="vendor">{row['PROVEEDOR']}</div>
                            <div class="price">{row['COSTO']:.2f}€</div>
                            <div class="pvp">PVP: {pvp:.2f}€</div>
                            <div style="font-size:0.8rem">📦 {row['STOCK']}</div>
                        </div>
                    """, unsafe_allow_html=True)
            st.divider()
    else:
        st.warning("No se encontraron resultados para los PN indicados.")
</logic>
