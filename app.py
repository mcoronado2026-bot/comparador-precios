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
    st.set_page_config(page_title="Price Intel Pro v4.5", layout="wide")
    
    # CSS para diseño profesional y tarjetas responsive
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
        </style>
        """, unsafe_allow_html=True)

    # --- MOTOR DE DATOS (CON PARALELISMO Y CACHÉ) ---
    @st.cache_data(ttl=3600)
    def cargar_datos_seguro():
        # Diccionario con URLs corregidas en una sola línea para evitar SyntaxError
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
    st.title("🧡 Console Price v4.5")
    
    # Barra lateral
    margen = st.sidebar.slider("Margen de beneficio (%)", 0, 50, 15)
    if st.sidebar.button("🔄 Forzar Recarga de Datos"):
        st.cache_data.clear()
        st.rerun()

    # Buscador principal
    entrada = st.text_input("🔍 Pega tus PN separados por |", placeholder="Ej: PN1 | PN2 | PN3").upper()

    if entrada:
        pns_buscados = [x.strip() for x in entrada.split('|') if x.strip()]
        res_total = db[db['PN'].isin(pns_buscados)]

        if not res_total.empty:
            # Resumen para la tabla (Recuadro Verde)
            res_resumen = res_total.sort_values('COSTO').groupby('PN').head(1)[['PN', 'DESC', 'COSTO', 'PROVEEDOR']]
            
            # Gestión del PN activo mediante Session State
            if "pn_activo" not in st.session_state or st.session_state["pn_activo"] not in pns_buscados:
                st.session_state["pn_activo"] = pns_buscados[0]

            # --- ZONA DE TARJETAS (VENTAS) ---
            pn_actual = st.session_state["pn_activo"]
            datos_pn = res_total[res_total['PN'] == pn_actual].sort_values('COSTO')
            
            if not datos_pn.empty:
                desc_label = datos_pn['DESC'].iloc[0]
                st.subheader(f"🎯 Ofertas para: {pn_actual}")
                st.caption(f"📝 {desc_label}")

                costo_min = datos_pn['COSTO'].min()
                costo_max = datos_pn['COSTO'].max()

                # Grid Responsive de 4 columnas
                grid = st.columns(4)
                for idx, (_, r) in enumerate(datos_pn.iterrows()):
                    pvp = r['COSTO'] * (1 + (margen/100))
                    ahorro = costo_max - r['COSTO']
                    with grid[idx % 4]:
                        st.markdown(f"""
                        <div class="card">
                            <div class="vendor-name">{r['PROVEEDOR']}</div>
                            <div class="price-val">{r['COSTO']:.2f}€</div>
                            <div class="pvp-val">PVP: {pvp:.2f}€</div>
                            <div style="margin: 10px 0;">
                                {'<span class="savings-tag">⭐ MEJOR PRECIO</span>' if r['COSTO'] == costo_min else f'<span style="color:gray; font-size:12px;">Dif: +{ahorro:.2f}€</span>'}
                            </div>
                            <p style="font-size:13px; margin:0;">📦 Stock: <b>{r['STOCK']}</b></p>
                        </div>
                        """, unsafe_allow_html=True)
            
            # --- TABLA DE NAVEGACIÓN (RECUADRO VERDE) ---
            st.divider()
            st.subheader("📋 Panel de Referencias (Selecciona una fila para actualizar tarjetas)")
            
            seleccion = st.dataframe(
                res_resumen,
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="tabla_navegacion"
            )

            # Lógica para cambiar de producto al hacer clic en la tabla
            if seleccion and seleccion.selection.rows:
                fila_idx = seleccion.selection.rows[0]
                nuevo_pn = res_resumen.iloc[fila_idx]['PN']
                if nuevo_pn != st.session_state["pn_activo"]:
                    st.session_state["pn_activo"] = nuevo_pn
                    st.rerun()

            # --- SECCIÓN DE EXPORTACIÓN ---
            st.sidebar.divider()
            st.sidebar.subheader("📦 Exportar Resultados")
            
            # Preparar datos pivotados (cada proveedor en una columna)
            try:
                df_pivot = res_total.pivot_table(index=['PN', 'DESC'], columns='PROVEEDOR', values=['COSTO', 'STOCK'], aggfunc='first')
                
                # Botón Excel
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_pivot.to_excel(writer, sheet_name='Comparativa')
                
                st.sidebar.download_button(
                    label="📥 Descargar Excel Completo",
                    data=output.getvalue(),
                    file_name="comparativa_precios.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                
                # Botón XML
                xml_data = res_total.to_xml(index=False)
                st.sidebar.download_button(
                    label="📄 Descargar XML",
                    data=xml_data,
                    file_name="datos_proveedores.xml",
                    mime="application/xml"
                )
            except:
                st.sidebar.warning("No se pudo generar la exportación con los datos actuales.")
        else:
            st.warning("No se encontraron resultados para esas referencias.")
   

