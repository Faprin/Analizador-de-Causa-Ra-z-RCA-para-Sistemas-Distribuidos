import os
import requests
import json
from datetime import datetime, timedelta


# ====================
#   Direcciones
# ====================
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "datasets")
LOKI_URL = "http://localhost:3100"
JSON_PATH = os.path.join(OUTPUT_DIR, "logs_dataset.json")
CSV_PATH  = os.path.join(OUTPUT_DIR, "logs_dataset.csv")


# ====================
#   Descarga y Parseo
# ====================
def descargar(horas_atras = 24, limite = 5000):

    tiempo_actual = datetime.utcnow()
    inicio = tiempo_actual - timedelta(hours = horas_atras)

    start = int(inicio.timestamp() * 1e9)
    end = int(tiempo_actual.timestamp() * 1e9)

    response = requests.post(
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
    return response.json()

def parsear_logs(raw):
    registros = []
    for stream in raw["data"]["result"]:
        servicio = stream["stream"].get("service", "unknown")
        for timestamp, linea in stream["values"]:
            try:
                log = json.loads(linea)
                log["service"] = servicio
                registros.append(log)
            except json.JSONDecodeError:
                pass  # ignora líneas que no son JSON
    return registros

# ====================
#   MAIN
# ====================
if __name__ == "__main__":
    print("Descargando logs de Loki...")
    raw  = descargar(horas_atras=24, limite=5000)
    logs = parsear_logs(raw)
    print(f"Logs descargados: {len(logs)}")

    with open(JSON_PATH, "w") as f:
        json.dump(logs, f, indent=2)

    print("Guardado en logs_dataset.json")