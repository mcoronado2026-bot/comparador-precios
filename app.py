import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- SISTEMA DE SEGURIDAD ---
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
    st.set_page_config(page_title="AI Inventory Console v4.8 - Stable", layout="wide")
    
    # CSS Optimizado para velocidad y limpieza
    st.markdown("""
        <style>
        .card {
            background: #ffffff; padding: 20px; border-radius: 10px;
            border-top: 4px solid #ff6000; box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-bottom: 20px;
        }
        .vendor-name { font-size: 12px; color: #888; font-weight: bold; text-transform: uppercase; }
        .price-val { font-size: 28px; font-weight: bold; color: #1d1d1b; margin: 5px 0; }
        .pvp-val { color: #ff6000; font-size: 20px; font-weight: bold; }
        .stock-val { font-size: 14px; margin-top: 10px; color: #444; }
        </style>
        """, unsafe_allow_html=True)

    # --- MOTOR DE DATOS LOCALES (Optimizado) ---
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
                r = requests.get(info["url"], timeout=15)
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

    db = cargar_datos_locales()

    # --- INTERFAZ PRINCIPAL ---
    st.title("🤖 AI Inventory Console v4.8")
    
    # Buscador limpio y directo
    entrada = st.text_input("🔍 Introduce Part Number (PN) o múltiples separados por |", placeholder="Ej: ZT-B50800B-10P").upper()

    if entrada:
        pns_buscados = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns_buscados)]

        if not res_total.empty:
            # Sincronización de selección
            if "pn_activo" not in st.session_state or st.session_state["pn_activo"] not in pns_buscados:
                st.session_state["pn_activo"] = pns_buscados[0]
            
            pn_actual = st.session_state["pn_activo"]
            datos_pn = res_total[res_total['PN'] == pn_actual].sort_values('COSTO')
            
            # Mostrar Info del producto
            st.subheader(f"🎯 Comparativa de Costos: {pn_actual}")
            if not datos_pn.empty:
                st.info(f"📝 {datos_pn['DESC'].iloc[0]}")
                
                # Tarjetas locales (Máximo 4 por fila)
                grid = st.columns(4)
                margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
                
                for idx, (_, r) in enumerate(datos_pn.iterrows()):
                    pvp = r['COSTO'] * (1 + (margen/100))
                    with grid[idx % 4]:
                        st.markdown(f"""
                        <div class="card">
                            <div class="vendor-name">{r['PROVEEDOR']}</div>
                            <div class="price-val">{r['COSTO']:.2f}€</div>
                            <div class="pvp-val">PVP Sugerido: {pvp:.2f}€</div>
                            <div class="stock-val">📦 Stock: <b>{r['STOCK']}</b></div>
                        </div>
                        """, unsafe_allow_html=True)

            # --- PANEL DE REFERENCIAS (TABLA NAVEGABLE) ---
            st.divider()
            st.subheader("📋 Resumen de Referencias Encontradas")
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            seleccion = st.dataframe(
                res_resumen, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row", 
                key="nav_table_v48"
            )

            # Cambio de PN al hacer clic en la fila
            if seleccion and seleccion.selection.rows:
                idx = seleccion.selection.rows[0]
                st.session_state["pn_activo"] = res_resumen.iloc[idx]['PN']
                st.rerun()

    # Sidebar: Acciones globales
    st.sidebar.divider()
    if st.sidebar.button("🔄 Forzar Recarga de Inventarios"):
        st.cache_data.clear()
        st.rerun()
