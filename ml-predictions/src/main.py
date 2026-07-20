from fastapi import FastAPI, HTTPException
from typing import Optional
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import pandas as pd
import requests
from datetime import datetime, timedelta
import json

from features import clean
from model import rca_model

LOKI_URL = "http://localhost:3100"

# ============================
# CLASES AUXILIARES
# ============================
class Log(BaseModel):
    model_config = {"extra": "ignore", "populate_by_name": True}
    
    timestamp: str = Field(None, alias = "@timestamp")
    service: str
    level: str
    event_type: Optional[str] = None
    outcome: Optional[str] = None
    http_method: Optional[str] = None
    http_uri: Optional[str] = None
    http_status: Optional[str] = None
    duration_ms: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_origin: Optional[str] = None
    traceId: Optional[str] = None

class LogBatch(BaseModel):
    logs: list[Log]

# ============================
# LIFESPAN (contexto de la API)
# ============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # cargar el modelo
    print("[*] Cargando el modelo...")
    rca_model.load_model()
    print("[*] Modelo cargado correctamente")

    # ejecucion del contexto
    yield

    # paramos el servidor
    print("[*] Cerrando Servidor")

app = FastAPI(
    title="RCA - Motor Analitico",
    lifespan=lifespan
)

# ============================
# ENDPOINTS
# ============================
@app.get("/health")
async def health():
    ''' Comprueba que el servidor esta arrancado '''
    return {
        "status": "ok",
        "modelo_cargado": rca_model.model is not None
    }

@app.post("/predict")
def predict(batch: LogBatch):
    """
        Recibe un array de logs en Json, los procesa y detecta las anomalias con IsolationForest
    """

    if not batch.logs:
        raise HTTPException(status_code=400, detail="No se han recibido logs en la peticion")
    
    df_raw = pd.DataFrame([log.model_dump(by_alias=True) for log in batch.logs])
    df_raw = df_raw.rename(columns={"timestamp": "@timestamp"})

    try:
        df_clean = clean(df_raw)
    except Exception as e:
        print(str(e))
        raise HTTPException(status_code=422, detail=f'Error en la transofrmacion de los datos: {str(e)}')
    
    if df_clean.empty:
        return {
            "anomalias": [],
            "total": 0
        }
    
    anomalias = rca_model.predict(df_clean)
    anomalias = anomalias.replace([float('inf'), float('-inf')], None).fillna(0)

    return {
        "total_analizado": str(len(df_clean)),
        "total_anomalias": str(len(anomalias)),
        "anomalias": anomalias.to_dict(orient="records")
    }

@app.get("/analize")
async def analize(horas: int = 1):
    """
    COnsulta directamente loki, procesa y analiza las anomalias y las devuelve.
    No hace falta enviar nada en el cuerpo de la peticion
    """

    df_raw = loki_download(horas_atras=horas)

    if df_raw.empty:
        return {
            "anomalias": [],
            "total_analizadas": 0,
            "message": "No se han encontrado registros para analizar"
        }
    
    try:
        df_clean = clean(df_raw)

    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Error en la transformacion de datos {str(e)}")

    if df_clean.empty:
        return {
            "anomalias": [],
            "total_analizadas": 0,
            "message": "No se han encontrado registros para analizar"
        }
    
    anomalias = rca_model.predict(df_clean)

    return {
        "total_analizado": len(df_clean),
        "total_anomalias": len(anomalias),
        "anomalias": anomalias.to_dict(orient="records")
    }




# ============================
# FUNCIONES AUXILIARES  
# ============================
def loki_download(horas_atras: int = 1, limite: int = 1000):

    tiempo_actual = datetime.now()
    inicio = tiempo_actual - timedelta(hours = horas_atras)

    start = int(inicio.timestamp() * 1e9)
    end = int(tiempo_actual.timestamp() * 1e9)

    try:
        response = requests.get(
            f"{LOKI_URL}/loki/api/v1/query_range",
            params={
                "query": '{service=~"api-inventario|api-pedidos|api-autenticacion"}',
                "start": start,
                "end":   end,
                "limit": limite,
                "direction": "forward"
            }
        )
        response.raise_for_status()
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Error en la descarga de loki: {str(e)}")

    registros = []
    for stream in response.json().get("data", {}).get("result", []):
        servicio = stream["stream"].get("service", "unknown")
        for _, linea in stream["values"]:
            try:
                log = json.loads(linea)
                log["service"] = servicio
                registros.append(log)
            except json.JSONDecodeError:
                pass

    return pd.DataFrame(registros) if registros else pd.DataFrame()