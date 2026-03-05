import streamlit as st
import pandas as pd
import requests
import io
import re
from concurrent.futures import ThreadPoolExecutor

# --- 1. CAPA DE CONFIGURACIÓN Y UI (PRESENTACIÓN) ---
st.set_page_config(page_title="Price Intel Console v8.0", layout="wide")

st.markdown("""
    <style>
    .main-card { background: #fff; border-radius: 12px; padding: 20px; border-top: 5px solid #ff6000; box-shadow: 0 4px 10px rgba(0,0,0,0.1); text-align: center; }
    .price-big { font-size: 2.2rem; font-weight: 800; color: #111; margin: 5px 0; }
    .euro-symbol { color: #ff6000; font-size: 1.2rem; }
    .stock-badge { font-size: 0.8rem; background: #f0f2f6; padding: 4px 12px; border-radius: 20px; color: #333; }
    </style>
""", unsafe_allow_html=True)

# --- 2. CAPA DE LÓGICA DE DETECCIÓN Y NORMALIZACIÓN (CORE) ---
class DataEngine:
    """Clase encargada de la detección dinámica y validación de tipos."""
    
    COL_MAPPING = {
        'pn': ['partnumber', 'referencia', 'codigo', 'mpn', 'pn', 'referencia_fabricante'],
        'costo': ['price', 'precio', 'costo', 'wholesale', 'neto', 'unit_price'],
        'stock': ['stock', 'cantidad', 'qty', 'disponible', 'unidades'],
        'desc': ['nombre', 'descripcion', 'description', 'producto', 'name']
    }

    @staticmethod
    def identify_column(df_columns, target_key):
        """Busca la columna más probable basándose en palabras clave."""
        for name in DataEngine.COL_MAPPING[target_key]:
            match = [c for c in df_columns if name.lower() in str(c).lower()]
            if match: return match[0]
        return None

    @staticmethod
    def sanitize_price(value):
        """Validador Anti-Alucinación: Evita EANs en campos de precio."""
        if pd.isna(value): return 0.0
        # Limpieza básica de strings
        str_val = str(value).replace(',', '.').strip()
        # Extraer solo el patrón numérico (decimal)
        match = re.search(r'(\d+\.?\d*)', str_val)
        if not match: return 0.0
        
        num = float(match.group(1))
        # EXCEPCIÓN DE MAPEO: Si el número tiene formato de EAN (ej: > 10^10)
        # o es sospechosamente largo (> 10 dígitos), es un error de columna.
        if num > 9999999: # Límite lógico de precio para hardware
            return None 
        return num

@st.cache_data(ttl=3600)
def fetch_and_process_all():
    """Carga asíncrona de proveedores con ThreadPoolExecutor."""
    PROVIDERS = {
        "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";"},
        "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";"},
        "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t"},
        "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";"}
    }

    def process_single(name, config):
        try:
            r = requests.get(config["url"], timeout=20)
            df = pd.read_csv(io.BytesIO(r.content), sep=config["sep"], encoding='latin-1', on_bad_lines='skip')
            
            # Detección dinámica de columnas
            c_pn = DataEngine.identify_column(df.columns, 'pn')
            c_costo = DataEngine.identify_column(df.columns, 'costo')
            c_stock = DataEngine.identify_column(df.columns, 'stock')
            c_desc = DataEngine.identify_column(df.columns, 'desc')

            if not c_pn or not c_costo: return pd.DataFrame()

            # Normalización vectorizada
            temp_df = pd.DataFrame()
            temp_df['PN'] = df[c_pn].astype(str).str.upper().str.strip()
            temp_df['COSTO'] = df[c_costo].apply(DataEngine.sanitize_price)
            temp_df['STOCK'] = pd.to_numeric(df[c_stock].astype(str).str.extract('(\d+)')[0], errors='coerce').fillna(0).astype(int)
            temp_df['DESC'] = df[c_desc].astype(str).str.slice(0, 100) if c_desc else "N/A"
            temp_df['PROVEEDOR'] = name
            
            # Eliminar registros con "Excepción de Mapeo" (Precios=None)
            return temp_df.dropna(subset=['COSTO'])
        except Exception as e:
            return pd.DataFrame()

    with ThreadPoolExecutor(max_workers=len(PROVIDERS)) as executor:
        results = list(executor.map(lambda p: process_single(*p), PROVIDERS.items()))
    
    full_db = pd.concat(results, ignore_index=True)
    # Optimización: Indexar por PN para búsquedas instantáneas (O(1) vs O(n))
    return full_db

# --- 3. FLUJO DE APLICACIÓN (UI SEPARADA) ---
db = fetch_and_process_all()

st.title("🚀 Console Price Intelligence v8.0")
st.sidebar.header("Configuración")
margen = st.sidebar.slider("Margen de beneficio (%)", 0, 100, 15)

# Buscador multilínea con pipes |
search_raw = st.text_input("🔍 Pega tus PN separados por |", placeholder="PN1 | PN2 | PN3").strip().upper()

if search_raw:
    # Hash-Set para búsqueda eficiente
    target_pns = {p.strip() for p in search_raw.split('|') if p.strip()}
    
    # Filtrado ultra-rápido mediante vectorización
    filtered_res = db[db['PN'].isin(target_pns)]

    if not filtered_res.empty:
        # Lógica de selección de referencia activa
        if "selected_pn" not in st.session_state or st.session_state.selected_pn not in target_pns:
            st.session_state.selected_pn = list(target_pns)[0]
        
        pn_sel = st.session_state.selected_pn
        cards_data = filtered_res[filtered_res['PN'] == pn_sel].sort_values('COSTO')

        st.subheader(f"🎯 Ofertas para: {pn_sel}")
        
        # Grid de Cards (Comparativa)
        grid = st.columns(4)
        for i, (_, row) in enumerate(cards_data.iterrows()):
            pvp = row['COSTO'] * (1 + (margen/100))
            with grid[i % 4]:
                st.markdown(f"""
                    <div class="main-card">
                        <div style="color:#888; font-weight:bold; font-size:0.7rem;">{row['PROVEEDOR']}</div>
                        <div class="price-big">{row['COSTO']:,.2f}<span class="euro-symbol">€</span></div>
                        <div style="color:#ff6000; font-weight:600; border-top:1px solid #eee; margin-top:10px; padding-top:5px;">
                            PVP Sug: {pvp:,.2f}€
                        </div>
                        <div class="stock-badge">📦 Stock: {row['STOCK']} uds</div>
                    </div>
                """, unsafe_allow_html=True)

        # Tabla de Referencias (Resumen)
        st.divider()
        st.subheader("📋 Panel de Referencias")
        resumen = filtered_res.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
        
        # Evento de selección en tabla
        event = st.dataframe(resumen, use_container_width=True, hide_index=True, 
                             on_select="rerun", selection_mode="single-row")
        
        if event and event.selection.rows:
            st.session_state.selected_pn = resumen.iloc[event.selection.rows[0]]['PN']
            st.rerun()
    else:
        st.warning("No se han encontrado coincidencias en los proveedores actuales.")
