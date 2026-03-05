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
    st.set_page_config(page_title="AI Inventory Console v4.6", layout="wide")
    
    # CSS: Estilos para tarjetas y el nuevo panel ITscope
    st.markdown("""
        <style>
        .card {
            background: #ffffff; padding: 15px; border-radius: 10px;
            border-top: 4px solid #ff6000; box-shadow: 0 4px 6px rgba(0,0,0,0.07);
            margin-bottom: 20px; min-height: 190px;
        }
        .itscope-box {
            background: #f1f3f5; padding: 15px; border-radius: 10px;
            border: 1px solid #dee2e6;
        }
        .itscope-item {
            display: flex; justify-content: space-between; 
            padding: 5px 0; border-bottom: 1px solid #e9ecef;
            font-size: 13px;
        }
        .vendor-name { font-size: 11px; color: #888; font-weight: bold; text-transform: uppercase; }
        .price-val { font-size: 24px; font-weight: bold; color: #1d1d1b; }
        .pvp-val { color: #ff6000; font-size: 18px; font-weight: bold; }
        .savings-tag { background: #e8f5e9; color: #2e7d32; padding: 4px 8px; border-radius: 5px; font-size: 11px; font-weight: bold; }
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

    # --- FUNCIÓN ITSCOPE ---
    def obtener_itscope(pn):
        try:
            url = f"https://api.itscope.com/2.0/t/86MIdkfqPjtK_SDiprcfaKp1l_hWeIgtka9oYRZLH3X95Vje82UP7nh1rcwaLTaUHXj2MELgGTBusiarXbby2Z5BJeJqHS-5ASq9CRl76fYlf9Dhu7K3dY5tZNp_fMZ7-iUmn4JhGS0D7mwHNH7eo7oEyeFA8tbBGyjwyYJxfSc?q={pn}"
            r = requests.get(url, timeout=5)
            # Simulación de parseo (Ajustar según respuesta real XML/JSON de ITscope)
            # Aquí asumimos que buscamos los 5 mejores precios externos
            return [("Market A", "45.20€"), ("Market B", "46.10€"), ("Market C", "47.00€"), ("Market D", "48.50€"), ("Market E", "49.00€")]
        except: return []

    db = cargar_datos_locales()

    st.title("🤖 AI Inventory Console v4.6")
    
    margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
    entrada = st.text_input("🔍 Pega tus PN separados por |", placeholder="Ej: PN1 | PN2").upper()

    if entrada:
        pns_buscados = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns_buscados)]

        if not res_total.empty:
            if "pn_activo" not in st.session_state or st.session_state["pn_activo"] not in pns_buscados:
                st.session_state["pn_activo"] = pns_buscados[0]

            pn_actual = st.session_state["pn_activo"]
            
            # --- LAYOUT SUPERIOR: TARJETAS (IZQ) + ITSCOPE (DER) ---
            col_izq, col_der = st.columns([3, 1])

            with col_izq:
                datos_pn = res_total[res_total['PN'] == pn_actual].sort_values('COSTO')
                st.subheader(f"🎯 Ofertas para: {pn_actual}")
                st.caption(f"📝 {datos_pn['DESC'].iloc[0] if not datos_pn.empty else ''}")
                
                if not datos_pn.empty:
                    costo_min = datos_pn['COSTO'].min()
                    grid = st.columns(2) # Ajustado para que quepan bien al lado de ITscope
                    for idx, (_, r) in enumerate(datos_pn.iterrows()):
                        pvp = r['COSTO'] * (1 + (margen/100))
                        with grid[idx % 2]:
                            st.markdown(f"""
                            <div class="card">
                                <div class="vendor-name">{r['PROVEEDOR']}</div>
                                <div class="price-val">{r['COSTO']:.2f}€</div>
                                <div class="pvp-val">PVP: {pvp:.2f}€</div>
                                <div style="margin: 10px 0;">
                                    {'<span class="savings-tag">⭐ MEJOR PRECIO</span>' if r['COSTO'] == costo_min else f'<span>Dif: +{(r["COSTO"]-costo_min):.2f}€</span>'}
                                </div>
                                <p style="font-size:13px; margin:0;">📦 Stock: <b>{r['STOCK']}</b></p>
                            </div>
                            """, unsafe_allow_html=True)

            with col_der:
                st.markdown(f'### 📊 Market Top 5 (ITscope)')
                it_precios = obtener_itscope(pn_actual)
                if it_precios:
                    html_it = '<div class="itscope-box">'
                    for vend, precio in it_precios:
                        html_it += f'<div class="itscope-item"><span>{vend}</span><b>{precio}</b></div>'
                    html_it += '</div>'
                    st.markdown(html_it, unsafe_allow_html=True)
                else:
                    st.info("No hay datos externos para esta referencia.")

            # --- TABLA DE NAVEGACIÓN ---
            st.divider()
            st.subheader("📋 Panel de Referencias")
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            seleccion = st.dataframe(
                res_resumen, use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row", key="tabla_nav"
            )

            if seleccion and seleccion.selection.rows:
                idx = seleccion.selection.rows[0]
                nuevo_pn = res_resumen.iloc[idx]['PN']
                if nuevo_pn != st.session_state["pn_activo"]:
                    st.session_state["pn_activo"] = nuevo_pn
                    st.rerun()

            # --- EXPORTAR ---
            st.sidebar.divider()
            if st.sidebar.button("📥 Generar Excel"):
                df_pivot = res_total.pivot_table(index=['PN', 'DESC'], columns='PROVEEDOR', values=['COSTO', 'STOCK'], aggfunc='first')
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_pivot.to_excel(writer, sheet_name='Comparativa')
                st.sidebar.download_button("Descargar Archivo", output.getvalue(), "comparativa.xlsx")

    if st.sidebar.button("🔄 Forzar Recarga"):
        st.cache_data.clear()
        st.rerun()
