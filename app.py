import streamlit as st
import pandas as pd
import requests
import io
import re
from concurrent.futures import ThreadPoolExecutor

# --- 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS ---
st.set_page_config(page_title="Console Price Intelligence v8.0", layout="wide")

def local_css():
    st.markdown("""
        <style>
        .main-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #e6e9ef;
            border-top: 5px solid #ff6000;
            box-shadow: 0 2px 12px rgba(0,0,0,0.05);
            text-align: center;
            margin-bottom: 20px;
        }
        .provider-name { color: #888; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; }
        .price-big { font-size: 2.4rem; font-weight: 800; color: #111; margin: 10px 0; }
        .pvp-sug { color: #ff6000; font-weight: 700; font-size: 1rem; border-top: 1px solid #eee; padding-top: 10px; }
        .stock-badge { 
            display: inline-block; background: #f1f3f6; color: #555; 
            padding: 5px 15px; border-radius: 15px; font-size: 0.85rem; margin-top: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

local_css()

# --- 2. MOTOR DE DATOS (ENGINE) ---
class DataEngine:
    COL_MAPPING = {
        'pn': ['partnumber', 'referencia', 'codigo', 'mpn', 'pn', 'referencia_fabricante'],
        'costo': ['price', 'precio', 'costo', 'wholesale', 'neto', 'unit_price'],
        'stock': ['stock', 'cantidad', 'qty', 'disponible', 'unidades', 'stock_total'],
        'desc': ['nombre', 'descripcion', 'description', 'producto', 'name']
    }

    @staticmethod
    def identify_column(df_columns, target_key):
        for name in DataEngine.COL_MAPPING[target_key]:
            match = [c for c in df_columns if name.lower() in str(c).lower()]
            if match: return match[0]
        return None

    @staticmethod
    def sanitize_price(value):
        if pd.isna(value): return 0.0
        str_val = str(value).replace(',', '.').replace('€', '').strip()
        match = re.search(r'(\d+\.?\d*)', str_val)
        if not match: return 0.0
        num = float(match.group(1))
        return num if num < 1000000 else None # Filtro anti-EAN

@st.cache_data(ttl=3600)
def load_all_providers():
    # Ampliado a los 8 mayoristas mencionados en tu arquitectura
    PROVIDERS = {
        "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";"},
        "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";"},
        "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t"},
        "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";"}
        # Agregar aquí el resto de URLs hasta completar los 8
    }

    def process_node(name, config):
        try:
            r = requests.get(config["url"], timeout=15)
            df = pd.read_csv(io.BytesIO(r.content), sep=config["sep"], encoding='latin-1', on_bad_lines='skip')
            
            c_pn = DataEngine.identify_column(df.columns, 'pn')
            c_costo = DataEngine.identify_column(df.columns, 'costo')
            c_stock = DataEngine.identify_column(df.columns, 'stock')
            c_desc = DataEngine.identify_column(df.columns, 'desc')

            if not c_pn or not c_costo: return pd.DataFrame()

            temp = pd.DataFrame()
            temp['PN'] = df[c_pn].astype(str).str.upper().str.strip()
            temp['COSTO'] = df[c_costo].apply(DataEngine.sanitize_price)
            temp['STOCK'] = pd.to_numeric(df[c_stock].astype(str).str.extract('(\d+)')[0], errors='coerce').fillna(0).astype(int)
            temp['DESC'] = df[c_desc].astype(str).str.slice(0, 80) if c_desc else "Sin descripción"
            temp['PROVEEDOR'] = name
            return temp[temp['STOCK'] > 0].dropna(subset=['COSTO'])
        except:
            return pd.DataFrame()

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda p: process_node(*p), PROVIDERS.items()))
    
    return pd.concat(results, ignore_index=True)

# --- 3. LÓGICA DE INTERFAZ ---
db = load_all_providers()

st.title("🚀 Console Price Intelligence v8.0")

with st.sidebar:
    st.header("⚙️ Configuración")
    margen = st.slider("Margen de beneficio (%)", 0, 100, 15)
    st.info(f"Actualizado con {len(db)} referencias activas.")

# Input de búsqueda avanzado
search_input = st.text_input("🔍 Pega tus PN separados por |", 
                            placeholder="SDA3000AI02BX | G210-1GB D3 LP").strip().upper()

if search_input:
    target_pns = [p.strip() for p in search_input.split('|') if p.strip()]
    filtered_df = db[db['PN'].isin(target_pns)]

    if not filtered_df.empty:
        # Gestión de Selección Activa
        if "active_pn" not in st.session_state or st.session_state.active_pn not in target_pns:
            st.session_state.active_pn = target_pns[0]

        # --- SECCIÓN OFERTAS ---
        current_pn = st.session_state.active_pn
        offers = filtered_df[filtered_df['PN'] == current_pn].sort_values('COSTO')
        
        st.subheader(f"🎯 Ofertas para: {current_pn}")
        
        cols = st.columns(4)
        for i, (_, row) in enumerate(offers.iterrows()):
            pvp = row['COSTO'] * (1 + (margen/100))
            with cols[i % 4]:
                st.markdown(f"""
                    <div class="main-card">
                        <div class="provider-name">{row['PROVEEDOR']}</div>
                        <div class="price-big">{row['COSTO']:,.2f}€</div>
                        <div class="pvp-sug">PVP Sug: {pvp:,.2f}€</div>
                        <div class="stock-badge">📦 Stock: {row['STOCK']} uds</div>
                    </div>
                """, unsafe_allow_html=True)

        # --- PANEL DE REFERENCIAS ---
        st.divider()
        st.subheader("📋 Panel de Referencias")
        
        # Agrupamos para mostrar la mejor opción por cada PN buscado
        resumen = filtered_df.sort_values('COSTO').groupby('PN').first().reset_index()
        resumen = resumen[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]

        event = st.dataframe(
            resumen, 
            use_container_width=True, 
            hide_index=True,
            on_select="rerun",
            selection_mode="single-row"
        )

        if event.selection.rows:
            idx = event.selection.rows[0]
            st.session_state.active_pn = resumen.iloc[idx]['PN']
            st.rerun()
    else:
        st.warning("No se encontraron resultados para los PN ingresados.")
