import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="RCA Platform | Monitor en Vivo",
    page_icon="🔍",
    layout="wide"
)

FASTAPI_URL = "http://isolation-backend:8000/analize" 
OLLAMA_URL = ""

st.title("🔍 Analizador de Causa Raíz (RCA)")
st.markdown("Monitor de anomalías en tiempo real usando Isolation Forest.")
st.divider()

# ========================
# 1. FUNCIONES AUXILIARES 
# ========================
@st.cache_data(ttl=5)
def fetch_predictions():
    try:
        response = requests.get(FASTAPI_URL, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"Error del backend: {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        st.error(f"No se pudo conectar con el motor analítico: {e}")
        return None

def anomaly_format(logs_anomalos):
    """Convierte los logs del Isolation Forest en una historia legible"""
    if not logs_anomalos:
        return "No hay datos."
    
    trace_id = logs_anomalos[0].get("traceId", "Desconocido")
    historia = f"TRACE_ID: {trace_id}\n\n"
    
    for i, log in enumerate(logs_anomalos, start=1):
        servicio = log.get("service", log.get("uri_servicio", "Desconocido"))
        duracion = log.get("duration_ms", "Desconocido")
        evento = log.get("event_type", "ERROR")
        texto = log.get("error_message", log.get("texto_completo", "Sin descripción"))
        
        historia += f"EVENTO {i} (DURACION: {duracion}ms):\n"
        historia += f"- SERVICIO: {servicio}\n"
        historia += f"- TIPO EVENTO: {evento}\n"
        historia += f"- MENSAJE: {texto}\n"
        historia += "-" * 40 + "\n"
    return historia

def call_ai(texto_formateado):
    
    try:
        respuesta = requests.post(OLLAMA_URL, json=texto_formateado, timeout=60)
        if respuesta.status_code == 200:
            return respuesta.json().get("response", "Respuesta vacía del modelo.")
        return f"Error en Ollama: {respuesta.status_code}"
    except Exception as e:
        return f"Error conectando a Ollama: {str(e)}"

# =============================
# 2. PANEL DE CONTROL Y LÓGICA
# =============================
with st.sidebar:
    st.header("⚙️ Controles")
    if st.button("🔄 Actualizar", use_container_width=True):
        st.cache_data.clear()
    
    st.info("El panel extrae las anomalías devueltas por el modelo de IA y genera visualizaciones en tiempo real.")

datos_api = fetch_predictions()

if datos_api:
    total_analizado = datos_api.get("total_analizado", 0)
    total_anomalias = datos_api.get("total_anomalias", 0)
    total_saludables = total_analizado - total_anomalias
    lista_anomalias = datos_api.get("anomalias", [])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Peticiones Analizadas", total_analizado)
    col2.metric("Tráfico Saludable", total_saludables)
    col3.metric("Anomalías Detectadas", total_anomalias, delta_color="inverse")
    st.divider()

    st.subheader("📊 Distribución del Tráfico")
    df_grafico = pd.DataFrame({"Estado": ["Saludable", "Anomalías"], "Volumen": [total_saludables, total_anomalias]})
    st.bar_chart(df_grafico.set_index("Estado"), use_container_width=True)
    st.divider()
    
    # --- VISUALIZACIÓN DE ALERTAS EN TABLA ---
    if total_anomalias > 0 and lista_anomalias:
        df_anomalias = pd.DataFrame(lista_anomalias)
        st.error(f"🚨 ¡ALERTA! Se han detectado {total_anomalias} logs anómalos.")
        
        columnas_a_mostrar = [col for col in ['traceId', 'level', 'event_type', 'http_status', 'duration_ms', 'service'] if col in df_anomalias.columns]
        st.dataframe(df_anomalias[columnas_a_mostrar], use_container_width=True, hide_index=True)
        
        st.divider()

        # ================
        # 3. SECCIÓN RAG 
        # ================
        st.subheader("🧠 Asistente Forense IA (RCA)")
        st.markdown("Selecciona un incidente para generar un informe automático de causa raíz.")
        
        trace_ids_unicos = df_anomalias['traceId'].unique()
        
        col_ctrl, col_result = st.columns([1, 2])
        
        with col_ctrl:
            trace_seleccionado = st.selectbox("Selecciona un Trace ID:", trace_ids_unicos)
            
            btn_analizar = st.button("Generar Informe RCA 🚀", type="primary", use_container_width=True)
            
        with col_result:
            if btn_analizar:
                with st.spinner(f"Agrupando logs y analizando con Llama 3.2..."):
                    logs_filtrados = [log for log in lista_anomalias if log.get('traceId') == trace_seleccionado]
                    
                    texto_historia = anomaly_format(logs_filtrados)
                    
                    reporte_ia = call_ai(texto_historia)
                    
                    st.success("Análisis completado:")
                    st.markdown(reporte_ia)
                    
                    with st.expander("Ver historia enviada a la IA"):
                        st.text(texto_historia)

    else:
        st.success("✅ No se detectan anomalías.")

else:
    st.warning("Esperando datos de telemetría de Loki y FastAPI...")