import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE INTERFAZ PROFESIONAL ---
st.set_page_config(page_title="Price Intel Master v7.0", layout="wide")

st.markdown("""
    <style>
    .price-card {
        background: white; border-radius: 12px; padding: 20px;
        border-top: 5px solid #ff6000; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        text-align: center; margin-bottom: 20px;
    }
    .vendor-label { font-size: 0.8rem; font-weight: 800; color: #999; text-transform: uppercase; }
    .price-big { font-size: 2.2rem; font-weight: 700; color: #1a1a1a; margin: 5px 0; }
    .pvp-orange { font-size: 1.3rem; font-weight: 600; color: #ff6000; border-top: 1px solid #eee; padding-top: 10px; }
    .stock-info { font-size: 0.9rem; margin-top: 10px; color: #555; background: #f8f9fa; padding: 5px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- SISTEMA DE SEGURIDAD ESTABLE ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Restringido")
        with st.form("login"):
            pwd = st.text_input("Contraseña de Equipo", type="password")
            if st.form_submit_button("Entrar"):
                if pwd == st.secrets["password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Contraseña incorrecta")
        return False
    return True

if check_password():
    # --- MOTOR DE DATOS (RE-MAPEADO QUIRÚRGICO) ---
    @st.cache_data(ttl=3600)
    def get_inventory():
        # Formato cols: [PN, PRECIO, STOCK, DESC]
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"},
            "SYK": {"url": "https://www.syk.es/tarifas/completa.csv", "sep": ";", "cols": [0, 4, 5, 1], "enc": "utf-8"}
        }

        def fetch(name, cfg):
            try:
                r = requests.get(cfg["url"], timeout=15)
                # Cargamos solo las columnas necesarias para no saturar memoria
                df = pd.read_csv(io.BytesIO(r.content), sep=cfg["sep"], usecols=cfg["cols"], 
                                 encoding=cfg["enc"], on_bad_lines='skip', engine='c')
                
                # RE-MAPEADO SEGURO: Evita leer EANs como Precios
                clean_df = pd.DataFrame()
                clean_df['PN'] = df.iloc[:, 0].astype(str).str.upper().str.strip()
                
                # Limpieza de precio: quitamos todo lo que no sea número o punto/coma
                p_raw = df.iloc[:, 1].astype(str).str.replace(',', '.')
                clean_df['COSTO'] = pd.to_numeric(p_raw.str.extract('(\d+\.?\d*)')[0], errors='coerce')
                
                # Stock como entero limpio
                s_raw = df.iloc[:, 2].astype(str).str.extract('(\d+)')[0]
                clean_df['STOCK'] = pd.to_numeric(s_raw, errors='coerce').fillna(0).astype(int)
                
                clean_df['DESC'] = df.iloc[:, 3].astype(str).str.slice(0, 100) # Recortar para estética
                clean_df['PROVEEDOR'] = name
                
                return clean_df.dropna(subset=['COSTO'])
            except: return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda p: fetch(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    db = get_inventory()

    # --- INTERFAZ DE USUARIO ---
    st.title("🚀 AI Inventory Console v7.0")
    
    # El slider fuera de fragmentos para evitar el error de las capturas
    margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
    
    search = st.text_input("🔍 Introduce PNs (separa con | )", placeholder="Ej: ZT-D40710D-10P | 90-MXBJS0-A0U").strip().upper()

    if search:
        target_pns = [p.strip() for p in search.split('|') if p.strip()]
        res = db[db['PN'].isin(target_pns)]

        if not res.empty:
            # Lógica de navegación persistente
            if "active_pn" not in st.session_state or st.session_state.active_pn not in target_pns:
                st.session_state.active_pn = target_pns[0]

            # Tarjetas del PN seleccionado
            pn_act = st.session_state.active_pn
            data_pn = res[res['PN'] == pn_act].sort_values('COSTO')
            
            st.subheader(f"🎯 Ofertas: {pn_act}")
            st.caption(data_pn['DESC'].iloc[0] if not data_pn.empty else "")

            grid = st.columns(4)
            for i, (_, row) in enumerate(data_pn.iterrows()):
                pvp = row['COSTO'] * (1 + (margen/100))
                with grid[i % 4]:
                    st.markdown(f"""
                        <div class="price-card">
                            <div class="vendor-label">{row['PROVEEDOR']}</div>
                            <div class="price-big">{row['COSTO']:.2f}€</div>
                            <div class="pvp-orange">PVP Sug: {pvp:.2f}€</div>
                            <div class="stock-info">📦 Stock: <b>{row['STOCK']} uds.</b></div>
                        </div>
                    """, unsafe_allow_html=True)

            # --- TABLA DE RESUMEN (Vuelve la interactividad) ---
            st.divider()
            st.subheader("📋 Resumen de la búsqueda")
            resumen = res.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            # Formateo de moneda en tabla
            resumen_view = resumen.copy()
            resumen_view['COSTO'] = resumen_view['COSTO'].map('{:.2f}€'.format)
            
            sel = st.dataframe(resumen_view, use_container_width=True, hide_index=True, 
                                 on_select="rerun", selection_mode="single-row")

            if sel and sel.selection.rows:
                st.session_state.active_pn = resumen.iloc[sel.selection.rows[0]]['PN']
                st.rerun()
        else:
            st.warning("No se encontraron esos PNs en los mayoristas.")

    # Sidebar: Botón de actualización real
    st.sidebar.divider()
    if st.sidebar.button("🔄 Forzar Recarga"):
        st.cache_data.clear()
        st.rerun()
