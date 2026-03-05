import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- 1. CONFIGURACIÓN DE ALTO RENDIMIENTO ---
st.set_page_config(page_title="Price Intel v6.2 - Professional", layout="wide")

# Estilo CSS Restaurado y Mejorado
st.markdown("""
    <style>
    .price-card {
        background: white; border-radius: 10px; padding: 18px;
        border-top: 4px solid #ff6000; box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        margin-bottom: 15px; text-align: center; transition: 0.3s;
    }
    .price-card:hover { transform: translateY(-3px); box-shadow: 0 6px 12px rgba(0,0,0,0.1); }
    .vendor { font-size: 0.7rem; color: #888; font-weight: bold; text-transform: uppercase; letter-spacing: 1px; }
    .price { font-size: 1.8rem; font-weight: 800; color: #111; margin: 5px 0; }
    .pvp { color: #ff6000; font-weight: 700; font-size: 1.1rem; border-top: 1px solid #eee; padding-top: 8px; }
    .stock-tag { font-size: 0.8rem; background: #f1f3f5; color: #444; padding: 3px 8px; border-radius: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SISTEMA DE SEGURIDAD RESTAURADO ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Restringido")
        pwd = st.text_input("Clave de Seguridad", type="password")
        if st.button("Desbloquear Sistema"):
            if pwd == st.secrets["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        return False
    return True

if check_password():
    # --- 3. MOTOR DE DATOS (7 PROVEEDORES + VELOCIDAD C) ---
    @st.cache_data(ttl=3600, show_spinner="Sincronizando Mayoristas...")
    def cargar_datos_maestros():
        # Diccionario con los 7 proveedores y sus columnas específicas
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"},
            "SYK": {"url": "TU_URL_SYK", "sep": ";", "cols": [0, 4, 5, 1], "enc": "utf-8"},
            "JARLTECH": {"url": "TU_URL_JARLTECH", "sep": ";", "cols": [0, 5, 8, 1], "enc": "utf-8"},
            "KOSATEK": {"url": "TU_URL_KOSATEK", "sep": ";", "cols": [1, 10, 15, 2], "enc": "utf-8"}
        }

        def fetch_worker(nombre, cfg):
            try:
                if "TU_URL" in cfg["url"]: return pd.DataFrame()
                r = requests.get(cfg["url"], timeout=10)
                # Engine 'c' para velocidad máxima
                df = pd.read_csv(io.BytesIO(r.content), sep=cfg["sep"], usecols=cfg["cols"], 
                                 encoding=cfg["enc"], on_bad_lines='skip', engine='c')
                
                # Procesamiento vectorial (rápido)
                res = pd.DataFrame({
                    'PN': df.iloc[:, 0].astype(str).str.upper().str.strip(),
                    'COSTO': pd.to_numeric(df.iloc[:, 1].astype(str).str.replace(',', '.').str.extract('(\d+\.?\d*)')[0], errors='coerce'),
                    'STOCK': df.iloc[:, 2].fillna('0'),
                    'DESC': df.iloc[:, 3].fillna('Sin descripción'),
                    'PROVEEDOR': nombre
                })
                return res.dropna(subset=['COSTO'])
            except:
                return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=7) as executor:
            results = list(executor.map(lambda p: fetch_worker(*p), PROVEEDORES.items()))
        
        return pd.concat(results, ignore_index=True)

    db = cargar_datos_maestros()

    # --- 4. INTERFAZ DE USUARIO ---
    st.title("⚡ Price Intel v6.2")
    
    # Buscador principal
    entrada = st.text_input("🔍 Introduce Part Number (puedes usar | para varios)", placeholder="Ej: ZT-D40710D-10P").strip().upper()

    if entrada:
        target_pns = [p.strip() for p in entrada.split('|') if p.strip()]
        res_total = db[db['PN'].isin(target_pns)]

        if not res_total.empty:
            # Mantener el PN activo en memoria
            if "pn_activo" not in st.session_state or st.session_state["pn_activo"] not in target_pns:
                st.session_state["pn_activo"] = target_pns[0]
            
            pn_sel = st.session_state["pn_activo"]
            
            # --- ZONA DE TARJETAS (FRAGMENTADA PARA VELOCIDAD) ---
            @st.fragment
            def mostrar_precios(pn):
                datos_pn = res_total[res_total['PN'] == pn].sort_values('COSTO')
                st.subheader(f"📦 Referencia: {pn}")
                st.info(datos_pn['DESC'].iloc[0] if not datos_pn.empty else "Sin descripción")
                
                margen = st.sidebar.slider("Margen Comercial %", 0, 50, 15)
                
                grid = st.columns(4)
                for idx, (_, row) in enumerate(datos_pn.iterrows()):
                    pvp = row['COSTO'] * (1 + (margen/100))
                    with grid[idx % 4]:
                        st.markdown(f"""
                        <div class="price-card">
                            <div class="vendor">{row['PROVEEDOR']}</div>
                            <div class="price">{row['COSTO']:.2f}€</div>
                            <div class="pvp">PVP SUG: {pvp:.2f}€</div>
                            <div class="stock-tag">Stock: {row['STOCK']}</div>
                        </div>
                        """, unsafe_allow_html=True)

            mostrar_precios(pn_sel)

            # --- TABLA DE NAVEGACIÓN RESTAURADA ---
            st.divider()
            st.subheader("📋 Resumen de la búsqueda")
            resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            # El on_select permite volver a tener la interactividad de la tabla
            tabla = st.dataframe(resumen, use_container_width=True, hide_index=True, 
                                 on_select="rerun", selection_mode="single-row")

            if tabla and tabla.selection.rows:
                st.session_state["pn_activo"] = resumen.iloc[tabla.selection.rows[0]]['PN']
                st.rerun()
        else:
            st.error("No se encontraron resultados para esos PNs.")

    # Sidebar: Botón de refresco
    st.sidebar.divider()
    if st.sidebar.button("🔄 Forzar Sincronización"):
        st.cache_data.clear()
        st.rerun()
