import streamlit as st
import pandas as pd
import requests
import io
import re
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURACIÓN DE SEGURIDAD (Secrets) ---
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
    st.set_page_config(page_title="Price Intel Pro v4.3", layout="wide")
    
    # CSS para Tarjetas Compactas (Mitad de ancho, 4 por fila)
    st.markdown("""
        <style>
        .card {
            background: white; padding: 12px; border-radius: 10px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 5px solid #ff6000;
            margin-bottom: 10px; height: 160px;
        }
        .price { font-size: 22px; font-weight: bold; color: #1d1d1b; }
        .pvp { color: #ff6000; font-size: 18px; font-weight: bold; }
        .vendor { font-size: 14px; color: #666; text-transform: uppercase; letter-spacing: 1px; }
        </style>
        """, unsafe_allow_html=True)

    HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}

    @st.cache_data(ttl=3600)
    def cargar_datos_seguro():
        PROVEEDORES = {
            "DEPAU": {"url": "https://www.depau.es/webservices/tarifa_completa/84acda65-a18c-4dc7-87d8-afc8f54616ba/csv", "sep": "\t", "cols": [9, 2, 8], "enc": "utf-8"},
            "INFORTISA": {"url": "https://apiv2.infortisa.com/api/Tarifa/GetFileV5?user=4057C87D-91D1-42C9-A95F-D1FF8E30720E", "sep": ";", "cols": [0, 10, 11], "enc": "latin-1"},
            "GLOBOMATIK": {"url": "https://multimedia.globomatik.net/csv/import.php?username=31843&password=04665238&formato=csv&filter=PRESTAIMPORT&type=prestashop2&mode=all", "sep": ";", "cols": [1, 13, 12], "enc": "utf-8"},
            "DESYMAN": {"url": "https://desyman.com/module/ma_desyman/download_rate_customer?token=68c40ea1aa4df9db6e2614a6b79bcb48&format=CSVreducido", "sep": ";", "cols": [2, 7, 3], "enc": "utf-8"}
        }
        
        def descargar(nombre, info):
            try:
                r = requests.get(info["url"], headers=HEADERS, timeout=15)
                df = pd.read_csv(io.StringIO(r.content.decode(info["enc"], errors='replace')), sep=info["sep"], on_bad_lines='skip', engine='python')
                t = pd.DataFrame()
                t['PN'] = df.iloc[:, info["cols"][0]].astype(str).str.upper().str.strip()
                t['COSTO'] = df.iloc[:, info["cols"][1]].replace(r'[^0-9,.]', '', regex=True).replace(',', '.', regex=True).astype(float)
                t['STOCK'] = df.iloc[:, info["cols"][2]].astype(str)
                t['PROVEEDOR'] = nombre
                return t
            except: return pd.DataFrame()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda p: descargar(*p), PROVEEDORES.items()))
        return pd.concat(results, ignore_index=True)

    st.title("🧡 Panel de Inteligencia Comercial")
    margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
    
    if st.sidebar.button("🔄 Actualizar Mayoristas"):
        st.cache_data.clear()
        st.rerun()

    db = cargar_datos_seguro()

    # 1. BUSCADOR MULTI-REFERENCIA
    entrada = st.text_input("🔍 Busca múltiples PN separados por |", placeholder="Ej: PN1 | PN2 | PN3").upper()

    if entrada:
        pns_buscados = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns_buscados)]

        if not res_total.empty:
            # 2. TABLA INTERACTIVA (Tu recuadro verde)
            st.subheader("📋 Resumen de Referencias Encontradas")
            # Agrupamos para mostrar la mejor opción de cada PN en la tabla
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'PROVEEDOR', 'COSTO', 'STOCK']]
            
            # Selector de fila (interacción del recuadro verde)
            seleccion = st.dataframe(
                res_resumen, 
                use_container_width=True, 
                hide_index=True, 
                on_select="rerun", 
                selection_mode="single-row"
            )

            # Lógica de selección: Primera línea por defecto o la que pinche el usuario
            pn_a_mostrar = pns_buscados[0] # Por defecto el primero
            if seleccion and seleccion.selection.rows:
                index_seleccionado = seleccion.selection.rows[0]
                pn_a_mostrar = res_resumen.iloc[index_seleccionado]['PN']

            # 3. TARJETAS DETALLADAS (Mitad de ancho, 4 por fila)
            st.divider()
            st.subheader(f"🏷️ Ofertas para: {pn_a_mostrar}")
            detalles = res_total[res_total['PN'] == pn_a_mostrar].sort_values('COSTO')
            
            # Generar Grid de 4 columnas
            cols = st.columns(4)
            for i, (_, r) in enumerate(detalles.iterrows()):
                pvp = r['COSTO'] * (1 + (margen/100))
                with cols[i % 4]:
                    st.markdown(f"""
                    <div class="card">
                        <div class="vendor">{r['PROVEEDOR']}</div>
                        <div class="price">{r['COSTO']:.2f}€ <small>(Costo)</small></div>
                        <div class="pvp">{pvp:.2f}€ <small>(PVP)</small></div>
                        <p style="margin-top:10px;">📦 Stock: <b>{r['STOCK']}</b></p>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.warning("No se encontraron resultados para esas referencias.")
