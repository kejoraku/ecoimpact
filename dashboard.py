import streamlit as st
import folium
from streamlit_folium import st_folium
import requests
import json
import ee
from calculos_gee import obtener_todas_las_capas_gee
import subprocess
import sys

# --- PIPELINE AUTOMÁTICO DE LIBRERÍAS ---
try:
    from google import genai
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-genai"])
    from google import genai

# --- INICIALIZACIÓN INDUSTRIAL DE GOOGLE EARTH ENGINE ---
try:
    # Si la app corre en internet, lee la clave metida en tres comillas desde tus secretos
    if "gcp" in st.secrets and "service_account" in st.secrets["gcp"]:
        json_en_texto = st.secrets["gcp"]["service_account"]
        config_credenciales = json.loads(json_en_texto)
        
        credenciales_oficiales = ee.ServiceAccountCredentials(
            config_credenciales["client_email"],
            key_data=json.dumps(config_credenciales)
        )
        ee.Initialize(credentials=credenciales_oficiales, project='ee-raanidg')
    else:
        # Fallback de seguridad para tu entorno local
        ee.Initialize(project='ee-raanidg')
except Exception as e:
    st.error(f"⚠️ GEE no inicializado. Revisa tu consola: {e}")

st.set_page_config(page_title="EcoImpact AI - Argentina", layout="wide")
st.title("🌍 EcoImpact AI: Análisis de Desastres y Biodiversidad en Argentina")
st.write("Geodashboard analítico con pre-procesamiento de bandas en paralelo.")

# --- PIPELINE DE ATRIBUTOS BIOLÓGICOS (LIBRERÍA OFICIAL PYGBIF) ---
@st.cache_data(ttl=600)
def descargar_fauna_argentina_real(anio):
    import pygbif
    registros_totales = []
    try:
        respuesta = pygbif.occurrences.search(country='AR', year=int(anio), hasCoordinate=True, limit=40)
        st.sidebar.success("📡 Conexión GBIF: 200 OK")
        results = respuesta.get('results', [])
        for r in results:
            clase_orig = r.get("class", "Otros")
            r["grupo_espanol"] = "Mamíferos" if clase_orig == "Mammalia" else "Aves" if clase_orig == "Aves" else "Reptiles" if clase_orig == "Reptilia" else f"Fauna ({clase_orig})"
            registros_totales.append(r)
    except:
        pass
    return registros_totales

# Interfaz Barra Lateral
st.sidebar.header("⚙️ Configuración")
tipo_busqueda = st.sidebar.radio("Selecciona el tipo de análisis:", ["Año Único", "Período (Hasta 3 años)"])

if tipo_busqueda == "Año Único":
    anio_inicio = st.sidebar.slider("Selecciona el año:", 2015, 2025, 2022)
    anios_a_procesar = [anio_inicio]
else:
    anio_inicio = st.sidebar.slider("Año de Inicio:", 2015, 2024, 2020)
    anio_fin = st.sidebar.slider("Año de Fin (Máx. 3 años):", anio_inicio, min(anio_inicio + 2, 2025), anio_inicio + 2)
    anios_a_procesar = list(range(anio_inicio, anio_fin + 1))

st.sidebar.subheader("🔑 Credenciales")
api_key_openai = st.sidebar.text_input("Ingresa tu Google Gemini API Key:", type="password")
procesar_ia = st.sidebar.button("🤖 Generar Informe Ecológico con IA")

# Panel Principal de Pestañas
st.subheader("🗺️ Capas Espaciales Automatizadas")
tabs = st.tabs([f"Año {anio}" for anio in anios_a_procesar])
datos_para_la_ia = {}

for i, tab in enumerate(tabs):
    anio_actual = anios_a_procesar[i]
    with tab:
        st.write(f"### Mapeo Integrado para el año {anio_actual}")
        
        if f"cache_{anio_actual}" not in st.session_state:
            with st.spinner(f"Cargando telemetría paralela y biodiversidad para {anio_actual}..."):
                especies = descargar_fauna_argentina_real(anio_actual)
                diccionario_capas, sat_activo = obtener_todas_las_capas_gee(anio_actual)
                st.session_state[f"cache_{anio_actual}"] = {"especies": especies, "capas": diccionario_capas, "sat": sat_activo}
        
        info_memoria = st.session_state[f"cache_{anio_actual}"]
        especies = info_memoria["especies"]
        diccionario_capas = info_memoria["capas"]
        sat_activo = info_memoria["sat"]
        
        st.success(f"💥 ¡Éxito! Satélite Activo: {sat_activo} | Registros de GBIF: {len(especies)}")
        st.caption("ℹ️ Abre el control de capas flotante arriba a la derecha del mapa para alternar entre tus 4 índices.")

        datos_para_la_ia[anio_actual] = {
            "satelite_origen": sat_activo,
            "indices_calculados": list(diccionario_capas.keys()),
            "taxones_registrados": [{"cientifico": esp.get("scientificName"), "grupo": esp.get("grupo_espanol")} for esp in especies[:10]]
        }

        # --- MAPA INTERACTIVO CON CONTROL DE CAPAS PROFESIONAL ---
        m = folium.Map(location=[-40.0, -65.0], zoom_start=4)
        
        if "NBRI" in diccionario_capas:
            folium.TileLayer(tiles=diccionario_capas["NBRI"], attr='GEE', name='🔥 Incendios Forestales (NBRI)', overlay=True, opacity=0.7, show=True).add_to(m)
        if "NDWI" in diccionario_capas:
            folium.TileLayer(tiles=diccionario_capas["NDWI"], attr='GEE', name='💧 Clima Extremo / Agua (NDWI)', overlay=True, opacity=0.7, show=False).add_to(m)
        if "OSI" in diccionario_capas:
            folium.TileLayer(tiles=diccionario_capas["OSI"], attr='GEE', name='🛢️ Derrames Hidrocarburos (OSI)', overlay=True, opacity=0.7, show=False).add_to(m)
        if "NDSI" in diccionario_capas:
            folium.TileLayer(tiles=diccionario_capas["NDSI"], attr='GEE', name='❄️ Índice de Nieve (NDSI)', overlay=True, opacity=0.7, show=False).add_to(m)

        for esp in especies:
            lat, lon = esp.get("decimalLatitude"), esp.get("decimalLongitude")
            if lat and lon:
                grupo = esp.get("grupo_espanol")
                color = "red" if grupo == "Mamíferos" else "blue" if grupo == "Aves" else "purple" if grupo == "Reptiles" else "orange"
                folium.Marker(location=[lat, lon], popup=f"<b>{esp.get('scientificName')}</b>", icon=folium.Icon(color=color, icon="leaf")).add_to(m)
        
        folium.LayerControl(position='topright', collapsed=False).add_to(m)
        st_folium(m, use_container_width=True, height=580, key=f"geodashboard_mapa_{anio_actual}")

# --- MÓDULO FINAL: CONEXIÓN INDUSTRIAL MEDIANTE SDK OFICIAL (MIGRADO A INTERACTIONS API) ---
if procesar_ia:
    st.subheader("🤖 Informe Metodológico Estructurado con IA")
    
    if not api_key_openai:
        st.warning("⚠️ Por favor, ingresa tu Google Gemini API Key en la barra lateral izquierda.")
    else:
        with st.status("🤖 Conectando con Google Gemini mediante Interactions API...", expanded=True) as status_progreso:
            try:
                from google import genai
                
                # Inicialización limpia de la IA
                client = genai.Client(api_key=str(api_key_openai).strip())
                paquete_contexto_ia = json.dumps(datos_para_la_ia, ensure_ascii=False)
                
                prompt_contenido = f"""
                Actúa como un Ecólogo GIS Senior de Argentina. Analiza la siguiente matriz multitemporal combinada de bandas satelitales y registros de campo de Argentina: {paquete_contexto_ia}. 
                Debes entregar OBLIGATORIAMENTE un JSON estructurado con este formato estricto y sin texto extra: 
                {{
                  "nivel_alerta_global": "Bajo, Medio o Crítico",
                  "diagnostico_metodologico": "Un párrafo científico analítico detallando la relación entre los índices de las bandas y las especies.",
                  "anos_recuperacion_estimados": 5
                }}
                """
                
                                # 1. Ejecutamos la consulta con el tipo corregido para Interactions API
                interaction = client.interactions.create(
                    model='gemini-3.5-flash', 
                    input=prompt_contenido,
                    response_format={"type": "string"}  # Evita el bloqueo del objeto vacío y permite salida libre
                )
                
                # 2. Extraemos el texto crudo del informe generado
                texto_json_puro = interaction.output_text
                
                # 3. Convertimos el texto string a diccionario real de Python
                resultado_json = json.loads(texto_json_puro)

                # 4. Actualizamos el estado de la barra de progreso
                status_progreso.update(label="¡Informe técnico generado con éxito!", state="complete")
                
                # 5. Renderizado de métricas en la interfaz de Streamlit
                col_ia1, col_ia2 = st.columns(2)
                with col_ia1: 
                    st.metric(label="Dictamen de Alerta", value=resultado_json.get("nivel_alerta_global", "N/A"))
                with col_ia2: 
                    st.metric(label="Tiempo de Recuperación", value=f"{resultado_json.get('anos_recuperacion_estimados', 0)} años")
                
                st.info(f"**Análisis Metodológico del Ecólogo (IA):**\n\n{resultado_json.get('diagnostico_metodologico')}")
                with st.expander("🔍 Ver Estructura JSON de Salida Dirigida (Requisito de Cátedra)"): 
                    st.json(resultado_json)
                    
            except Exception as e:
                status_progreso.update(label="🚨 Error en el procesamiento de Interactions", state="error")
                st.exception(e)
