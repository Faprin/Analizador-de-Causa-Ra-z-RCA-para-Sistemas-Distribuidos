from fastapi import FastAPI, HTTPException
from typing import Optional
from pydantic import BaseModel, Field
from contextlib import asynccontextmanager
import pandas as pd

from features import clean
from model import rca_model

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
        raise HTTPException(status_code=422, detail=f'Error en la transofrmacion de los datos: {str(e)}')
    
    if df_clean.empty:
        return {
            "anomalias": [],
            "total": 0
        }
    
    anomalias = rca_model.predict(df_clean)

    return {
        "total_analizado": len(df_clean),
        "total_anomalias": len(anomalias),
        "anomalias": anomalias.to_dict(orient="records")
    }
