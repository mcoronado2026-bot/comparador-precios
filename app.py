import streamlit as st
import pandas as pd
import requests
import io
from concurrent.futures import ThreadPoolExecutor

# --- SEGURIDAD ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else: st.session_state["password_correct"] = False
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso Restringido")
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    return st.session_state["password_correct"]

if check_password():
    st.set_page_config(page_title="Price Intel Pro v4.4", layout="wide")
    
    # CSS Optimizado: Tarjetas compactas y alineación
    st.markdown("""
        <style>
        .card {
            background: #f8f9fa; padding: 15px; border-radius: 10px;
            border-top: 4px solid #ff6000; box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px; min-height: 180px;
        }
        .vendor-name { font-size: 12px; color: #666; font-weight: bold; text-transform: uppercase; }
        .price-val { font-size: 24px; font-weight: bold; color: #1d1d1b; }
        .pvp-val { color: #ff6000; font-size: 20px; font-weight: bold; }
        .savings { color: #28a745; font-size: 13px; font-weight: bold; }
        </style>
        """, unsafe_allow_html=True)

    @st.cache_data(ttl=3600)
    def cargar_datos_seguro():
        # Añadimos columna de descripción (índice extra en cada proveedor)
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

    db = cargar_datos_seguro()

    # --- INTERFAZ SUPERIOR ---
    st.title("🧡 Console Price Intelligence")
    entrada = st.text_input("🔍 Pega tus PN separados por |", placeholder="PN1 | PN2...").upper()
    margen = st.sidebar.slider("Margen (%)", 0, 50, 15)

    if entrada:
        pns_buscados = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns_buscados)]

        if not res_total.empty:
            # Lógica de Selección (Recuadro Verde ahora abajo)
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            # Determinamos qué PN mostrar basándonos en la selección o el primero por defecto
            pn_seleccionado = pns_buscados[0]
            
            # --- ZONA DE VENTAS (ARRIBA) ---
            st.divider()
            # Buscamos la descripción para el PN actual
            desc_actual = res_total[res_total['PN'] == pn_seleccionado]['DESC'].iloc[0] if pn_seleccionado in res_total['PN'].values else "Sin descripción"
            
            st.subheader(f"🎯 Ofertas para: {pn_seleccionado}")
            st.caption(f"📝 {desc_actual}")

            ofertas = res_total[res_total['PN'] == pn_seleccionado].sort_values('COSTO')
            costo_min = ofertas['COSTO'].min()
            costo_max = ofertas['COSTO'].max()

            cols = st.columns(4)
            for i, (_, r) in enumerate(ofertas.iterrows()):
                pvp = r['COSTO'] * (1 + (margen/100))
                ahorro = costo_max - r['COSTO']
                with cols[i % 4]:
                    st.markdown(f"""
                    <div class="card">
                        <div class="vendor-name">{r['PROVEEDOR']}</div>
                        <div class="price-val">{r['COSTO']:.2f}€</div>
                        <div class="pvp-val">PVP: {pvp:.2f}€</div>
                        <div class="savings">{'🔥 Mejor Precio' if r['COSTO'] == costo_min else f'Ahorro: {ahorro:.2f}€'}</div>
                        <p style="margin-top:10px; font-size:13px;">📦 Stock: {r['STOCK']}</p>
                    </div>
                    """, unsafe_allow_html=True)

            # --- TABLA DE NAVEGACIÓN (ABAJO / RECUADRO VERDE) ---
            st.divider()
            st.subheader("📋 Panel de Referencias (Pincha una fila para cambiar)")
            
            event = st.dataframe(
                res_resumen,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row"
            )

            # Si el usuario hace clic, actualizamos el PN seleccionado y forzamos refresco
            if event and event.selection.rows:
                idx = event.selection.rows[0]
                nuevo_pn = res_resumen.iloc[idx]['PN']
                if nuevo_pn != pn_seleccionado:
                    # Usamos un pequeño truco de estado para recordar la selección
                    st.session_state["ultimo_pn"] = nuevo_pn
                    st.rerun()

    if st.sidebar.button("🔄 Limpiar Caché"):
        st.cache_data.clear()
        st.rerun()
