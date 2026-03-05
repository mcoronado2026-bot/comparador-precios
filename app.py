import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="AI Inventory Console v5.1 - Fix", layout="wide")

st.markdown("""
    <style>
    .card {
        background: #ffffff; padding: 20px; border-radius: 10px;
        border-top: 4px solid #ff6000; box-shadow: 0 4px 6px rgba(0,0,0,0.07);
        margin-bottom: 20px; transition: transform 0.2s;
    }
    .card:hover { transform: translateY(-5px); }
    .vendor-name { font-size: 11px; color: #888; font-weight: bold; text-transform: uppercase; }
    .price-val { font-size: 26px; font-weight: bold; color: #1d1d1b; margin: 5px 0; }
    .pvp-val { color: #ff6000; font-size: 19px; font-weight: bold; }
    .stock-label { font-size: 12px; color: #444; }
    </style>
    """, unsafe_allow_html=True)

# --- SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Price Intel - Acceso")
        pwd = st.text_input("Introduce la clave de seguridad", type="password")
        if st.button("Acceder"):
            if pwd == st.secrets["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Clave incorrecta")
        return False
    return True

if check_password():
    # --- MOTOR DE DATOS ---
    @st.cache_data(ttl=3600, show_spinner="Sincronizando con Mayoristas...")
    def cargar_datos_completos():
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"},
            "SYK": {"url": "URL_AQUI", "sep": ";", "cols": [0, 1, 2, 3], "enc": "utf-8"},
            "JARLTECH": {"url": "URL_AQUI", "sep": ";", "cols": [0, 1, 2, 3], "enc": "utf-8"},
            "KOSATEK": {"url": "URL_AQUI", "sep": ";", "cols": [0, 1, 2, 3], "enc": "utf-8"}
        }

        def descargar(nombre, info):
            try:
                if "URL_AQUI" in info["url"]: return pd.DataFrame()
                r = requests.get(info["url"], timeout=10)
                df = pd.read_csv(io.StringIO(r.content.decode(info["enc"], errors='replace')), 
                                 sep=info["sep"], on_bad_lines='skip', engine='c')
                t = pd.DataFrame()
                t['PN'] = df.iloc[:, info["cols"][0]].astype(str).str.upper().str.strip()
                t['COSTO'] = pd.to_numeric(df.iloc[:, info["cols"][1]].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)')[0], errors='coerce')
                t['STOCK'] = df.iloc[:, info["cols"][2]].astype(str)
                t['DESC'] = df.iloc[:, info["cols"][3]].astype(str)
                t['PROVEEDOR'] = nombre
                return t.dropna(subset=['COSTO'])
            except: return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=7) as pool:
            results = list(pool.map(lambda p: descargar(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    db = cargar_datos_completos()

    # --- UI PRINCIPAL ---
    st.title("🤖 AI Inventory Console v5.1")
    
    entrada = st.text_input("🔍 Part Number(s)", key="main_search").upper()

    if entrada:
        pns = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns)]

        if not res_total.empty:
            if "pn_activo" not in st.session_state or st.session_state["pn_activo"] not in pns:
                st.session_state["pn_activo"] = pns[0]
            
            pn_sel = st.session_state["pn_activo"]
            datos_actuales = res_total[res_total['PN'] == pn_sel].sort_values('COSTO')

            # --- SOLUCIÓN AL ERROR: Slider fuera de la sidebar si usamos fragmentos ---
            st.subheader(f"🏷️ Referencia: {pn_sel}")
            st.caption(f"📝 {datos_actuales['DESC'].iloc[0] if not datos_actuales.empty else ''}")
            
            # Slider de margen (Global para que no rompa el fragmento)
            margen = st.slider("Margen de beneficio (%)", 0, 50, 15)

            @st.fragment
            def render_cards(df, m):
                grid = st.columns(4)
                for i, (_, r) in enumerate(df.iterrows()):
                    pvp = r['COSTO'] * (1 + (m/100))
                    with grid[i % 4]:
                        st.markdown(f'''
                        <div class="card">
                            <div class="vendor-name">{r['PROVEEDOR']}</div>
                            <div class="price-val">{r['COSTO']:.2f}€</div>
                            <div class="pvp-val">PVP: {pvp:.2f}€</div>
                            <div class="stock-label">📦 Stock: <b>{r['STOCK']}</b></div>
                        </div>
                        ''', unsafe_allow_html=True)

            render_cards(datos_actuales, margen)

            # TABLA NAVEGABLE
            st.divider()
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            sel = st.dataframe(res_resumen, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row")

            if sel and sel.selection.rows:
                st.session_state["pn_activo"] = res_resumen.iloc[sel.selection.rows[0]]['PN']
                st.rerun()

    if st.sidebar.button("🔄 Refrescar Todo"):
        st.cache_data.clear()
        st.rerun()
