import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- SISTEMA DE SEGURIDAD (LOGIN) ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Introduce la contraseña de equipo", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Contraseña incorrecta", type="password", on_change=password_entered, key="password")
        st.error("😕 Acceso denegado")
        return False
    return True

if check_password():
    st.set_page_config(page_title="AI Inventory Console v4.7", layout="wide")
    
    # CSS: Diseño de tarjetas y posicionamiento del panel superior ITscope
    st.markdown("""
        <style>
        .itscope-header-box {
            background: #f8f9fa; padding: 15px; border-radius: 10px;
            border-left: 5px solid #0056b3; margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        }
        .itscope-grid { display: flex; gap: 10px; flex-wrap: wrap; }
        .itscope-mini-card {
            background: white; border: 1px solid #ddd; padding: 8px 12px;
            border-radius: 6px; font-size: 12px; min-width: 160px;
        }
        .itscope-price { color: #0056b3; font-weight: bold; font-size: 14px; }
        .card {
            background: #ffffff; padding: 15px; border-radius: 10px;
            border-top: 4px solid #ff6000; box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-bottom: 20px;
        }
        .vendor-name { font-size: 11px; color: #888; font-weight: bold; text-transform: uppercase; }
        .price-val { font-size: 24px; font-weight: bold; color: #1d1d1b; }
        .pvp-val { color: #ff6000; font-size: 18px; font-weight: bold; }
        </style>
        """, unsafe_allow_html=True)

    # --- MOTOR DE DATOS LOCALES ---
    @st.cache_data(ttl=3600)
    def cargar_datos_locales():
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"}
        }
        def descargar(nombre, info):
            try:
                r = requests.get(info["url"], timeout=20)
                df = pd.read_csv(io.StringIO(r.content.decode(info["enc"], errors='replace')), sep=info["sep"], on_bad_lines='skip', engine='python')
                t = pd.DataFrame()
                t['PN'] = df.iloc[:, info["cols"][0]].astype(str).str.upper().str.strip()
                t['COSTO'] = df.iloc[:, info["cols"][1]].replace(r'[^0-9,.]', '', regex=True).replace(',', '.', regex=True).astype(float)
                t['STOCK'] = df.iloc[:, info["cols"][2]].astype(str)
                t['DESC'] = df.iloc[:, info["cols"][3]].astype(str)
                t['PROVEEDOR'] = nombre
                return t
            except: return pd.DataFrame()
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: descargar(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    # --- FUNCIÓN ITSCOPE REAL (Simulada según tu captura) ---
    def obtener_itscope_real(pn):
        # En producción, aquí se procesaría el XML/JSON de la URL proporcionada
        # Basado en tu captura: Globomatik, everIT, notebooksbilliger, Omega
        return [
            {"vend": "Globomatik IT", "stock": "30", "price": "1.099,99€"},
            {"vend": "everIT - direct", "stock": "15", "price": "1.125,90€"},
            {"vend": "notebooksbilliger", "stock": "4", "price": "1.133,61€"},
            {"vend": "Omega", "stock": "10", "price": "1.161,50€"},
            {"vend": "Market-E", "stock": "2", "price": "1.180,00€"}
        ]

    db = cargar_datos_locales()

    # --- TITULO E ITSCOPE (ZONA SUPERIOR - RECUADRO VERDE) ---
    st.title("🤖 AI Inventory Console v4.7")
    
    # Comprobar si hay un PN activo para mostrar ITscope arriba
    if "pn_activo" in st.session_state:
        st.markdown(f"#### 📊 Market Insights (ITscope) para: {st.session_state['pn_activo']}")
        market_data = obtener_itscope_real(st.session_state['pn_activo'])
        
        html_it = '<div class="itscope-header-box"><div class="itscope-grid">'
        for item in market_data:
            html_it += f'''
            <div class="itscope-mini-card">
                <b>{item['vend']}</b><br>
                <span class="itscope-price">{item['price']}</span><br>
                <span style="color:gray">📦 Stock: {item['stock']}</span>
            </div>
            '''
        html_it += '</div></div>'
        st.markdown(html_it, unsafe_allow_html=True)

    # --- BUSCADOR ---
    entrada = st.text_input("🔍 Introduce Part Number (PN) separados por |", placeholder="Ej: ZT-B50800B-10P").upper()

    if entrada:
        pns_buscados = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns_buscados)]

        if not res_total.empty:
            if "pn_activo" not in st.session_state or st.session_state["pn_activo"] not in pns_buscados:
                st.session_state["pn_activo"] = pns_buscados[0]
            
            pn_actual = st.session_state["pn_activo"]
            datos_pn = res_total[res_total['PN'] == pn_actual].sort_values('COSTO')
            
            # --- TARJETAS LOCALES ---
            st.subheader(f"🎯 Tus Costos Locales: {pn_actual}")
            if not datos_pn.empty:
                grid = st.columns(4)
                margen = st.sidebar.slider("Margen (%)", 0, 50, 15)
                for idx, (_, r) in enumerate(datos_pn.iterrows()):
                    pvp = r['COSTO'] * (1 + (margen/100))
                    with grid[idx % 4]:
                        st.markdown(f"""
                        <div class="card">
                            <div class="vendor-name">{r['PROVEEDOR']}</div>
                            <div class="price-val">{r['COSTO']:.2f}€</div>
                            <div class="pvp-val">PVP Sug: {pvp:.2f}€</div>
                            <p style="font-size:13px; margin-top:10px;">📦 Stock: {r['STOCK']}</p>
                        </div>
                        """, unsafe_allow_html=True)

            # --- TABLA DE NAVEGACIÓN ---
            st.divider()
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            seleccion = st.dataframe(res_resumen, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key="nav_table")

            if seleccion and seleccion.selection.rows:
                idx = seleccion.selection.rows[0]
                st.session_state["pn_activo"] = res_resumen.iloc[idx]['PN']
                st.rerun()

    if st.sidebar.button("🔄 Forzar Recarga"):
        st.cache_data.clear()
        st.rerun()
