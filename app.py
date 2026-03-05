import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- SISTEMA DE SEGURIDAD (LOGIN) ---
def check_password():
    """Devuelve True si el usuario introdujo la contraseña correcta."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Eliminar de memoria por seguridad
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Introduce la contraseña de equipo", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.title("🔐 Acceso Restringido - Price Intel")
        st.text_input("Contraseña incorrecta. Inténtalo de nuevo", type="password", on_change=password_entered, key="password")
        st.error("😕 Acceso denegado")
        return False
    else:
        return True

if check_password():
    # --- CONFIGURACIÓN DE PÁGINA ---
    st.set_page_config(page_title="AI Inventory Console v4.5", layout="wide")
    
    # CSS para diseño profesional, tarjetas y el nuevo recuadro de ITscope
    st.markdown("""
        <style>
        .card {
            background: #ffffff; padding: 15px; border-radius: 10px;
            border-top: 4px solid #ff6000; box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-bottom: 20px; min-height: 190px; transition: 0.3s;
        }
        .card:hover { transform: translateY(-5px); }
        .vendor-name { font-size: 11px; color: #888; font-weight: bold; text-transform: uppercase; }
        .price-val { font-size: 26px; font-weight: bold; color: #1d1d1b; margin: 5px 0; }
        .pvp-val { color: #ff6000; font-size: 19px; font-weight: bold; }
        .savings-tag { background: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 5px; font-size: 12px; font-weight: bold; }
        .itscope-box {
            background-color: #f8f9fa; padding: 15px; border-radius: 10px;
            border: 1px solid #eaeaea; box-shadow: inset 0 2px 4px rgba(0,0,0,0.02);
        }
        </style>
        """, unsafe_allow_html=True)

    # --- FUNCIÓN ESPECÍFICA ITSCOPE ---
    def obtener_top5_itscope(pn):
        url_api = "https://api.itscope.com/2.0/t/86MIdkfqPjtK_SDiprcfaKp1l_hWeIgtka9oYRZLH3X95Vje82UP7nh1rcwaLTaUHXj2MELgGTBusiarXbby2Z5BJeJqHS-5ASq9CRl76fYlf9Dhu7K3dY5tZNp_fMZ7-iUmn4JhGS0D7mwHNH7eo7oEyeFA8tbBGyjwyYJxfSc"
        try:
            # Petición a la API de ITscope
            r = requests.get(url_api, timeout=10)
            df_it = pd.read_csv(io.StringIO(r.content.decode('utf-8')), sep=',', on_bad_lines='skip')
            
            # Limpieza de columnas para asegurar compatibilidad
            df_it.columns = [c.upper().strip() for c in df_it.columns]
            
            # Buscamos por la columna de referencia (ajustar si ITscope usa otro nombre de columna)
            # Suponemos que el CSV tiene 'PN' o 'MANUFACTURER_SKU'
            col_ref = 'PN' if 'PN' in df_it.columns else df_it.columns[0]
            col_precio = 'PRECIO' if 'PRECIO' in df_it.columns else df_it.columns[1]
            
            top5 = df_it[df_it[col_ref].astype(str).str.contains(pn, na=False)].sort_values(by=col_precio).head(5)
            return top5
        except:
            return None

    # --- MOTOR DE DATOS ORIGINAL ---
    @st.cache_data(ttl=3600)
    def cargar_datos_seguro():
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8, 3], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11, 1], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12, 2], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3, 1], "enc": "utf-8"}
        }
        
        def descargar(nombre, info):
            try:
                headers = {"User-Agent": "Mozilla/5.0"}
                r = requests.get(info["url"], headers=headers, timeout=15)
                df = pd.read_csv(io.StringIO(r.content.decode(info["enc"], errors='replace')), sep=info["sep"], on_bad_lines='skip', engine='python')
                t = pd.DataFrame()
                t['PN'] = df.iloc[:, info["cols"][0]].astype(str).str.upper().str.strip()
                t['COSTO'] = df.iloc[:, info["cols"][1]].replace(r'[^0-9,.]', '', regex=True).replace(',', '.', regex=True).astype(float)
                t['STOCK'] = df.iloc[:, info["cols"][2]].astype(str)
                t['DESC'] = df.iloc[:, info["cols"][3]].astype(str)
                t['PROVEEDOR'] = nombre
                return t
            except:
                return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: descargar(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    db = cargar_datos_seguro()

    # --- INTERFAZ DE USUARIO ---
    col_head, col_itscope = st.columns([2, 1])

    with col_head:
        st.title("🤖 AI Inventory Console v4.5") # Cambio de icono y título
        entrada = st.text_input("🔍 Pega tus PN separados por |", placeholder="Ej: PN1 | PN2 | PN3").upper()

    # Barra lateral
    margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
    if st.sidebar.button("🔄 Forzar Recarga de Datos"):
        st.cache_data.clear()
        st.rerun()

    if entrada:
        pns_buscados = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns_buscados)]

        # --- RECUADRO ITSCOPE (TOP 5) ---
        with col_itscope:
            st.markdown('<div class="itscope-box">', unsafe_allow_html=True)
            st.subheader("📊 Market Top 5 (ITscope)")
            # Usamos el primer PN de la lista para la consulta rápida
            pn_para_itscope = pns_buscados[0]
            top5_it = obtener_top5_itscope(pn_para_itscope)
            if top5_it is not None and not top5_it.empty:
                st.dataframe(top5_it, hide_index=True)
            else:
                st.caption("No hay datos externos para esta referencia.")
            st.markdown('</div>', unsafe_allow_html=True)

        if not res_total.empty:
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            if "pn_activo" not in st.session_state or st.session_state["pn_activo"] not in pns_buscados:
                st.session_state["pn_activo"] = pns_buscados[0]

            # --- ZONA DE TARJETAS ---
            pn_actual = st.session_state["pn_activo"]
            datos_pn = res_total[res_total['PN'] == pn_actual].sort_values('COSTO')
            
            if not datos_pn.empty:
                desc_label = datos_
   


