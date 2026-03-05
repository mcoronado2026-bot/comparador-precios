import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE PANTALLA ---
st.set_page_config(page_title="Price Intel Master v7.2", layout="wide")

# CSS para que el precio se vea profesional: Grande y con el € destacado
st.markdown("""
    <style>
    .price-card {
        background: #fff; border-radius: 12px; padding: 20px;
        border-top: 5px solid #ff6000; box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        text-align: center; margin-bottom: 20px;
    }
    .vendor { font-size: 0.8rem; color: #888; font-weight: bold; text-transform: uppercase; }
    .price-tag { font-size: 2.2rem; font-weight: 800; color: #111; margin: 5px 0; }
    .euro { color: #ff6000; font-size: 1.4rem; margin-left: 2px; }
    .pvp-tag { font-size: 1.1rem; color: #ff6000; font-weight: 600; border-top: 1px solid #eee; padding-top: 10px; }
    .stock-tag { font-size: 0.85rem; background: #f0f2f6; padding: 3px 10px; border-radius: 15px; margin-top: 10px; display: inline-block; }
    </style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=3600)
def cargar_inventario_inteligente():
    # Diccionario de mayoristas
    MAYORISTAS = {
        "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t"},
        "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";"},
        "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";"},
        "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";"}
    }

    def worker(nombre, info):
        try:
            r = requests.get(info["url"], timeout=15)
            df = pd.read_csv(io.BytesIO(r.content), sep=info["sep"], encoding='latin-1', on_bad_lines='skip')
            
            # --- EL "CEREBRO" DEL CÓDIGO: DETECCIÓN DINÁMICA ---
            # Buscamos columnas por nombre, no por posición (así no se rompe si cambian el orden)
            def find_col(possible_names):
                for name in possible_names:
                    match = [c for c in df.columns if name.lower() in c.lower()]
                    if match: return match[0]
                return None

            c_pn = find_col(['partnumber', 'referencia', 'codigo', 'mpn', 'pn'])
            c_price = find_col(['price', 'precio', 'costo', 'wholesale', 'neto'])
            c_stock = find_col(['stock', 'cantidad', 'qty', 'disponible'])
            c_desc = find_col(['nombre', 'descripcion', 'description', 'producto'])

            if not c_price or not c_pn: return pd.DataFrame()

            # Limpieza y formateo
            res = pd.DataFrame()
            res['PN'] = df[c_pn].astype(str).str.upper().str.strip()
            # Limpieza de precio: extrae solo el número real para evitar EANs
            res['COSTO'] = pd.to_numeric(df[c_price].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)')[0], errors='coerce')
            res['STOCK'] = pd.to_numeric(df[c_stock].astype(str).str.extract('(\d+)')[0], errors='coerce').fillna(0).astype(int)
            res['DESC'] = df[c_desc].astype(str).str.slice(0, 80) if c_desc else "Sin descripción"
            res['PROVEEDOR'] = nombre

            # Filtro de seguridad Senior: descartar precios imposibles (EANs colados)
            return res[(res['COSTO'] > 0.1) & (res['COSTO'] < 25000)]
        except: return pd.DataFrame()

    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(lambda x: worker(*x), MAYORISTAS.items()))
    return pd.concat(results, ignore_index=True)

# --- FLUJO PRINCIPAL ---
if "password_correct" not in st.session_state:
    # (Aquí iría tu bloque de login)
    st.session_state["password_correct"] = True # Simulando acceso para el ejemplo

db = cargar_inventario_inteligente()

st.title("🛡️ Price Intel Master v7.2")
margen = st.sidebar.slider("Margen de beneficio (%)", 0, 100, 15)
search = st.text_input("🔍 Introduce PNs (separa con | )").strip().upper()

if search:
    pns = [p.strip() for p in search.split('|') if p.strip()]
    res = db[db['PN'].isin(pns)]
    
    if not res.empty:
        # Mostrar tarjetas del primer PN encontrado o seleccionado
        pn_act = pns[0] 
        data_pn = res[res['PN'] == pn_act].sort_values('COSTO')
        
        st.subheader(f"Ofertas para: {pn_act}")
        
        cols = st.columns(4)
        for i, (_, row) in enumerate(data_pn.iterrows()):
            pvp = row['COSTO'] * (1 + (margen/100))
            with cols[i % 4]:
                st.markdown(f"""
                    <div class="price-card">
                        <div class="vendor">{row['PROVEEDOR']}</div>
                        <div class="price-tag">{row['COSTO']:,.2f}<span class="euro">€</span></div>
                        <div class="pvp-tag">PVP Sug: {pvp:,.2f}€</div>
                        <div class="stock-tag">📦 Stock: {row['STOCK']} uds.</div>
                    </div>
                """, unsafe_allow_html=True)
