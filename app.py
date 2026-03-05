import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- 1. CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="Price Intel Console v6.4", layout="wide")

st.markdown("""
    <style>
    .price-card {
        background: white; border-radius: 12px; padding: 20px;
        border-top: 5px solid #ff6000; box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        text-align: center; margin-bottom: 20px;
    }
    .vendor-label { font-size: 0.8rem; font-weight: 800; color: #999; text-transform: uppercase; }
    .price-big { font-size: 2rem; font-weight: 700; color: #1a1a1a; margin: 5px 0; }
    .pvp-orange { font-size: 1.2rem; font-weight: 600; color: #ff6000; padding-top: 5px; }
    .stock-info { font-size: 0.9rem; margin-top: 10px; color: #333; background: #f0f2f6; border-radius: 5px; padding: 4px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SISTEMA DE SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Price Intel")
        with st.form("login"):
            pwd = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                if pwd == st.secrets["password"]:
                    st.session_state["password_correct"] = True
                    st.rerun()
                else: st.error("Incorrecta")
        return False
    return True

if check_password():
    # --- 3. MOTOR DE DATOS (LIMPIEZA QUIRÚRGICA) ---
    @st.cache_data(ttl=3600)
    def get_data():
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
                df = pd.read_csv(io.BytesIO(r.content), sep=cfg["sep"], usecols=cfg["cols"], encoding=cfg["enc"], on_bad_lines='skip', engine='c')
                
                # --- LIMPIEZA DE PRECIOS ---
                # Extraemos solo números y puntos/comas, luego convertimos
                costo_raw = df.iloc[:, 1].astype(str).str.replace(',', '.')
                costo_num = pd.to_numeric(costo_raw.str.extract('(\d+\.?\d*)')[0], errors='coerce')
                
                # --- LIMPIEZA DE STOCK ---
                # Forzamos a que el stock sea un número entero limpio
                stock_raw = df.iloc[:, 2].astype(str).str.extract('(\d+)')[0]
                stock_num = pd.to_numeric(stock_raw, errors='coerce').fillna(0).astype(int)

                return pd.DataFrame({
                    'PN': df.iloc[:, 0].astype(str).str.upper().str.strip(),
                    'COSTO': costo_num,
                    'STOCK': stock_num,
                    'DESC': df.iloc[:, 3].fillna('Sin descripción'),
                    'PROVEEDOR': name
                }).dropna(subset=['COSTO'])
            except: return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(lambda p: fetch(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    db = get_data()

    # --- 4. INTERFAZ Y LÓGICA ---
    st.sidebar.header("🛒 Ajustes")
    margen = st.sidebar.slider("Margen %", 0, 100, 15)
    
    search = st.text_input("🔍 Buscar Part Numbers (separa con | )").upper()

    if search:
        pns = [p.strip() for p in search.split('|') if p.strip()]
        res = db[db['PN'].isin(pns)]

        if not res.empty:
            if "active_pn" not in st.session_state or st.session_state.active_pn not in pns:
                st.session_state.active_pn = pns[0]

            pn_act = st.session_state.active_pn
            data_pn = res[res['PN'] == pn_act].sort_values('COSTO')
            
            st.subheader(f"📦 Referencia: {pn_act}")
            st.caption(data_pn['DESC'].iloc[0])

            # Grid de Tarjetas Formateadas
            cols = st.columns(4)
            for i, (_, row) in enumerate(data_cards := data_pn.iterrows()):
                pvp = row['COSTO'] * (1 + (margen/100))
                with cols[i % 4]:
                    st.markdown(f"""
                        <div class="price-card">
                            <div class="vendor-label">{row['PROVEEDOR']}</div>
                            <div class="price-big">{row['COSTO']:,.2f}€</div>
                            <div class="pvp-orange">PVP Sug: {pvp:,.2f}€</div>
                            <div class="stock-info">Stock: <b>{row['STOCK']} uds.</b></div>
                        </div>
                    """, unsafe_allow_html=True)

            # --- TABLA DE RESUMEN ---
            st.divider()
            resumen = res.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            # Formateamos la tabla para que también se vea bien el dinero
            resumen['COSTO'] = resumen['COSTO'].map('{:,.2f}€'.format)
            
            sel = st.dataframe(resumen, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

            if sel and sel.selection.rows:
                st.session_state.active_pn = resumen.iloc[sel.selection.rows[0]]['PN']
                st.rerun()
        else:
            st.warning("No hay resultados.")
