import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- 1. CONFIGURACIÓN DE INTERFAZ PROFESIONAL ---
st.set_page_config(page_title="Price Intel Console v6.3", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .price-card {
        background: white; border-radius: 12px; padding: 20px;
        border-top: 5px solid #ff6000; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        text-align: center; margin-bottom: 20px;
    }
    .vendor-label { font-size: 0.8rem; font-weight: 800; color: #999; text-transform: uppercase; }
    .price-big { font-size: 2.2rem; font-weight: 700; color: #1a1a1a; margin: 10px 0; }
    .pvp-orange { font-size: 1.3rem; font-weight: 600; color: #ff6000; border-top: 1px solid #eee; padding-top: 10px; }
    .stock-info { font-size: 0.9rem; margin-top: 10px; color: #555; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SISTEMA DE SEGURIDAD (CORREGIDO) ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Price Intel")
        # Usamos un form para evitar el error de las capturas
        with st.form("login_form"):
            pwd = st.text_input("Introduce la contraseña de equipo", type="password")
            if st.form_submit_button("Entrar"):
                if pwd == st.secrets["password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta")
        return False
    return True

if check_password():
    # --- 3. MOTOR DE DATOS MULTI-PROVEEDOR (7 PROVEEDORES) ---
    @st.cache_data(ttl=3600, show_spinner="Actualizando base de datos...")
    def get_global_inventory():
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"},
            "SYK": {"url": "https://www.syk.es/tarifas/completa.csv", "sep": ";", "cols": [0, 4, 5, 1], "enc": "utf-8"},
            "JARLTECH": {"url": "URL_JARLTECH_AQUI", "sep": ";", "cols": [0, 5, 8, 1], "enc": "utf-8"},
            "KOSATEK": {"url": "URL_KOSATEK_AQUI", "sep": ";", "cols": [1, 10, 15, 2], "enc": "utf-8"}
        }

        def fetch(name, cfg):
            try:
                if "URL_" in cfg["url"]: return pd.DataFrame()
                r = requests.get(cfg["url"], timeout=15)
                df = pd.read_csv(io.BytesIO(r.content), sep=cfg["sep"], usecols=cfg["cols"], 
                                 encoding=cfg["enc"], on_bad_lines='skip', engine='c')
                
                return pd.DataFrame({
                    'PN': df.iloc[:, 0].astype(str).str.upper().str.strip(),
                    'COSTO': pd.to_numeric(df.iloc[:, 1].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)')[0], errors='coerce'),
                    'STOCK': df.iloc[:, 2].fillna('0'),
                    'DESC': df.iloc[:, 3].fillna(''),
                    'PROVEEDOR': name
                }).dropna(subset=['COSTO'])
            except: return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=7) as executor:
            results = list(executor.map(lambda p: fetch(*p), PROVEEDORES.items()))
        
        return pd.concat(results, ignore_index=True)

    db = get_global_inventory()

    # --- 4. LOGICA DE BÚSQUEDA Y NAVEGACIÓN ---
    st.title("🚀 AI Inventory Console v6.3")
    
    # Sidebar fija para controles globales
    st.sidebar.header("Configuración")
    margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
    
    search_query = st.text_input("🔍 Pega uno o varios PN (separados por | )", placeholder="Ej: ZT-D40710D-10P | 90-MXBJS0-A0U").strip().upper()

    if search_query:
        target_pns = [p.strip() for p in search_query.split('|') if p.strip()]
        filtered_res = db[db['PN'].isin(target_pns)]

        if not filtered_res.empty:
            # Sistema de selección de PN activo
            if "selected_pn" not in st.session_state or st.session_state.selected_pn not in target_pns:
                st.session_state.selected_pn = target_pns[0]

            # Mostrar tarjetas del PN seleccionado
            pn_act = st.session_state.selected_pn
            data_cards = filtered_res[filtered_res['PN'] == pn_act].sort_values('COSTO')
            
            st.subheader(f"🎯 Ofertas para: {pn_act}")
            if not data_cards.empty:
                st.caption(data_cards['DESC'].iloc[0])
            
            grid = st.columns(4)
            for i, (_, row) in enumerate(data_cards.iterrows()):
                pvp = row['COSTO'] * (1 + (margen/100))
                with grid[i % 4]:
                    st.markdown(f"""
                        <div class="price-card">
                            <div class="vendor-label">{row['PROVEEDOR']}</div>
                            <div class="price-big">{row['COSTO']:.2f}€</div>
                            <div class="pvp-orange">PVP Sug: {pvp:.2f}€</div>
                            <div class="stock-info">📦 Stock: <b>{row['STOCK']}</b></div>
                        </div>
                    """, unsafe_allow_html=True)

            # --- TABLA DE RESUMEN INTERACTIVA ---
            st.divider()
            st.subheader("📋 Resumen de Referencias")
            resumen_df = filtered_res.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            # Usamos la selección nativa de Streamlit para cambiar de producto
            event = st.dataframe(resumen_df, use_container_width=True, hide_index=True, 
                                 on_select="rerun", selection_mode="single-row")

            if event and event.selection.rows:
                st.session_state.selected_pn = resumen_df.iloc[event.selection.rows[0]]['PN']
                st.rerun()
        else:
            st.warning("No se encontraron coincidencias en la base de datos.")

    # Botón para forzar recarga en el sidebar
    st.sidebar.divider()
    if st.sidebar.button("🔄 Actualizar Mayoristas"):
        st.cache_data.clear()
        st.rerun()
