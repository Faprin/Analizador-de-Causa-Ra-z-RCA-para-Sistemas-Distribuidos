import streamlit as st
import requests
import pandas as pd

st.set_page_config(
    page_title="RCA Platform | Monitor en Vivo",
    page_icon="🔍",
    layout="wide"
)

FASTAPI_URL = "http://isolation-backend:8000/analize" 

st.title("🔍 Analizador de Causa Raíz (RCA)")
st.markdown("Monitor de anomalías en tiempo real usando Isolation Forest.")
st.divider()

# ===================================
# FUNCIÓN DE INGESTA DE DATOS
# ===================================
@st.cache_data(ttl=5) # Cache de 5 segundos
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

# --- PANEL DE CONTROL (SIDEBAR) ---
with st.sidebar:
    st.header("⚙️ Controles")
    if st.button("🔄 Actualizar", use_container_width=True):
        st.cache_data.clear()
    
    st.info("El panel extrae las anomalías devueltas por el modelo de IA y genera visualizaciones en tiempo real.")

# --- LÓGICA PRINCIPAL ---
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
    
    df_grafico = pd.DataFrame({
        "Estado": ["Saludable", "Anomalías"],
        "Volumen": [total_saludables, total_anomalias]
    })

    st.bar_chart(df_grafico.set_index("Estado"), use_container_width=True)

    st.divider()
    
    # --- VISUALIZACIÓN DE ALERTAS EN TABLA ---
    if total_anomalias > 0 and lista_anomalias:
        df_anomalias = pd.DataFrame(lista_anomalias)
        st.error(f"🚨 ¡ALERTA! Se han detectado {total_anomalias} anomalías.")
        st.subheader("Trazas Anómalas (Aislamiento de Causa Raíz)")
        
        columnas_deseadas = [
            'traceId', 'level', 'event_type', 'http_status', 
            'duration_ms', 'tiene_error_5xx', 'service'
        ]
        
        columnas_a_mostrar = [col for col in columnas_deseadas if col in df_anomalias.columns]
        
        st.dataframe(
            df_anomalias[columnas_a_mostrar],
            use_container_width=True,
            hide_index=True
        )
        
        with st.expander("Ver JSON crudo de anomalías"):
            st.json(lista_anomalias)
            
    else:
        st.success("✅ No se detectan anomalías.")

else:
    st.warning("Esperando datos de telemetría de Loki y FastAPI...")